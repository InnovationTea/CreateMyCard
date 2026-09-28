/**
 * Maps mini compact graph commands → full **v0.9** A2UI NDJSON messages
 * consumable by `genui-sdk/parser` `tryNormalizeV09Protocol` (round-trip for graph keys)
 * and by hosts that stream `version` + `createSurface` / `updateComponents` / `updateDataModel` / `deleteSurface`.
 *
 * Input shape (from {@link parseCompactLine}):
 * - Protocol: `{ __createSurface }`, `{ __updateDataModel }`, `{ __deleteSurface }` — use {@link mapGraphCommandToV09A2UI}
 * - Node: `{ [id]: { type, props?, children? } }` — use {@link compactGraphCommandToV09} or {@link mapGraphCommandToV09A2UI}
 *
 * Patch-only lines (`{ [id]: { props?, children? } }` without `type`) cannot be expressed
 * as a standalone v0.9 component → {@link compactGraphCommandToV09} returns `null`.
 */

import {
  CREATE_SURFACE_KEY,
  DELETE_SURFACE_KEY,
  UPDATE_DATA_MODEL_KEY,
} from "../../parser/src/protocol-v09.js";

export const PROTOCOL_VERSION_V09 = "v0.9" as const;

/** Spike / puncture: fixed surface id (see project convention). */
export const SPIKE_SURFACE_ID = "test";

export type V09UpdateComponentsMessage = {
  version: typeof PROTOCOL_VERSION_V09;
  updateComponents: {
    surfaceId: string;
    components: Record<string, unknown>[];
  };
};

/** v0.9 `createSurface` with optional catalog/theme (from minimal GenUI `@"…"` lines). */
export type V09CreateSurfaceMessage = {
  version: typeof PROTOCOL_VERSION_V09;
  createSurface: {
    surfaceId: string;
    catalogId: string;
    theme?: Record<string, unknown>;
    sendDataModel?: boolean;
  };
};

export type V09UpdateDataModelMessage = {
  version: typeof PROTOCOL_VERSION_V09;
  updateDataModel: {
    surfaceId: string;
    path: string;
    value?: unknown;
  };
};

export type V09DeleteSurfaceMessage = {
  version: typeof PROTOCOL_VERSION_V09;
  deleteSurface: { surfaceId: string };
};

/** One complete v0.9 A2UI object line (single kind per object). */
export type V09A2UIMessage =
  | V09UpdateComponentsMessage
  | V09CreateSurfaceMessage
  | V09UpdateDataModelMessage
  | V09DeleteSurfaceMessage;

const CARD_TOP = new Set([
  "title",
  "description",
  "layout",
  "gap",
  "fill",
  "justifyContent",
  "alignItems",
]);

const ROW_COL_TOP = new Set(["space"]);

const TEXT_TOP = new Set(["content"]);

const IMAGE_TOP = new Set(["src"]);

const BUTTON_TOP = new Set(["label", "enabled"]);

/**
 * A2UI component **`action.functionCall`** for **`openUrl`**
 * (see `skills/a2ui/reference/protocol/extended-interactions.md`).
 * Merge as `{ action: buildActionOpenUrl(url) }` on the component object.
 */
export function buildActionOpenUrl(url: string): Record<string, unknown> {
  return {
    functionCall: {
      call: "openUrl",
      args: { url },
    },
  };
}

/** Mini short names from `mini-prompt-assets/ui_schema` → `Extended.*` component strings. */
export function miniTypeToExtended(shortType: string): string | null {
  const map: Record<string, string> = {
    Card: "Extended.Card",
    Row: "Extended.Row",
    Column: "Extended.Column",
    Text: "Extended.Text",
    Image: "Extended.Image",
    Button: "Extended.Button",
    Radio: "Extended.Radio",
    Select: "Extended.Select",
    Checkbox: "Extended.Checkbox",
    Input: "Extended.TextInput",
  };
  return map[shortType] ?? null;
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function omitStylesIfEmpty(styles: Record<string, unknown>): Record<string, unknown> | undefined {
  return Object.keys(styles).length > 0 ? styles : undefined;
}

function partitionTopAndStyles(
  flat: Record<string, unknown>,
  topKeys: Set<string>,
): { top: Record<string, unknown>; styles: Record<string, unknown> } {
  const top: Record<string, unknown> = {};
  const styles: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(flat)) {
    if (topKeys.has(k)) top[k] = v;
    else styles[k] = v;
  }
  return { top, styles };
}

