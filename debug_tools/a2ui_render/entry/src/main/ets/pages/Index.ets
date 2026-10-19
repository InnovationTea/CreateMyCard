import {
  CatalogFactory,
  SurfaceControllerFactory,
  SurfaceController,
  SurfaceErrorCode,
  SurfaceEventType,
  UIRendererComponent
} from '@arkui-genius/genui_form';
import { common } from '@kit.AbilityKit';
import { fileIo } from '@kit.CoreFileKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { util } from '@kit.ArkTS';
import {
  isValidContainerSize,
  parseA2UIMessages,
  RenderRequest,
  stageInitialDataModel
} from '../runner/A2UIProtocol';

const DOMAIN = 0x0000;
const TAG = 'A2UIRunner';
const REQUEST_STORAGE_KEY = 'a2uiRenderRequest';
const CAPTURE_ROOT_ID = 'a2ui_capture_root';

@Entry
@Component
struct Index {
  @StorageLink(REQUEST_STORAGE_KEY) @Watch('onRenderRequestChanged') renderRequestJson: string = '';
  @State controller: SurfaceController | undefined = undefined;
  @State cardWidth: number = 150;
  @State cardHeight: number = 150;
  @State rendererVisible: boolean = false;
  @State renderKey: string = '';
  private viewportWidth: number = 0;
  private viewportHeight: number = 0;
  private activeRunId: string = '';
  private pendingRequestJson: string = '';
  private warnings: string[] = [];
  private fatalError: string = '';
  private componentsUpdated: boolean = false;

  // Keep the ArkUI primitives used indirectly by genui_form reachable so the
  // application compiler does not tree-shake their dynamic render functions.
  @Builder
  private genuiFormDeclarations() {
    if (false) {
      Text('')
      Row() {}
      Column() {}
      Stack() {}
    }
  }

  aboutToAppear(): void {
    this.pendingRequestJson = this.renderRequestJson;
    this.tryStartPendingRequest();
  }

  aboutToDisappear(): void {
    this.controller?.destroy();
    this.controller = undefined;
  }

  onRenderRequestChanged(): void {
    this.pendingRequestJson = this.renderRequestJson;
    this.tryStartPendingRequest();
  }

  private tryStartPendingRequest(): void {
    if (this.viewportWidth <= 0 || this.viewportHeight <= 0 || this.pendingRequestJson.length === 0) {
      return;
    }
    try {
      const request: RenderRequest = JSON.parse(this.pendingRequestJson) as RenderRequest;
      if (request.runId === this.activeRunId) {
        return;
      }
      this.startRun(request);
    } catch (err) {
      this.logState('unknown', 'FAILED', '', 'INVALID_REQUEST', (err as Error).message);
    }
  }

  private startRun(request: RenderRequest): void {
    this.activeRunId = request.runId;
    this.warnings = [];
    this.fatalError = '';
    this.componentsUpdated = false;
    this.rendererVisible = false;
    this.renderKey = '';
    this.controller?.destroy();
    this.controller = undefined;
    this.logState(request.runId, 'RECEIVED', request.sampleFile);

    if (!isValidContainerSize(request.width, request.height, this.viewportWidth, this.viewportHeight)) {
      this.logState(request.runId, 'FAILED', request.sampleFile, 'INVALID_DIMENSIONS',
        `Requested ${request.width}x${request.height}vp exceeds viewport ${this.viewportWidth}x${this.viewportHeight}vp`);
      return;
    }

    this.cardWidth = request.width;
    this.cardHeight = request.height;
    let messages: object[];
    try {
      this.logState(request.runId, 'LOADING', request.sampleFile);
      const content: string = this.loadSample(request);
      messages = stageInitialDataModel(parseA2UIMessages(content));
      this.logState(request.runId, 'PARSED', request.sampleFile, '', '', messages.length);
    } catch (err) {
      this.logState(request.runId, 'FAILED', request.sampleFile, 'SAMPLE_LOAD_FAILED', (err as Error).message);
      return;
    }

    // Let ArkUI commit removal of the previous keyed renderer before mounting
    // the next controller. Without this frame boundary rapid onNewWant calls
    // can leave UIRendererComponent observing the destroyed controller.
    setTimeout(() => this.mountController(request, messages), 32);
  }

  private mountController(request: RenderRequest, messages: object[]): void {
    if (request.runId !== this.activeRunId) {
      return;
    }
    const runId: string = request.runId;
    this.controller = SurfaceControllerFactory.createSurfaceController({
      catalog: CatalogFactory.extended(),
      eventCallback: (eventType: SurfaceEventType, controller: SurfaceController, surfaceId: string): void => {
        if (runId === this.activeRunId && eventType === SurfaceEventType.SURFACE_COMPONENTS_UPDATED) {
          this.componentsUpdated = true;
        }
      }
    });
    this.controller.enableSchemaWarningReport(true);
    this.controller.registerErrorCallback((code: SurfaceErrorCode, errorMessage: string): void => {
      if (runId !== this.activeRunId) {
        return;
      }
      if (this.isRecoverableWarning(code)) {
        if (this.warnings.length < 8) {
          this.warnings.push(`${code}: ${errorMessage}`.slice(0, 300));
        }
      } else {
        this.fatalError = `${code}: ${errorMessage}`;
      }
    });

    this.renderKey = runId;
    this.rendererVisible = true;
    // Give the keyed UIRendererComponent one frame to subscribe to the new
    // controller before messages are delivered.
    setTimeout(() => this.applyMessages(request, messages), 32);
  }

