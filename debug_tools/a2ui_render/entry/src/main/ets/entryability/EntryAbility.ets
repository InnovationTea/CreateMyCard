import { AbilityConstant, ConfigurationConstant, UIAbility, Want } from '@kit.AbilityKit';
import { util } from '@kit.ArkTS';
import { fileIo } from '@kit.CoreFileKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { window } from '@kit.ArkUI';
import { executeDesktopCommand } from '../runner/DesktopBridge';
import { DEFAULT_HEIGHT, DEFAULT_WIDTH, isSafeSampleFile, normalizeDimension, RenderRequest } from '../runner/A2UIProtocol';

const DOMAIN = 0x0000;
const TAG = 'A2UIRunner';
const REQUEST_STORAGE_KEY = 'a2uiRenderRequest';

export default class EntryAbility extends UIAbility {
  private sampleChunks: Map<string, string[]> = new Map<string, string[]>();

  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    try {
      this.context.getApplicationContext().setColorMode(ConfigurationConstant.ColorMode.COLOR_MODE_NOT_SET);
    } catch (err) {
      hilog.error(DOMAIN, TAG, 'Failed to set colorMode. Cause: %{public}s', JSON.stringify(err));
    }
    AppStorage.setOrCreate<string>(REQUEST_STORAGE_KEY, '');
    this.publishRequest(want);
  }

  onNewWant(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    this.publishRequest(want);
  }

  private publishRequest(want: Want): void {
    const parameters: Record<string, Object> | undefined = want.parameters;
    const runIdValue: Object | undefined = parameters?.['runId'];
    const sampleFileValue: Object | undefined = parameters?.['sampleFile'];
    const widthValue: Object | undefined = parameters?.['width'];
    const heightValue: Object | undefined = parameters?.['height'];
    const transportValue: Object | undefined = parameters?.['sampleTransport'];
    const providedRunId: string = typeof runIdValue === 'string' ? runIdValue : '';
    const providedSampleFile: string = typeof sampleFileValue === 'string' ? sampleFileValue : '';
    const rawWidth: number | undefined = typeof widthValue === 'number' ? widthValue : undefined;
    const rawHeight: number | undefined = typeof heightValue === 'number' ? heightValue : undefined;
    const hasExternalSample: boolean = providedSampleFile.length > 0;
    const runId: string = providedRunId.length > 0 ? providedRunId : `manual-${Date.now()}`;

    if (hasExternalSample && !isSafeSampleFile(providedSampleFile)) {
      this.logFailed(runId, providedSampleFile, 'INVALID_SAMPLE_FILE', 'sampleFile contains unsafe characters');
      return;
    }

    if (transportValue === 'base64-chunk') {
      this.receiveSampleChunk(parameters, runId, providedSampleFile, rawWidth, rawHeight);
      return;
    }

    if (parameters?.['desktopOperation'] === true) {
      void executeDesktopCommand(this.context, providedSampleFile);
      return;
    }

    this.publishRenderRequest(runId, providedSampleFile, rawWidth, rawHeight);
  }

  private receiveSampleChunk(parameters: Record<string, Object> | undefined, runId: string, sampleFile: string,
    rawWidth: number | undefined, rawHeight: number | undefined): void {
    const indexValue: Object | undefined = parameters?.['chunkIndex'];
    const countValue: Object | undefined = parameters?.['chunkCount'];
    const chunkValue: Object | undefined = parameters?.['sampleChunk'];
    const validNumbers: boolean = typeof indexValue === 'number' && typeof countValue === 'number' &&
      Number.isInteger(indexValue) && Number.isInteger(countValue);
    if (!validNumbers || typeof chunkValue !== 'string') {
      this.sampleChunks.delete(runId);
      this.logFailed(runId, sampleFile, 'INVALID_SAMPLE_CHUNK', 'sample chunk parameters are invalid');
      return;
    }
    const chunkIndex: number = indexValue as number;
    const chunkCount: number = countValue as number;
    if (chunkIndex < 0 || chunkCount <= 0 || chunkIndex >= chunkCount || chunkCount > 1024 ||
      chunkValue.length === 0 || chunkValue.length > 8192) {
      this.sampleChunks.delete(runId);
      this.logFailed(runId, sampleFile, 'INVALID_SAMPLE_CHUNK', 'sample chunk is out of bounds');
      return;
    }

    let chunks: string[] | undefined = this.sampleChunks.get(runId);
    if (chunks === undefined || chunks.length !== chunkCount) {
      chunks = new Array<string>(chunkCount).fill('');
      this.sampleChunks.set(runId, chunks);
    }
    chunks[chunkIndex] = chunkValue;
    if (!chunks.every((value: string) => value.length > 0)) {
      return;
    }

    this.sampleChunks.delete(runId);
    try {
      const encoded: string = chunks.join('');
      const limit: number = parameters?.['desktopOperation'] === true ? 6_144_000 : 3_000_000;
      if (encoded.length > limit) {
        throw new Error('sample payload is too large');
      }
      const decoded: Uint8Array = new util.Base64Helper().decodeSync(encoded, util.Type.BASIC);
      const decoder = util.TextDecoder.create('utf-8', { fatal: false, ignoreBOM: true });
      const sampleText: string = decoder.decodeToString(decoded, { stream: false });
      const sampleRoot: string = `${this.context.filesDir}/a2ui`;
      fileIo.mkdirSync(sampleRoot, true);
      const sample = fileIo.openSync(`${sampleRoot}/${sampleFile}`,
        fileIo.OpenMode.CREATE | fileIo.OpenMode.READ_WRITE | fileIo.OpenMode.TRUNC);
      try {
        fileIo.writeSync(sample.fd, sampleText);
      } finally {
        fileIo.closeSync(sample);
      }
    } catch (err) {
      this.logFailed(runId, sampleFile, 'SAMPLE_TRANSFER_FAILED', (err as Error).message);
      return;
    }
    if (parameters?.['desktopOperation'] === true) {
      void executeDesktopCommand(this.context, sampleFile);
    } else {
      this.publishRenderRequest(runId, sampleFile, rawWidth, rawHeight);
    }
  }

  private publishRenderRequest(runId: string, providedSampleFile: string, rawWidth: number | undefined,
    rawHeight: number | undefined): void {
    const hasExternalSample: boolean = providedSampleFile.length > 0;

    const request: RenderRequest = {
      runId: runId,
      sampleFile: hasExternalSample ? providedSampleFile : 'test.json',
      width: normalizeDimension(rawWidth, DEFAULT_WIDTH),
      height: normalizeDimension(rawHeight, DEFAULT_HEIGHT),
      useRawResource: !hasExternalSample
    };
    AppStorage.set<string>(REQUEST_STORAGE_KEY, JSON.stringify(request));
  }

  private logFailed(runId: string, sample: string, code: string, message: string): void {
    const payload: Record<string, Object> = {
      'runId': runId,
      'state': 'FAILED',
      'sample': sample,
      'code': code,
      'message': message
    };
    hilog.error(DOMAIN, TAG, '%{public}s', `A2UI_RUN ${JSON.stringify(payload)}`);
  }

  onDestroy(): void {
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onDestroy');
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    try {
      const mainWindow: window.Window = windowStage.getMainWindowSync();
      mainWindow.setWindowLayoutFullScreen(true).catch((err: Error) => {
        hilog.warn(DOMAIN, TAG, 'Failed to enable full screen. Cause: %{public}s', JSON.stringify(err));
      });
      mainWindow.setWindowSystemBarEnable([]).catch((err: Error) => {
        hilog.warn(DOMAIN, TAG, 'Failed to hide system bars. Cause: %{public}s', JSON.stringify(err));
      });
      mainWindow.setSpecificSystemBarEnabled('status', false).catch((err: Error) => {
        hilog.warn(DOMAIN, TAG, 'Failed to hide status bar. Cause: %{public}s', JSON.stringify(err));
      });
      mainWindow.setSpecificSystemBarEnabled('navigation', false).catch((err: Error) => {
        hilog.warn(DOMAIN, TAG, 'Failed to hide navigation bar. Cause: %{public}s', JSON.stringify(err));
      });
      mainWindow.setSpecificSystemBarEnabled('navigationIndicator', false).catch((err: Error) => {
        hilog.warn(DOMAIN, TAG, 'Failed to hide navigation indicator. Cause: %{public}s', JSON.stringify(err));
      });
    } catch (err) {
      hilog.warn(DOMAIN, TAG, 'Failed to configure window. Cause: %{public}s', JSON.stringify(err));
    }

    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        hilog.error(DOMAIN, TAG, 'Failed to load the content. Cause: %{public}s', JSON.stringify(err));
        return;
      }
      hilog.info(DOMAIN, TAG, 'Succeeded in loading the content.');
    });
  }

  onWindowStageDestroy(): void {
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onWindowStageDestroy');
  }

  onForeground(): void {
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onForeground');
  }

  onBackground(): void {
    hilog.info(DOMAIN, TAG, '%{public}s', 'Ability onBackground');
  }
}
