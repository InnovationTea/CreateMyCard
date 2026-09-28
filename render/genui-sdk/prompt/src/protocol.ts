/** Which system prompt + output conventions the GenUI chat route uses. */
export type GenUIProtocol = "a2ui" | "mini";

export const DEFAULT_GENUI_PROTOCOL: GenUIProtocol = "a2ui";

export function coerceGenUIProtocol(v: unknown): GenUIProtocol {
  return v === "mini" ? "mini" : "a2ui";
}