  private loadSample(request: RenderRequest): string {
    const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    try {
      if (!request.useRawResource) {
        const applicationFilesDir: string = context.getApplicationContext().filesDir;
        const samplePath: string = `${applicationFilesDir}/a2ui/${request.sampleFile}`;
        const content: string = fileIo.readTextSync(samplePath);
        fileIo.unlinkSync(samplePath);
        return content;
      }
      const fileData: Uint8Array = context.resourceManager.getRawFileContentSync(request.sampleFile);
      const decoder = util.TextDecoder.create('utf-8', { fatal: false, ignoreBOM: true });
      return decoder.decodeToString(fileData, { stream: false });
    } catch (err) {
      throw new Error(`Cannot read ${request.sampleFile}: ${(err as Error).message}`);
    }
  }

  private applyMessages(request: RenderRequest, messages: object[]): void {
    if (request.runId !== this.activeRunId) {
      return;
    }
    this.logState(request.runId, 'RENDERING', request.sampleFile);
    messages.forEach((message: object) => {
      if (this.fatalError.length === 0) {
        this.controller?.handleMessage(JSON.stringify(message));
      }
    });

    if (this.fatalError.length > 0) {
      this.logState(request.runId, 'FAILED', request.sampleFile, 'RENDER_ERROR', this.fatalError);
      return;
    }
    if (!this.componentsUpdated) {
      this.logState(request.runId, 'FAILED', request.sampleFile, 'NO_COMPONENT_TREE',
        'No updateComponents message produced a component tree');
      return;
    }
    setTimeout(() => this.finishWhenRendered(request), 0);
  }

  private async finishWhenRendered(request: RenderRequest, attempt: number = 0): Promise<void> {
    if (request.runId !== this.activeRunId) {
      return;
    }
    try {
      const pixelMap = await this.getUIContext().getComponentSnapshot().get(CAPTURE_ROOT_ID, {
        waitUntilRenderFinished: true
      });
      if (request.runId !== this.activeRunId) {
        await pixelMap.release();
        return;
      }
      const info = this.getUIContext().getComponentUtils().getRectangleById(CAPTURE_ROOT_ID);
      const crop: Record<string, Object> = {
        'left': Math.round(info.screenOffset.x),
        'top': Math.round(info.screenOffset.y),
        'width': Math.round(info.size.width),
        'height': Math.round(info.size.height)
      };
      await pixelMap.release();
      const state: string = this.warnings.length > 0 ? 'READY_WITH_WARNINGS' : 'READY';
      this.logTerminalState(request, state, crop);
    } catch (err) {
      // The surface event can arrive one frame before the ArkUI wrapper with
      // CAPTURE_ROOT_ID is available to ComponentSnapshot. Retry briefly while
      // still requiring a successful waitUntilRenderFinished snapshot.
      if (request.runId === this.activeRunId && attempt < 20) {
        setTimeout(() => this.finishWhenRendered(request, attempt + 1), 50);
        return;
      }
      const errorMessage: string = (err as Error).message ?? String(err);
      this.logState(request.runId, 'FAILED', request.sampleFile, 'SNAPSHOT_FAILED', errorMessage);
    }
  }

  private isRecoverableWarning(code: SurfaceErrorCode): boolean {
    return code === SurfaceErrorCode.COMPONENT_DROPPED_ON_INVALID_PARAMETER ||
      code === SurfaceErrorCode.FALLBACK_WARNING || code === SurfaceErrorCode.SCHEMA_WARNING;
  }

  private logTerminalState(request: RenderRequest, state: string, crop: Record<string, Object>): void {
    const payload: Record<string, Object> = {
      'runId': request.runId,
      'state': state,
      'sample': request.sampleFile,
      'widthVp': request.width,
      'heightVp': request.height,
      'cropPx': crop,
      'warnings': this.warnings
    };
    hilog.info(DOMAIN, TAG, '%{public}s', `A2UI_RUN ${JSON.stringify(payload)}`);
  }

  private logState(runId: string, state: string, sample: string, code: string = '', message: string = '',
    messageCount: number = 0): void {
    const payload: Record<string, Object> = {
      'runId': runId,
      'state': state,
      'sample': sample
    };
    if (code.length > 0) {
      payload['code'] = code;
    }
    if (message.length > 0) {
      payload['message'] = message;
    }
    if (messageCount > 0) {
      payload['messageCount'] = messageCount;
    }
    const serialized: string = `A2UI_RUN ${JSON.stringify(payload)}`;
    if (state === 'FAILED') {
      hilog.error(DOMAIN, TAG, '%{public}s', serialized);
    } else {
      hilog.info(DOMAIN, TAG, '%{public}s', serialized);
    }
  }

  build() {
    Column() {
      this.genuiFormDeclarations()
      if (this.rendererVisible && this.controller !== undefined) {
        ForEach([this.renderKey], (_key: string) => {
          Stack() {
            UIRendererComponent({ surfaceController: this.controller })
              .width('100%')
              .height('100%')
          }
          .id(CAPTURE_ROOT_ID)
          .width(this.cardWidth)
          .height(this.cardHeight)
        }, (key: string) => key)
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor(Color.White)
    .justifyContent(FlexAlign.Center)
    .alignItems(HorizontalAlign.Center)
    .onAreaChange((_oldValue: Area, newValue: Area) => {
      this.viewportWidth = Number(newValue.width);
      this.viewportHeight = Number(newValue.height);
      this.tryStartPendingRequest();
    })
  }
}
