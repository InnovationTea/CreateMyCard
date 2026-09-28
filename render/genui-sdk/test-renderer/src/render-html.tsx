/**
 * render-html.tsx
 *
 * Reads JSONL file(s), parses each line with the parser, feeds commands
 * into UIGraph, renders the tree with the renderer's React components,
 * and writes the result as standalone HTML file(s).
 *
 * Modes:
 *   --input <file>    Render a single JSONL file (default: output/random-ui.jsonl)
 *   --output <file>   Output HTML path (single-file mode only)
 *   --all             Render all output/test-*.jsonl files to output/test-*.html
 *
 * Run:  npx tsx src/render-html.tsx --input output/test-Card.jsonl
 *       npx tsx src/render-html.tsx --all
 */

import { readFileSync, writeFileSync, mkdirSync, readdirSync } from "node:fs";
import { resolve, basename } from "node:path";
import type { ReactElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { parseCompactLine } from "@genui-sdk/parser";
import { UIGraph } from "@genui-sdk/graph";
import { renderTree, defaultRegistry } from "@genui-sdk/renderer";

// ── HTML wrapper ────────────────────────────────────────────────────────────

function wrapHtml(bodyHtml: string, title: string): string {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${title}</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
           font-size: 16px; line-height: 1.5; color: #1e293b;
           background: #f8fafc; }
    body { max-width: 480px; margin: 24px auto; padding: 16px;
           background: #ffffff; border-radius: 12px;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); }
    img { max-width: 100%; height: auto; }
  </style>
</head>
<body>
${bodyHtml}
</body>
</html>`;
}

// ── Render one JSONL file to HTML ───────────────────────────────────────────

function renderJsonlToHtml(inputPath: string, outputPath: string): boolean {
  const raw = readFileSync(inputPath, "utf-8");
  const lines = raw.split("\n").map((l) => l.trim()).filter((l) => l.length > 0);

  const graph = new UIGraph();
  let parsed = 0;
  let errors = 0;

  for (const line of lines) {
    const cmd = parseCompactLine(line);
    if (cmd) {
      graph.applyCommand(cmd);
      parsed++;
    } else {
      console.warn(`  ⚠️  Failed to parse: ${line.slice(0, 80)}…`);
      errors++;
    }
  }

  const root = graph.getRoot();
  if (!root) {
    console.warn(`  ⚠️  No root node in ${basename(inputPath)}, skipping.`);
    return false;
  }

  const reactTree = renderTree(graph, defaultRegistry);
  if (!reactTree) {
    console.warn(`  ⚠️  renderTree returned null for ${basename(inputPath)}, skipping.`);
    return false;
  }

  const bodyHtml = renderToStaticMarkup(reactTree as ReactElement);
  const title = `GenUI Test — ${basename(inputPath, ".jsonl")}`;
  const html = wrapHtml(bodyHtml, title);

  writeFileSync(outputPath, html, "utf-8");
  console.log(`  ✅ ${basename(inputPath).padEnd(28)} → ${basename(outputPath)} (${graph.size} nodes, ${html.length} bytes)`);
  return true;
}

// ── CLI ─────────────────────────────────────────────────────────────────────

function main() {
  const args = process.argv.slice(2);
  const outDir = resolve(__dirname, "../output");
  mkdirSync(outDir, { recursive: true });

  const allMode = args.includes("--all");

  if (allMode) {
    // Render all test-*.jsonl files
    const jsonlFiles = readdirSync(outDir)
      .filter((f) => f.startsWith("test-") && f.endsWith(".jsonl"))
      .sort();

    if (jsonlFiles.length === 0) {
      console.error("  ❌ No test-*.jsonl files found. Run generate-jsonl.ts first.");
      process.exit(1);
    }

    console.log(`  📂 Rendering ${jsonlFiles.length} test files from ${outDir}\n`);

    let success = 0;
    for (const file of jsonlFiles) {
      const inputPath = resolve(outDir, file);
      const htmlName = file.replace(".jsonl", ".html");
      const outputPath = resolve(outDir, htmlName);
      if (renderJsonlToHtml(inputPath, outputPath)) success++;
    }

    console.log(`\n  📊 Done: ${success}/${jsonlFiles.length} files rendered.`);
  } else {
    // Single file mode
    const inputIdx = args.indexOf("--input");
    const outputIdx = args.indexOf("--output");

    const inputPath =
      inputIdx >= 0 && args[inputIdx + 1]
        ? resolve(args[inputIdx + 1])
        : resolve(outDir, "random-ui.jsonl");
    const outputPath =
      outputIdx >= 0 && args[outputIdx + 1]
        ? resolve(args[outputIdx + 1])
        : resolve(outDir, "rendered.html");

    console.log(`  📄 Rendering ${basename(inputPath)}\n`);
    renderJsonlToHtml(inputPath, outputPath);
  }
}

main();
