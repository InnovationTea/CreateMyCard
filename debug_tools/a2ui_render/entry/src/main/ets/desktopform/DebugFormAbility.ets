import { FormExtensionAbility, formBindingData, formInfo, formProvider } from '@kit.FormKit';
import { Want } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import {
  readDesktopEnvelope, saveDesktopReceipt, removeDesktopReceipt, DESKTOP_FORM_NAME
} from '../runner/DesktopProtocol';

export default class DebugFormAbility extends FormExtensionAbility {
  onAddForm(want: Want): formBindingData.FormBindingData {
    const dimension = want.parameters?.[formInfo.FormParam.DIMENSION_KEY];
    const size = dimension === 2 ? '2x2' : '2x4';
    const formId = String(want.parameters?.[formInfo.FormParam.IDENTITY_KEY]);
    const data: Record<string, string> = {
      'desktopEnvelope': readDesktopEnvelope(this.context, size), 'desktopFormId': formId, 'desktopSize': size
    };
    hilog.info(0, 'A2UIDesktop', 'FORM_ADDED %{public}s',
      String(want.parameters?.[formInfo.FormParam.IDENTITY_KEY]));
    return formBindingData.createFormBindingData(data);
  }

  onRemoveForm(formId: string): void {
    removeDesktopReceipt(this.context, formId);
    hilog.info(0, 'A2UIDesktop', 'FORM_REMOVED %{public}s', formId);
  }

  onUpdateForm(formId: string): void { void this.restore(formId); }

  private async restore(formId: string): Promise<void> {
    try {
      const forms = await formProvider.getPublishedRunningFormInfos();
      const target = forms.find((item: formInfo.RunningFormInfo) => item.formId === formId);
      if (target === undefined || target.formName !== DESKTOP_FORM_NAME) {
        throw new Error('Cannot restore unknown form');
      }
      if (target.dimension !== 2 && target.dimension !== 3) { throw new Error('Unsupported dimension'); }
      const size = target.dimension === 2 ? '2x2' : '2x4';
      const content: string = readDesktopEnvelope(this.context, size);
      await formProvider.updateForm(formId,
        formBindingData.createFormBindingData({
          desktopEnvelope: content, desktopFormId: formId, desktopSize: size
        }));
    } catch (err) {
      hilog.error(0, 'A2UIDesktop', 'FORM_RESTORE_FAILED %{public}s %{public}s', formId, (err as Error).message);
    }
  }

  onFormEvent(formId: string, message: string): void {
    try {
      const record = JSON.parse(message) as Record<string, Object>;
      const event = (record['params'] ?? record) as Record<string, Object>;
      event['formId'] = formId;
      saveDesktopReceipt(this.context, formId, event);
      hilog.info(0, 'A2UIDesktop', '%{public}s', `A2UI_DESKTOP ${JSON.stringify(event)}`);
    } catch (err) {
      hilog.error(0, 'A2UIDesktop', 'INVALID_FORM_EVENT %{public}s %{public}s', formId, (err as Error).message);
    }
  }
}
