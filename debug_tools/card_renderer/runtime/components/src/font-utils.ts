/**
 * Host registers webfonts via @font-face; the model may pass short names.
 * Default UI stack: HarmonyOS Sans SC + HarmonyOS Sans (see platform `public/fonts/harmonyos/`).
 */
const HARMONYOS_STACK =
  '"HarmonyOS Sans SC", "HarmonyOS Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif';

function stripOuterQuotes(s: string): string {
  const t = s.trim();
  if (t.length >= 2) {
    const a = t[0];
    const b = t[t.length - 1];
    if ((a === '"' && b === '"') || (a === "'" && b === "'")) {
      return t.slice(1, -1).trim();
    }
  }
  return t;
}

export function resolveFontFamily(fontFamily: string | undefined): string | undefined {
  if (fontFamily === undefined) return undefined;
  const t = stripOuterQuotes(fontFamily);
  if (t === "Concert One") {
    return '"Concert One", system-ui, sans-serif';
  }
  if (
    t === "HarmonyOS Sans" ||
    t === "HarmonyOS_Sans" ||
    t === "HarmonyOS Sans SC" ||
    t === "HarmonyOS_Sans_SC"
  ) {
    return HARMONYOS_STACK;
  }
  return fontFamily;
}

/** Default stack for preview / prompts when no explicit `fontFamily` is set. */
export const DEFAULT_UI_FONT_STACK = HARMONYOS_STACK;
