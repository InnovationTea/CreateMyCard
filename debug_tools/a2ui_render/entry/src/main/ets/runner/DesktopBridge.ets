import { bundleManager, common } from '@kit.AbilityKit';
import { formBindingData, formInfo, formProvider } from '@kit.FormKit';
import { fileIo } from '@kit.CoreFileKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { display } from '@kit.ArkUI';
import { i18n } from '@kit.LocalizationKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { isSafeSampleFile } from './A2UIProtocol';
import {
  DesktopCommand, DESKTOP_FORM_NAME, readDesktopEnvelope, readDesktopReceipt, saveDesktopEnvelope
} from './DesktopProtocol';

function screenshotPixel(value: number): number {
  // 与电脑端Python round保持一致，避免非整数密度下的半像素取整差异。
  const lower = Math.floor(value);
  return value - lower === 0.5 && lower % 2 === 0 ? lower : Math.round(value);
}

async function replaceDesktopContent(context: common.UIAbilityContext, command: DesktopCommand,
  result: Record<string, Object>): Promise<void> {
  const envelope = command.envelope;
  const expected = command.expectedForms;
  const bounds = command.expectedRectPx;
  const signature = command.expectedDisplay;
  if (envelope === undefined || expected === undefined || bounds === undefined || signature === undefined) {
    throw new Error('Missing desktop replacement guards');
  }
  const screen = display.getDefaultDisplaySync();
  if (signature.length !== 4 || screen.width !== signature[0] || screen.height !== signature[1] ||
    screen.densityPixels !== signature[2] || screen.rotation !== signature[3]) {
    throw new Error('Desktop display changed before replacement');
  }
  const verifyForms = async (): Promise<void> => {
    const published = await formProvider.getPublishedRunningFormInfos();
    const forms = published.filter((item: formInfo.RunningFormInfo) =>
      item.formName === DESKTOP_FORM_NAME && item.formLocation === formInfo.FormLocation.DESKTOP);
    if (expected.length !== 2 || expected[0].dimension !== 2 || expected[1].dimension !== 3 || forms.length !== 2) {
      throw new Error('Desktop requires exactly one form of each dimension');
    }
    expected.forEach((item) => {
      if (!forms.some((actual: formInfo.RunningFormInfo) =>
        actual.formId === item.formId && actual.dimension === item.dimension)) {
        throw new Error('Desktop form removed or replaced');
      }
    });
    result['forms'] = forms;
  };
  const verifyRect = async (key: string): Promise<void> => {
    const rect = await formProvider.getFormRect(command.formId as string);
    const current = display.getDefaultDisplaySync();
    if (current.width !== signature[0] || current.height !== signature[1] ||
      current.densityPixels !== signature[2] || current.rotation !== signature[3]) {
      throw new Error('Desktop display changed during replacement');
    }
    const density = current.densityPixels;
    if (screenshotPixel(rect.left * density) !== bounds.left || screenshotPixel(rect.top * density) !== bounds.top ||
      screenshotPixel(rect.width * density) !== bounds.width || screenshotPixel(rect.height * density) !== bounds.height) {
      throw new Error('Desktop bounds changed during replacement');
    }
    result[key] = rect;
  };
  const dimension = envelope.size === '2x2' ? 2 : envelope.size === '2x4' ? 3 : 0;
  if (!expected.some((item) => item.formId === command.formId && item.dimension === dimension)) {
    throw new Error('Desktop envelope dimension does not match target');
  }
  await verifyForms();
  await verifyRect('beforeRectVp');
  await saveDesktopEnvelope(context, envelope);
  await verifyForms();
  await verifyRect('stagedRectVp');
  const data: Record<string, string> = {
    'desktopEnvelope': readDesktopEnvelope(context, envelope.size),
    'desktopFormId': command.formId as string, 'desktopSize': envelope.size
  };
  await formProvider.updateForm(command.formId as string, formBindingData.createFormBindingData(data));
  await verifyRect('updatedRectVp');
  await verifyForms();
  await verifyRect('rectVp');
  result['runId'] = envelope.runId;
  result['revision'] = envelope.revision;
  result['digest'] = envelope.digest;
}

