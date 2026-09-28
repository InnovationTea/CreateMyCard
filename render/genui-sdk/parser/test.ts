import * as readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import { config } from "dotenv";
import { resolve } from "node:path";
import { streamGenUI } from "@genui-sdk/llm-client";
import { JsonlStreamParser } from "@genui-sdk/parser";

config({ path: resolve(__dirname, "../../.env") });

const apiKey = process.env.VITE_OPENROUTER_API_KEY ?? "";

async function main() {
  if (!apiKey) {
    console.error("[错误] 缺少 VITE_OPENROUTER_API_KEY — 请在仓库根目录 .env 中配置");
    process.exit(1);
  }

  const argv = process.argv.slice(2);
  const showRaw =
    argv.includes("--raw") || argv.includes("-r") || process.env.DEBUG_GENUI_RAW === "1";
  const promptArgs = argv.filter((a) => a !== "--raw" && a !== "-r");
  let userPrompt = promptArgs.join(" ").trim();

  if (!userPrompt) {
    const rl = readline.createInterface({ input, output });
    userPrompt = await rl.question("请输入您的需求: ");
    rl.close();
  }

  console.log("\n--- 解析后的指令（已归一化为经典 JSON，与 graph 一致）---\n");

  let commandCount = 0;
  let rawStream = "";

  const parser = new JsonlStreamParser<Record<string, unknown>>({
    onMessage(obj, rawSegment) {
      commandCount++;
      console.log(`[指令 ${commandCount}]`);
      console.log(rawSegment);
      console.log(JSON.stringify(obj, null, 2));
      console.log();
    },
    onParseError(raw, err) {
      console.warn(`[解析错误] ${String(err)}\n  原始内容: ${raw}\n`);
    },
    onBraceMismatch() {
      console.warn("[警告] 括号不匹配，跳过异常片段");
    },
  });

  try {
    for await (const token of streamGenUI(userPrompt, { apiKey })) {
      rawStream += token;
      parser.push(token);
    }
    parser.end();
  } catch (err) {
    console.error("[错误]", err instanceof Error ? err.message : err);
    process.exit(1);
  }

  const pending = parser.getPending().trim();
  if (pending) {
    console.warn(`[未完成片段] ${pending}\n`);
  }

  console.log(`--- 共解析出 ${commandCount} 条指令 ---`);

  if (showRaw) {
    console.log("\n========== 模型原始输出（用于判断是否 compact）==========\n");
    console.log(rawStream);
    console.log(
      "\n--- 如何辨认 ---\n" +
        "• **Compact**：形如 `{\"root\", \"Card\", {...}, [...]}` —— id 与 type 用 **逗号** 分隔，无 `\"type\"` / `\"props\"` 键名。\n" +
        "• **经典 JSON**：形如 `{\"root\": {\"type\": \"Card\", \"props\": {...}}}` —— 使用 **冒号** 与嵌套对象。\n",
    );
  }
}

main();
