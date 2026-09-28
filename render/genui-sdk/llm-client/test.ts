import * as readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import { config } from "dotenv";
import { resolve } from "node:path";
import { streamGenUI } from "@genui-sdk/llm-client";

// Same root .env as platform (see ../../.env)
config({ path: resolve(__dirname, "../../.env") });

const apiKey = process.env.VITE_OPENROUTER_API_KEY ?? "";

async function main() {
  if (!apiKey) {
    console.error("[错误] 缺少 VITE_OPENROUTER_API_KEY — 请在仓库根目录 .env 中配置");
    process.exit(1);
  }

  let userPrompt = process.argv[2];

  if (!userPrompt) {
    const rl = readline.createInterface({ input, output });
    userPrompt = await rl.question("请输入您的需求: ");
    rl.close();
  }

  console.log("\n--- 模型输出 (流式) ---\n");

  try {
    for await (const token of streamGenUI(userPrompt, { apiKey })) {
      process.stdout.write(token);
    }
  } catch (err) {
    console.error("\n[错误]", err instanceof Error ? err.message : err);
    process.exit(1);
  }

  console.log("\n\n--- 输出完成 ---");
}

main();
