const MAX_ORIGINAL_PROMPT_IN_CONTINUATION = 60_000;

/**
 * Continuation user message for **mini** minimal GenUI when child ids are listed in
 * parents but not yet defined — mirrors the A2UI pending-child prompt in spirit.
 */
export function buildMiniPendingChildrenContinuationPrompt(
  originalUserPrompt: string,
  pendingChildIds: string[],
  /** Active surface id for updateComponent lines (no @ prefix). */
  surfaceId: string = "main",
): string {
  const ids = pendingChildIds.join(", ");
  let orig = originalUserPrompt.trim();
  if (orig.length > MAX_ORIGINAL_PROMPT_IN_CONTINUATION) {
    orig =
      orig.slice(0, MAX_ORIGINAL_PROMPT_IN_CONTINUATION) +
      "\n\n[… original user request truncated for size …]";
  }
  const surf = (surfaceId ?? "main").trim() || "main";
  return (
    `## Original user request (stay consistent — same items, copy, image URLs, tags, and layout; do not invent new list rows or unrelated content for the missing nodes)\n\n` +
    `${orig}\n\n` +
    `## Continuation only\n\n` +
    `Active **surfaceId** (use as first segment of every **updateComponent** line): \`"${surf}"\`.\n\n` +
    `These **componentId**s appear in a parent \`children\` array but have no **updateComponent** line yet: ${ids}.\n` +
    `Emit **only** valid minimal GenUI lines: each line is one **updateComponent** tuple \`{"${surf}", "<componentId>", "<Type>", { ...props }, [ children ]? }\` defining **one** of the pending ids (exact strings above).\n` +
    `- **Do not** emit a new \`createSurface\` (\`@...\`) unless you intend a new surface. **Do not** redefine components that already exist unless that id is in the pending list.\n` +
    `- Only emit lines for **missing** component ids (and nested ids required to complete them).\n` +
    `- In every \`children\` array you output, **each child id at most once**.\n` +
    `- **Do not** add extra sibling rows beyond what is needed to define the pending ids.`
  );
}
