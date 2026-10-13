// Read-only import of the documented few-shots and their resource library.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const parent = path.dirname(root);
const defaultReference = fs.existsSync(path.join(parent, "widget_service")) ? parent : path.join(root, ".git/fusion-reference");
const reference = path.resolve(process.argv[2] ?? defaultReference);
const sourceDir = "widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/generated";
const commit = execFileSync("git", ["-C", reference, "rev-parse", "HEAD"], { encoding: "utf8" }).trim();
const examples = [];
for (const size of ["2x2", "2x4"]) {
  const markdown = fs.readFileSync(path.join(reference, sourceDir, `FEWSHOT_${size}.md`), "utf8");
  for (const section of markdown.split(/^## /m).slice(1)) {
    const match = section.match(/```genui\s*\n([\s\S]*?)\n```/);
    if (!match) continue;
    const name = section.split("\n")[0].trim();
    // These two upstream examples retain 296-vp body rows from the 320×160 canvas.
    // Preserve their source verbatim; expose the compatibility canvas rather than shrinking text.
    const legacy = /2x4-V(?:02|05)/.test(name);
    examples.push({ name, size, width: size === "2x2" ? 150 : legacy ? 320 : 300, height: legacy ? 160 : 150,
      note: legacy ? "原示例含 296vp 内容区，按 320×160 兼容画布预览；分支文档的常规宽卡尺寸为 300×150。" : /2x4-V13/.test(name) ? "上游缺少 project_fill.svg，预览使用本地补充的文件夹图标。" : "",
      source: match[1].trim() });
  }
}
if (examples.length !== 30) throw new Error(`预期 30 个示例，实际 ${examples.length}；请复核分支变更。`);
fs.mkdirSync(path.join(root, "platform/fixtures"), { recursive: true });
fs.writeFileSync(path.join(root, "platform/fixtures/fusion-examples.json"), JSON.stringify({ repository: "https://github.com/InnovationTea/CreateMyCard", branch: "Br_feature_fusion", commit, sourceDir, examples }, null, 2) + "\n");
fs.mkdirSync(path.join(root, "platform/public/resources/base"), { recursive: true });
fs.cpSync(path.join(reference, "resources/base/media"), path.join(root, "platform/public/resources/base/media"), { recursive: true });
// This resource is referenced by V13 but absent from the source branch. Local fallback, not an upstream asset.
const fallback = path.join(root, "platform/public/resources/base/media/project_fill.svg");
if (!fs.existsSync(path.join(reference, "resources/base/media/project_fill.svg"))) {
  fs.writeFileSync(fallback, '<!-- Local fallback for missing upstream project_fill.svg -->\n<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="#000" d="M3 4h6l2 2h10a1 1 0 0 1 1 1v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1Z"/></svg>\n');
}
console.log(`已导入 ${examples.length} 个原始示例及资源，来源提交 ${commit}。`);
