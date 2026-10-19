#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const runnerRoot = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(runnerRoot, "../../..");
const platformRoot = path.join(repositoryRoot, "render/platform");

function usage(exitCode = 0) {
  const output = exitCode === 0 ? process.stdout : process.stderr;
  output.write(
    "用法：\n" +
    "  node build_gallery.mjs <批次目录> [--cards <CardSpec目录>] [--output <HTML路径>] [--python <解释器>]\n\n" +
    "批次目录没有 summary.json 时会自动导出已生成的部分结果，此时必须显式指定 --cards。\n\n" +
    "示例：\n" +
    "  node build_gallery.mjs output/cardspec24_repair10\n" +
    "  node build_gallery.mjs output/cardspec24_repair10 --cards cardSpec24 --output output/cardspec24_repair10/gallery.html\n" +
    "  node build_gallery.mjs ../runner-output/partial-run --cards 20261016_online_updated\n",
  );
  process.exit(exitCode);
}

function parseArguments(argv) {
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--help" || argument === "-h") usage();
    if (argument === "--cards" || argument === "--output" || argument === "--python") {
      const value = argv[index + 1];
      if (!value || value.startsWith("--")) throw new Error(`${argument} 缺少参数值`);
      options[argument.slice(2)] = value;
      index += 1;
      continue;
    }
    if (!options.runDirectory) {
      options.runDirectory = argument;
      continue;
    }
    throw new Error(`未知参数：${argument}`);
  }
  if (!options.runDirectory) throw new Error("必须指定批次目录");
  return options;
}

function resolveFromRunner(value) {
  return path.isAbsolute(value) ? value : path.resolve(runnerRoot, value);
}

function inferCardsDirectory(runDirectory) {
  const summaryPath = path.join(runDirectory, "summary.json");
  if (existsSync(summaryPath)) {
    const summary = JSON.parse(readFileSync(summaryPath, "utf8"));
    const results = Array.isArray(summary.results) ? summary.results : [];
    if (results.length && results.every(result => result?.size === "2x4")) {
      return path.join(runnerRoot, "cardSpec24");
    }
  }
  return path.join(runnerRoot, "cardSpec");
}

function main() {
  const options = parseArguments(process.argv.slice(2));
  const runDirectory = resolveFromRunner(options.runDirectory);
  const summaryPath = path.join(runDirectory, "summary.json");
  const hasSummary = existsSync(summaryPath);
  if (!hasSummary && !options.cards) {
    throw new Error("批次目录缺少 summary.json；导出部分结果时必须通过 --cards 指定原始任务目录");
  }
  const cardsDirectory = options.cards
    ? resolveFromRunner(options.cards)
    : inferCardsDirectory(runDirectory);
  const outputPath = options.output
    ? resolveFromRunner(options.output)
    : path.join(runDirectory, "gallery.html");
  if (!existsSync(cardsDirectory)) throw new Error(`CardSpec 目录不存在：${cardsDirectory}`);

  const tsxCli = path.join(repositoryRoot, "render/genui-sdk/node_modules/tsx/dist/cli.mjs");
  const tsconfig = path.join(repositoryRoot, "render/genui-sdk/tsconfig.base.json");
  const exporter = path.join(platformRoot, "scripts/export-runner-results.ts");
  if (!existsSync(tsxCli)) {
    throw new Error("缺少 Renderer Node 依赖，请先在 render/genui-sdk 安装依赖");
  }

  const exporterArguments = [
    tsxCli,
    "--tsconfig",
    tsconfig,
    exporter,
    "--input",
    runDirectory,
    "--cards",
    cardsDirectory,
    "--output",
    outputPath,
  ];
  if (!hasSummary) exporterArguments.push("--partial");
  if (options.python) exporterArguments.push("--python", options.python);
  const completed = spawnSync(
    process.execPath,
    exporterArguments,
    { cwd: platformRoot, encoding: "utf8", stdio: "inherit" },
  );
  if (completed.error) throw completed.error;
  if (completed.status !== 0) process.exit(completed.status ?? 1);
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
}
