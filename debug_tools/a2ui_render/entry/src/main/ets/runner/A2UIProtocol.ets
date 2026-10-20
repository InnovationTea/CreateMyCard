export interface RenderRequest {
  runId: string;
  sampleFile: string;
  width: number;
  height: number;
  useRawResource: boolean;
}

export const DEFAULT_WIDTH: number = 150;
export const DEFAULT_HEIGHT: number = 150;

export function isSafeSampleFile(sampleFile: string): boolean {
  return /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(sampleFile) && sampleFile !== '.' && sampleFile !== '..';
}

export function normalizeDimension(value: number | undefined, defaultValue: number): number {
  if (value === undefined) {
    return defaultValue;
  }
  return value;
}

export function isValidContainerSize(width: number, height: number,
  viewportWidth: number, viewportHeight: number): boolean {
  return Number.isInteger(width) && Number.isInteger(height) && width > 0 && height > 0 &&
    width <= viewportWidth && height <= viewportHeight;
}

export function parseA2UIMessages(content: string): object[] {
  const trimmed: string = content.trim();
  if (trimmed.length === 0) {
    throw new Error('A2UI sample is empty');
  }

  try {
    const parsed: Object = JSON.parse(trimmed);
    if (Array.isArray(parsed)) {
      if (parsed.length === 0) {
        throw new Error('A2UI message array is empty');
      }
      return parsed as object[];
    }
    if (typeof parsed === 'object' && parsed !== null) {
      return [parsed];
    }
    throw new Error('A2UI JSON root must be an object or array');
  } catch (wholeDocumentError) {
    const messages: object[] = [];
    const lines: string[] = trimmed.split('\n');
    try {
      lines.forEach((line: string) => {
        const jsonLine: string = line.trim();
        if (jsonLine.length > 0) {
          const message: Object = JSON.parse(jsonLine);
          if (typeof message !== 'object' || message === null || Array.isArray(message)) {
            throw new Error('Each JSONL line must contain one message object');
          }
          messages.push(message);
        }
      });
    } catch (jsonlError) {
      throw new Error(`Invalid A2UI JSON/JSONL: ${(jsonlError as Error).message}`);
    }
    if (messages.length === 0) {
      throw new Error(`Invalid A2UI JSON/JSONL: ${(wholeDocumentError as Error).message}`);
    }
    return messages;
  }
}

interface A2UIMessageShape {
  createSurface?: Object;
  updateComponents?: Object;
  updateDataModel?: Object;
}

// genui_form resolves bindings while updateComponents is handled. A canonical
// JSONL sample may place its initial data model immediately after the component
// tree, so stage that initial model first to avoid transient "path does not
// exist" errors. Only the messages before a second component update are moved;
// later incremental updates retain their original order.
export function stageInitialDataModel(messages: object[]): object[] {
  let firstComponents: number = -1;
  let initialBlockEnd: number = messages.length;
  for (let index: number = 0; index < messages.length; index++) {
    const message: A2UIMessageShape = messages[index] as A2UIMessageShape;
    if (message.updateComponents !== undefined) {
      if (firstComponents < 0) {
        firstComponents = index;
      } else {
        initialBlockEnd = index;
        break;
      }
    }
  }
  if (firstComponents < 0) {
    return messages;
  }

  const beforeComponents: object[] = messages.slice(0, firstComponents);
  const initialData: object[] = [];
  const initialComponentsAndOther: object[] = [];
  for (let index: number = firstComponents; index < initialBlockEnd; index++) {
    const message: A2UIMessageShape = messages[index] as A2UIMessageShape;
    if (message.updateDataModel !== undefined) {
      initialData.push(messages[index]);
    } else {
      initialComponentsAndOther.push(messages[index]);
    }
  }
  return beforeComponents.concat(initialData, initialComponentsAndOther, messages.slice(initialBlockEnd));
}
