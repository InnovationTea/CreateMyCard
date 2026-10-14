/**
 * Builds the user message for a follow-up GenUI turn when a UI tree already exists.
 */
export function buildGenUIUserMessage(userPrompt: string, treeJson: string): string {
  return (
    `Current UI tree (JSON summary). Each key is a node id; value has type and children (child ids in order). Props are omitted to save tokens — patch nodes by id using the schema.\n` +
    `\`\`\`json\n${treeJson}\n\`\`\`\n\n` +
    `User request (incremental edit, or a completely new scene):\n${userPrompt}`
  );
}