function mergeComponent(
  id: string,
  component: string,
  top: Record<string, unknown>,
  styles: Record<string, unknown>,
  children: string[] | undefined,
  /** Top-level v0.9 fields outside `styles` (e.g. `action`). */
  extras?: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {
    id,
    component,
    ...top,
  };
  const s = omitStylesIfEmpty(styles);
  if (s !== undefined) out.styles = s;
  if (children !== undefined) out.children = children;
  if (extras !== undefined) {
    for (const [k, v] of Object.entries(extras)) {
      out[k] = v;
    }
  }
  return out;
}

function mapInputType(mini: unknown): "normal" | "email" | "password" | "number" {
  if (mini === "email") return "email";
  if (mini === "password") return "password";
  if (mini === "number") return "number";
  return "normal";
}

/**
 * Converts one mini node (`shortType` + flat `props` + optional `children`) into one
 * v0.9 `components[]` entry (`id`, `component`, optional `children`, top-level + `styles`).
 */
export function mapMiniNodeToV09Component(
  id: string,
  shortType: string,
  props: Record<string, unknown>,
  children: string[] | undefined,
): Record<string, unknown> | null {
  const extended = miniTypeToExtended(shortType);
  if (!extended) return null;

  switch (shortType) {
    case "Card": {
      const { openUrl, ...cardRest } = props;
      const { top, styles } = partitionTopAndStyles(cardRest, CARD_TOP);
      const extras =
        typeof openUrl === "string" && openUrl.length > 0
          ? { action: buildActionOpenUrl(openUrl) }
          : undefined;
      return mergeComponent(id, extended, top, styles, children, extras);
    }
    case "Row":
    case "Column": {
      const { top, styles } = partitionTopAndStyles(props, ROW_COL_TOP);
      return mergeComponent(id, extended, top, styles, children);
    }
    case "Text": {
      const { openUrl, ...textRest } = props;
      const { top, styles } = partitionTopAndStyles(textRest, TEXT_TOP);
      const extras =
        typeof openUrl === "string" && openUrl.length > 0
          ? { action: buildActionOpenUrl(openUrl) }
          : undefined;
      return mergeComponent(id, extended, top, styles, children, extras);
    }
    case "Image": {
      const { top, styles } = partitionTopAndStyles(props, IMAGE_TOP);
      return mergeComponent(id, extended, top, styles, children);
    }
    case "Button": {
      const { openUrl, ...btnRest } = props;
      const { top, styles } = partitionTopAndStyles(btnRest, BUTTON_TOP);
      const extras =
        typeof openUrl === "string" && openUrl.length > 0
          ? { action: buildActionOpenUrl(openUrl) }
          : undefined;
      return mergeComponent(id, extended, top, styles, children, extras);
    }
    case "Radio": {
      const name = props.name;
      const options = props.options;
      const strOptions = Array.isArray(options)
        ? options.filter((x): x is string => typeof x === "string")
        : [];
      const top: Record<string, unknown> = {
        group: typeof name === "string" ? name : "",
        value: strOptions[0] ?? "",
        checked: false,
        indicationType: "dot",
      };
      const { label: _l, name: _n, options: _o, ...rest } = props;
      const styles = { ...rest };
      return mergeComponent(id, extended, top, styles, children);
    }
    case "Select": {
      const raw = props.options;
      const strOptions = Array.isArray(raw)
        ? raw.filter((x): x is string => typeof x === "string")
        : [];
      const extendedOptions = strOptions.map((value) => ({ value, icon: "" }));
      const top: Record<string, unknown> = {
        options: extendedOptions,
        selected: 0,
        value: strOptions[0] ?? "",
      };
      const { label, name, options: _opts, placeholder, ...rest } = props;
      const styles: Record<string, unknown> = { ...rest };
      if (typeof label === "string") styles.label = label;
      if (typeof name === "string") styles.name = name;
      if (typeof placeholder === "string") styles.placeholder = placeholder;
      return mergeComponent(id, extended, top, styles, children);
    }
    case "Checkbox": {
      const name = props.name;
      const checked = props.checked;
      const top: Record<string, unknown> = {
        group: typeof name === "string" ? name : "",
        select: typeof checked === "boolean" ? checked : false,
      };
      const { label: _l, name: _n, checked: _c, ...rest } = props;
      return mergeComponent(id, extended, top, rest, children);
    }
    case "Input": {
      const placeholder = props.placeholder;
      const miniType = props.type;
      const name = props.name;
      const top: Record<string, unknown> = {
        text: "",
        placeholder: typeof placeholder === "string" ? placeholder : "",
        enabled: true,
        type: mapInputType(miniType),
      };
      const { label, name: _nm, type: _t, placeholder: _p, ...rest } = props;
      const styles: Record<string, unknown> = { ...rest };
      if (typeof label === "string") styles.label = label;
      if (typeof name === "string") styles.name = name;
      return mergeComponent(id, extended, top, styles, children);
    }
    default:
      return null;
  }
}

