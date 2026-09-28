/**
 * Concatenates mini-prompt-assets/card-*.md into mini_card_examples.generated.ts
 * so buildMiniPrompt can embed Harmony card examples without runtime fs.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const assetsDir = path.join(__dirname, "../src/mini-prompt-assets");
const files = [
  "card-audio-list.md",
  "card-calender-almanac.md",
  "card-medal-leaderboard.md",
];

const parts = files.map((f) => fs.readFileSync(path.join(assetsDir, f), "utf8"));
const joined = parts.join("\n\n");
const outPath = path.join(assetsDir, "mini_card_examples.generated.ts");
const body = `/**
 * Auto-generated from card-*.md — run: \`node scripts/generate-mini-card-examples.mjs\`
 * (invoked from prompt package \`prebuild\`).
 */
export const MINI_HARMONY_CARD_EXAMPLES_PROMPT = ${JSON.stringify(joined)};
`;
fs.writeFileSync(outPath, body, "utf8");
console.log("wrote", outPath);
