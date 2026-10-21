import {
  CatalogFactory, SurfaceControllerFactory, SurfaceController, SurfaceErrorCode, SurfaceEventType, UIRendererComponent
} from '@arkui-genius/genui_form';
import { DesktopEnvelope, desktopMarker } from '../runner/DesktopProtocol';
import { parseA2UIMessages, stageInitialDataModel } from '../runner/A2UIProtocol';

const storage = new LocalStorage();

@Component
struct DesktopSurface {
  envelope: DesktopEnvelope | undefined = undefined;
  @State marker: string = '';
  private controller: SurfaceController = SurfaceControllerFactory.createSurfaceController({
    catalog: CatalogFactory.extended(),
    eventCallback: (event: SurfaceEventType): void => {
      if (event === SurfaceEventType.SURFACE_COMPONENTS_UPDATED) { this.componentsUpdated = true; }
    }
  });
  private componentsUpdated: boolean = false;
  private active: boolean = true;
  private applied: boolean = false;
  private failed: boolean = false;
  private warnings: string[] = [];

  aboutToDisappear(): void { this.active = false; this.controller.destroy(); }

  private apply(): void {
    if (this.applied || this.envelope === undefined) { return; }
    this.applied = true;
    this.controller.enableSchemaWarningReport(true);
    this.controller.registerErrorCallback((code: SurfaceErrorCode, message: string) => {
      if (code === SurfaceErrorCode.COMPONENT_DROPPED_ON_INVALID_PARAMETER ||
        code === SurfaceErrorCode.FALLBACK_WARNING || code === SurfaceErrorCode.SCHEMA_WARNING) {
        if (this.warnings.length < 8) { this.warnings.push(message.slice(0, 300)); }
      } else {
        this.failed = true;
        this.report('FAILED', message);
      }
    });
    try {
      const messages = stageInitialDataModel(parseA2UIMessages(this.envelope.dsl));
      messages.forEach((message: object) => {
        if (!this.failed) { this.controller.handleMessage(JSON.stringify(message)); }
      });
      if (!this.failed && !this.componentsUpdated) {
        this.failed = true;
        this.report('FAILED', 'No component tree produced');
      }
      if (!this.failed) { this.report('APPLIED', ''); }
    } catch (err) {
      this.failed = true;
      this.report('FAILED', (err as Error).message);
    }
  }

  private report(state: string, message: string): void {
    if (this.envelope === undefined || !this.active) { return; }
    this.marker = desktopMarker(this.envelope);
    postCardAction(this, { action: 'message', params: {
      runId: this.envelope.runId, revision: this.envelope.revision, digest: this.envelope.digest,
      size: this.envelope.size,
      state: state, message: message, warnings: this.warnings
    } });
  }

  @Builder
  private declarations() {
    if (false) {
      Text('')
      Image('')
      Divider()
      Progress({ value: 0, total: 100 })
      Button('')
      Checkbox()
      Row() {}
      Column() {}
      Stack() {}
      Blank()
      List() {}
      ListItem() {}
    }
  }

  build() {
    Stack() {
      this.declarations()
      UIRendererComponent({ surfaceController: this.controller })
        .width('100%').height('100%').onAppear(() => this.apply())
    }.width('100%').height('100%').accessibilityDescription(this.marker)
  }
}

@Entry(storage)
@Component
struct DebugFormCard {
  @LocalStorageProp('desktopFormId') formId: string = '';
  @LocalStorageProp('desktopSize') cardSize: string = '';
  @LocalStorageProp('desktopEnvelope') @Watch('onEnvelopeChanged') envelopeText: string = '';
  @State envelopes: DesktopEnvelope[] = [];
  private activeRun: string = '';
  private activeRevision: number = 0;

  aboutToAppear(): void { this.onEnvelopeChanged(); }

  onEnvelopeChanged(): void {
    if (this.envelopeText.length === 0) { return; }
    try {
      const envelope = JSON.parse(this.envelopeText) as DesktopEnvelope;
      parseA2UIMessages(envelope.dsl);
      if (envelope.runId === this.activeRun && envelope.revision <= this.activeRevision) { return; }
      this.activeRun = envelope.runId;
      this.activeRevision = envelope.revision;
      this.envelopes = [envelope];
    } catch (err) {
      this.envelopes = [];
      postCardAction(this, { action: 'message', params: { state: 'FAILED', message: (err as Error).message } });
    }
  }

  build() {
    Stack() {
      if (this.envelopes.length === 0) {
        Text(`${this.cardSize} 桌面卡片已就绪`).fontSize(14)
      }
      ForEach(this.envelopes, (envelope: DesktopEnvelope) => {
        DesktopSurface({ envelope: envelope })
      }, (envelope: DesktopEnvelope) => desktopMarker(envelope))
    }.width('100%').height('100%').accessibilityDescription(`A2UI_FORM:${this.formId}`)
  }
}
