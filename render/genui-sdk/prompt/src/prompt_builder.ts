import { ROLE_PROMPT } from "./prompt-assets/role";
import { DESIGN_GUIDE } from "./prompt-assets/design_guide";
import {
  STYLE_BY_ID,
  type StyleId,
} from "./prompt-assets/styles.generated";
import { A2UI_SKILL_PROMPT } from "./prompt-assets/a2ui_skill.generated";
import { ROLE_PROMPT as MINI_ROLE_PROMPT } from "./mini-prompt-assets/role";
import { DESIGN_GUIDE as MINI_DESIGN_GUIDE } from "./mini-prompt-assets/design_guide";
import { UI_SCHEMA_PROMPT as MINI_UI_SCHEMA_PROMPT } from "./mini-prompt-assets/ui_schema";
import { OUTPUT_FORMAT_PROMPT as MINI_OUTPUT_FORMAT_PROMPT } from "./mini-prompt-assets/output_format";
import { HARMONY_STYLE_PROMPT } from "./mini-prompt-assets/harmony_style";
import { MINI_HARMONY_CARD_EXAMPLES_PROMPT } from "./mini-prompt-assets/mini_card_examples.generated";

/**
 * Assembles prompt assets into a single system prompt for the model.
 *
 * @param styleId - Style id key from {@link STYLE_BY_ID}.
 *                  Pass `undefined` (or omit) to use no extra style guide (default look).
 */
export function buildPrompt(styleId?: StyleId): string {
  const styleGuide = styleId ? STYLE_BY_ID[styleId] : undefined;
  return [
    ROLE_PROMPT,
    DESIGN_GUIDE,
    A2UI_SKILL_PROMPT,
    // UI_SCHEMA_PROMPT,
    // OUTPUT_FORMAT_PROMPT,
    // ...(styleGuide ? [styleGuide] : []),
  ].join("\n\n");
}

/**
 * Compact JSONL / mini component schema (Card, Row, Text, …) + output rules +
 * embedded Harmony card examples (from `mini-prompt-assets/card-*.md`, see `generate-mini-card-examples.mjs`).
 * Optional {@link STYLE_BY_ID} style guide is appended when `styleId` is set.
 */
export function buildMiniPrompt(styleId?: StyleId): string {
  const styleGuide = styleId ? STYLE_BY_ID[styleId] : undefined;
  return [
    MINI_ROLE_PROMPT,
    MINI_DESIGN_GUIDE,
    HARMONY_STYLE_PROMPT,
    MINI_UI_SCHEMA_PROMPT,
    MINI_OUTPUT_FORMAT_PROMPT,
    MINI_HARMONY_CARD_EXAMPLES_PROMPT,
    ...(styleGuide ? [styleGuide] : []),
  ].join("\n\n");
}
