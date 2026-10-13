/** Client → server wire shape for a triggered `action.event` (after context resolution). See `skills/a2ui/reference/protocol/extended-interactions.md`. */
export type ActionEventMessage = {
  name: string;
  surfaceId: string;
  sourceComponentId: string;
  /** ISO 8601 timestamp at dispatch time. */
  timestamp: string;
  /** Fully resolved: literals, path snapshots, getSelectedValues, nested objects. */
  context: Record<string, unknown>;
};

/** Host-implemented side effects for **`action.functionCall`** (e.g. `openUrl`) and **`action.event`** (resolved → agent). */
export interface InteractionHost {
  /** Renderer hosts can inspect native intents without calling an LLM or navigating. */
  functionCall?(args: { call: string; args: unknown; componentId: string }): void | Promise<void>;
  /** If set, `action.functionCall.call === "openUrl"` uses `functionCall.args.url` (e.g. new tab). */
  openUrl?(args: { url: string }): void | Promise<void>;
  /**
   * Called for **every** `action.event` after **`context`** is fully resolved, with the **wire** fields
   * (`name`, `surfaceId`, `sourceComponentId`, `timestamp`, `context`).
   */
  submitForm?(args: ActionEventMessage): void | Promise<void>;
}

export interface EventContext {
  componentId: string;
  /** A2UI `surfaceId` for this node (wire `surfaceId` field). */
  surfaceId: string;
  eventData?: { x: number; y: number };
  /**
   * When set, `functionCall.args` path leaves are resolved with the data model at click time;
   * also used to resolve `{"path":"…"}` in `action.event.context`.
   */
  getDataModelLeaf?: (path: string) => unknown;
  /**
   * Resolves `{"call":"getSelectedValues","args":{"groupID":"…"}}` in `action.event.context`
   * (same `group` as `Extended.Radio` on this surface).
   */
  getSelectedGroupValue?: (groupID: string) => string;
}
