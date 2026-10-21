import { common } from '@kit.AbilityKit';
import { fileIo } from '@kit.CoreFileKit';
import { util } from '@kit.ArkTS';
import { cryptoFramework } from '@kit.CryptoArchitectureKit';
import { parseA2UIMessages } from './A2UIProtocol';

export const DESKTOP_FORM_NAME: string = 'DebugCard';
export const DESKTOP_STORAGE_KEY: string = 'desktopEnvelope';

export interface DesktopEnvelope {
  runId: string;
  sampleId: string;
  revision: number;
  digest: string;
  size: string;
  dsl: string;
}

export interface DesktopCommand {
  commandId: string;
  operation: string;
  formId?: string;
  envelope?: DesktopEnvelope;
  expectedForms?: DesktopExpectedForm[];
  expectedRectPx?: DesktopExpectedRect;
  expectedDisplay?: number[];
}

export interface DesktopExpectedForm {
  formId: string;
  dimension: number;
}

export interface DesktopExpectedRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function desktopMarker(envelope: DesktopEnvelope): string {
  return `A2UI_DESKTOP:${envelope.runId}:${envelope.revision}:${envelope.digest}`;
}

export function readDesktopEnvelope(context: common.Context, size: string): string {
  if (size !== '2x2' && size !== '2x4') { throw new Error('Invalid desktop size'); }
  const path: string = `${context.getApplicationContext().filesDir}/desktop/current-${size}.json`;
  let content: string = '';
  if (fileIo.accessSync(path)) {
    content = fileIo.readTextSync(path);
  }
  return content;
}

function receiptPath(context: common.Context, formId: string): string {
  if (!/^-?[0-9]{1,30}$/.test(formId)) { throw new Error('Invalid form identity'); }
  return `${context.getApplicationContext().filesDir}/desktop/receipt-${formId}.json`;
}

export function readDesktopReceipt(context: common.Context, formId: string): Record<string, Object> {
  const path = receiptPath(context, formId);
  return fileIo.accessSync(path) ? JSON.parse(fileIo.readTextSync(path)) as Record<string, Object> : {};
}

export function removeDesktopReceipt(context: common.Context, formId: string): void {
  const path = receiptPath(context, formId);
  if (fileIo.accessSync(path)) { fileIo.unlinkSync(path); }
}

export function saveDesktopReceipt(context: common.Context, formId: string, event: Record<string, Object>): void {
  const current = JSON.parse(readDesktopEnvelope(context, String(event['size']))) as DesktopEnvelope;
  if (event['runId'] !== current.runId || event['revision'] !== current.revision ||
    event['digest'] !== current.digest) { return; }
  const previous = readDesktopReceipt(context, formId);
  if (previous['runId'] === current.runId && previous['revision'] === current.revision &&
    previous['state'] === 'FAILED') { return; }
  const path = receiptPath(context, formId);
  const temporary = `${path}.tmp`;
  const file = fileIo.openSync(temporary,
    fileIo.OpenMode.CREATE | fileIo.OpenMode.READ_WRITE | fileIo.OpenMode.TRUNC);
  try {
    fileIo.writeSync(file.fd, JSON.stringify(event));
    fileIo.fsyncSync(file.fd);
  } finally { fileIo.closeSync(file); }
  fileIo.renameSync(temporary, path);
}

export async function saveDesktopEnvelope(context: common.Context, envelope: DesktopEnvelope): Promise<void> {
  if (!/^[A-Za-z0-9._-]{1,100}$/.test(envelope.runId) || envelope.sampleId.length === 0 ||
    !Number.isSafeInteger(envelope.revision) || envelope.revision <= 0) {
    throw new Error('Invalid desktop envelope identity');
  }
  if (envelope.size !== '2x2' && envelope.size !== '2x4') {
    throw new Error('Invalid desktop dimension');
  }
  parseA2UIMessages(envelope.dsl);
  const md = cryptoFramework.createMd('SHA256');
  await md.update({ data: new util.TextEncoder().encodeInto(envelope.dsl) });
  const hashed = await md.digest();
  let digest: string = '';
  hashed.data.forEach((value: number) => { digest += value.toString(16).padStart(2, '0'); });
  if (digest !== envelope.digest) {
    throw new Error('Desktop DSL digest mismatch');
  }
  const previousText: string = readDesktopEnvelope(context, envelope.size);
  if (previousText.length > 0) {
    const previous = JSON.parse(previousText) as DesktopEnvelope;
    if (previous.runId === envelope.runId && previous.revision > envelope.revision) {
      throw new Error('Stale desktop revision');
    }
  }
  const root: string = `${context.getApplicationContext().filesDir}/desktop`;
  if (!fileIo.accessSync(root)) {
    fileIo.mkdirSync(root, true);
  }
  const temporary: string = `${root}/current-${envelope.size}.json.tmp`;
  const file = fileIo.openSync(temporary,
    fileIo.OpenMode.CREATE | fileIo.OpenMode.READ_WRITE | fileIo.OpenMode.TRUNC);
  try {
    fileIo.writeSync(file.fd, JSON.stringify(envelope));
    fileIo.fsyncSync(file.fd);
  } finally {
    fileIo.closeSync(file);
  }
  fileIo.renameSync(temporary, `${root}/current-${envelope.size}.json`);
}