/**
 * Wraps a single compact graph command as a full v0.9 batch `updateComponents` message.
 *
 * @returns `null` if the command is not a typed node (no `type`) or type is unknown.
 */
export function compactGraphCommandToV09(
  compact: Record<string, unknown>,
  options?: { surfaceId?: string },
): V09UpdateComponentsMessage | null {
  const keys = Object.keys(compact);
  if (keys.length !== 1) return null;
  const id = keys[0]!;
  const inner = compact[id];
  if (!isPlainObject(inner)) return null;

  const shortType = inner.type;
  if (typeof shortType !== "string") return null;

  const props = isPlainObject(inner.props) ? inner.props : {};
  const ch = inner.children;
  const children =
    Array.isArray(ch) && ch.every((x) => typeof x === "string") ? (ch as string[]) : undefined;

  const component = mapMiniNodeToV09Component(id, shortType, props, children);
  if (!component) return null;

  return {
    version: PROTOCOL_VERSION_V09,
    updateComponents: {
      surfaceId: options?.surfaceId ?? SPIKE_SURFACE_ID,
      components: [component],
    },
  };
}

const DEFAULT_CATALOG_ID = "https://xxx/specification/ohos/extended_catalog.json";

/**
 * Map one graph command (from {@link parseCompactLine}) to a full **v0.9** A2UI JSON object
 * (one of `createSurface` | `updateComponents` | `updateDataModel` | `deleteSurface`).
 */
export function mapGraphCommandToV09A2UI(
  compact: Record<string, unknown>,
  options?: { surfaceId?: string },
): V09A2UIMessage | null {
  const keys = Object.keys(compact);
  if (keys.length !== 1) return null;
  const k = keys[0]!;

  if (k === CREATE_SURFACE_KEY) {
    const inner = compact[k];
    if (!isPlainObject(inner)) return null;
    const surfaceId = inner.surfaceId;
    if (typeof surfaceId !== "string") return null;
    const catalogId =
      typeof inner.catalogId === "string" ? inner.catalogId : DEFAULT_CATALOG_ID;
    const out: V09CreateSurfaceMessage = {
      version: PROTOCOL_VERSION_V09,
      createSurface: { surfaceId, catalogId },
    };
    if (isPlainObject(inner.theme)) {
      out.createSurface.theme = inner.theme;
    }
    if (typeof inner.sendDataModel === "boolean") {
      out.createSurface.sendDataModel = inner.sendDataModel;
    }
    return out;
  }

  if (k === UPDATE_DATA_MODEL_KEY) {
    const inner = compact[k];
    if (!isPlainObject(inner)) return null;
    const surfaceId = inner.surfaceId;
    const path = inner.path;
    if (typeof surfaceId !== "string" || typeof path !== "string") return null;
    const out: V09UpdateDataModelMessage = {
      version: PROTOCOL_VERSION_V09,
      updateDataModel: { surfaceId, path },
    };
    if (Object.prototype.hasOwnProperty.call(inner, "value")) {
      out.updateDataModel.value = inner.value;
    }
    return out;
  }

  if (k === DELETE_SURFACE_KEY) {
    const inner = compact[k];
    if (!isPlainObject(inner)) return null;
    const surfaceId = inner.surfaceId;
    if (typeof surfaceId !== "string") return null;
    return {
      version: PROTOCOL_VERSION_V09,
      deleteSurface: { surfaceId },
    };
  }

  return compactGraphCommandToV09(compact, { surfaceId: options?.surfaceId });
}

/**
 * Convenience: v0.9 `createSurface` message (spike `surfaceId` and default catalog by default).
 * Not merged with `updateComponents` in one object — protocol forbids both in one message.
 */
export function v09CreateSurfaceMessage(options?: {
  surfaceId?: string;
  catalogId?: string;
  theme?: Record<string, unknown>;
  sendDataModel?: boolean;
}): V09CreateSurfaceMessage {
  const createSurface: V09CreateSurfaceMessage["createSurface"] = {
    surfaceId: options?.surfaceId ?? SPIKE_SURFACE_ID,
    catalogId: options?.catalogId ?? DEFAULT_CATALOG_ID,
  };
  if (isPlainObject(options?.theme)) {
    createSurface.theme = options.theme;
  }
  if (typeof options?.sendDataModel === "boolean") {
    createSurface.sendDataModel = options.sendDataModel;
  }
  return { version: PROTOCOL_VERSION_V09, createSurface };
}