export async function executeDesktopCommand(context: common.UIAbilityContext, sampleFile: string): Promise<void> {
  let commandId: string = '';
  try {
    if (!isSafeSampleFile(sampleFile)) {
      throw new Error('Unsafe desktop command filename');
    }
    const path: string = `${context.getApplicationContext().filesDir}/a2ui/${sampleFile}`;
    const content: string = fileIo.readTextSync(path);
    const command = JSON.parse(content) as DesktopCommand;
    commandId = command.commandId;
    if (!/^[A-Za-z0-9-]{1,100}$/.test(commandId)) {
      throw new Error('Invalid desktop command identity');
    }
    const result: Record<string, Object> = { 'commandId': commandId, 'state': 'OK' };
    const published = command.operation === 'environment' ? [] : await formProvider.getPublishedRunningFormInfos();
    const forms: formInfo.RunningFormInfo[] = [];
    published.forEach((item: formInfo.RunningFormInfo) => {
      if (item.formName === DESKTOP_FORM_NAME && item.formLocation === formInfo.FormLocation.DESKTOP) {
        forms.push(item);
      }
    });
    result['forms'] = forms;
    if (command.operation === 'replace') {
      await replaceDesktopContent(context, command, result);
    } else if (command.operation === 'stage') {
      if (command.envelope === undefined) {
        throw new Error('Missing desktop envelope');
      }
      await saveDesktopEnvelope(context, command.envelope);
    } else if (command.operation === 'update' || command.operation === 'rect' || command.operation === 'receipt') {
      const target = forms.find((item: formInfo.RunningFormInfo) => item.formId === command.formId);
      if (target === undefined) {
        throw new Error('Desktop form identity does not exist');
      }
      if (command.operation === 'update') {
        const size = target.dimension === 2 ? '2x2' : '2x4';
        const data: Record<string, string> = {
          'desktopEnvelope': readDesktopEnvelope(context, size), 'desktopFormId': target.formId, 'desktopSize': size
        };
        if (data.desktopEnvelope.length === 0) {
          throw new Error('No staged desktop envelope');
        }
        if (target.dimension !== 2 && target.dimension !== 3) { throw new Error('Unsupported dimension'); }
        await formProvider.updateForm(target.formId, formBindingData.createFormBindingData(data));
      }
      if (command.operation === 'receipt') {
        result['receipt'] = readDesktopReceipt(context, target.formId);
      } else {
        result['rectVp'] = await formProvider.getFormRect(target.formId);
      }
    } else if (command.operation !== 'status' && command.operation !== 'environment') {
      throw new Error('Unsupported desktop operation');
    }
    const screen = display.getDefaultDisplaySync();
    result['density'] = screen.densityPixels;
    result['displayWidth'] = screen.width;
    result['displayHeight'] = screen.height;
    result['rotation'] = screen.rotation;
    result['locale'] = i18n.System.getSystemLocaleInstance().toString();
    result['desktopProtocolVersion'] = 3;
    result['desktopBatchUpdate'] = true;
    result['appVersion'] = bundleManager.getBundleInfoForSelfSync(
      bundleManager.BundleFlag.GET_BUNDLE_INFO_DEFAULT).versionName;
    hilog.info(0, 'A2UIDesktop', '%{public}s', `A2UI_DESKTOP ${JSON.stringify(result)}`);
    fileIo.unlinkSync(path);
  } catch (err) {
    hilog.error(0, 'A2UIDesktop', '%{public}s', `A2UI_DESKTOP ${JSON.stringify({
      commandId: commandId, state: 'FAILED', code: (err as BusinessError).code, message: (err as Error).message
    })}`);
  }
}
