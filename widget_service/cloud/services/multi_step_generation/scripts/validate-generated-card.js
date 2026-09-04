#!/usr/bin/env node

/**
 * Validate one generated Design System JSX card without reading 2x2-0815-good-cases.jsx
 * and without compiling to A2UI.
 *
 * The validator has two independent gates:
 *   1. Babel AST checks for the declarative JSX contract and duplicate actions.
 *   2. A React preview rendered in Chromium for real overflow, clipping and
 *      semantic-component overlap checks.
 *
 * CLI examples:
 *   node scripts/validate-generated-card.js \
 *     --jsx outputs/card-19.jsx \
 *     --task data/20_tasks_2x2_raw.json --task-id 19
 *
 * Runner integration uses --stdin with this JSON payload:
 *   { "source": "function CardGenerated_19() {...}", "task": {...} }
 *
 * Exit codes: 0 = valid, 1 = candidate validation failed, 2 = validator error.
 */

const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

function loadModule(candidates, label) {
  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch (_) {
      // Try the next workspace-local fallback.
    }
  }
  throw new Error(`${label} is required; tried: ${candidates.join(", ")}`);
}

const parser = loadModule(["@babel/parser"], "@babel/parser");

function loadChromium() {
  let playwright;

  try {
    playwright = loadModule(["playwright"], "playwright");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(
      `Playwright Node.js 依赖缺失。请先在项目根目录运行 ` +
      `\`npm install\`。原始错误：${message}`,
    );
  }

  const { chromium } = playwright;

  if (!chromium || typeof chromium.launch !== "function") {
    throw new Error(
      "Playwright chromium 对象无效，缺少 launch() 方法。",
    );
  }

  const customChromiumPath =
    process.env.CHROMIUM_EXECUTABLE_PATH ||
    "/opt/chrome-linux/chrome";

  let executablePath;

  if (fs.existsSync(customChromiumPath)) {
    executablePath = customChromiumPath;
  } else {
    try {
      executablePath = chromium.executablePath();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(
        `无法确定 Chromium 安装位置。请运行 ` +
        `\`npm run install:chromium\` 或 ` +
        `\`npx playwright install chromium\`。原始错误：${message}`,
      );
    }

    if (!executablePath || !fs.existsSync(executablePath)) {
      throw new Error(
        `Playwright Chromium 浏览器未安装（预期位置：` +
        `${executablePath || "未知"}）。请运行 ` +
        `\`npm run install:chromium\` 或 ` +
        `\`npx playwright install chromium\`。`,
      );
    }
  }

  return {
    chromium,
    executablePath,
  };
}

const skillDir = path.resolve(__dirname, "..");
const repoRoot = skillDir;
const resourceRoot = path.resolve(
  process.env.GENUI_RESOURCE_ROOT || path.join(repoRoot, "resources"),
);
const runtimePath = path.join(skillDir, "design-system-runtime.jsx");
const generationContractPath = path.join(skillDir, "jsx_runner/resources.py");
const templatePath = path.join(skillDir, "templates/template.html");
const parseOptions = { sourceType: "script", plugins: ["jsx"], errorRecovery: false };
const CARD_SIZE_PRESETS = Object.freeze({
  "2x2": Object.freeze({ token: "2x2", width: 160, height: 160 }),
  "2x4": Object.freeze({ token: "2x4", width: 320, height: 160 }),
});
const LOCAL_BROWSER_RUNTIMES = Object.freeze([
  Object.freeze({
    name: "React",
    external: "https://unpkg.com/react@18/umd/react.production.min.js",
    localUrl: "/node_modules/react/umd/react.production.min.js",
    localFile: path.join(repoRoot, "node_modules/react/umd/react.production.min.js"),
  }),
  Object.freeze({
    name: "ReactDOM",
    external: "https://unpkg.com/react-dom@18/umd/react-dom.production.min.js",
    localUrl: "/node_modules/react-dom/umd/react-dom.production.min.js",
    localFile: path.join(repoRoot, "node_modules/react-dom/umd/react-dom.production.min.js"),
  }),
  Object.freeze({
    name: "Babel standalone",
    external: "https://unpkg.com/@babel/standalone@7/babel.min.js",
    localUrl: "/node_modules/@babel/standalone/babel.min.js",
    localFile: path.join(repoRoot, "node_modules/@babel/standalone/babel.min.js"),
  }),
]);

function usage() {
  console.log(`Usage: node scripts/validate-generated-card.js [options]

Options:
  --jsx PATH          JSX function source or a single <Card> expression
  --task PATH         task object, task array, or {tasks:[...]} JSON
  --task-id ID        select one task when --task contains multiple tasks
  --report PATH       also write the JSON result to this file
  --screenshot PATH   save the rendered card screenshot
  --no-browser        run AST, contract and duplicate-action checks only
  --stdin             read {source, task?, componentName?} JSON from stdin
  --input PATH        read the same JSON payload from a UTF-8 file
  --help              show this help

The validator never reads 2x2-0815-good-cases.jsx and never compiles JSX to A2UI.`);
}

function parseArgs(argv) {
  const options = {
    jsx: null,
    task: null,
    taskId: null,
    report: null,
    screenshot: null,
    browser: true,
    stdin: false,
    input: null,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--help") {
      usage();
      process.exit(0);
    }
    if (arg === "--no-browser") {
      options.browser = false;
      continue;
    }
    if (arg === "--stdin") {
      options.stdin = true;
      continue;
    }
    const keys = {
      "--jsx": "jsx",
      "--task": "task",
      "--task-id": "taskId",
      "--report": "report",
      "--screenshot": "screenshot",
      "--input": "input",
    };
    const key = keys[arg];
    if (!key) throw new Error(`unknown option: ${arg}`);
    const value = argv[index + 1];
    if (!value) throw new Error(`${arg} requires a value`);
    index += 1;
    options[key] = key === "taskId" ? String(value) : path.resolve(value);
  }
  const inputModes = [options.stdin, Boolean(options.input), Boolean(options.jsx)].filter(Boolean).length;
  if (inputModes > 1) throw new Error("use exactly one of --stdin, --input, or --jsx");
  if (inputModes === 0) throw new Error("--jsx, --input, or --stdin is required");
  return options;
}

function parseInputPayload(source, label) {
  if (!source.trim()) throw new Error(`${label} requires a JSON payload`);
  const payload = JSON.parse(source);
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error(`${label} payload must be an object`);
  }
  if (typeof payload.source !== "string" || !payload.source.trim()) {
    throw new Error(`${label} payload.source must be a non-empty string`);
  }
  return payload;
}

async function readStdin() {
  let source = "";
  for await (const chunk of process.stdin) source += chunk;
  return parseInputPayload(source, "--stdin");
}

function walk(node, visit) {
  if (!node || typeof node !== "object") return;
  visit(node);
  for (const [key, value] of Object.entries(node)) {
    if (["loc", "start", "end", "extra"].includes(key)) continue;
    if (Array.isArray(value)) value.forEach((item) => walk(item, visit));
    else if (value && typeof value.type === "string") walk(value, visit);
  }
}

function propertyName(property) {
  if (!property || property.computed) return null;
  if (["Identifier", "JSXIdentifier"].includes(property.key?.type)) return property.key.name;
  if (property.key?.type === "StringLiteral") return property.key.value;
  return null;
}

function jsxName(node) {
  return node?.type === "JSXIdentifier" ? node.name : null;
}

function unwrapObjectExpression(node) {
  if (node?.type === "ObjectExpression") return node;
  if (node?.type === "CallExpression" && node.arguments[0]?.type === "ObjectExpression") return node.arguments[0];
  return null;
}

function staticValue(node) {
  if (!node) return undefined;
  if (["StringLiteral", "NumericLiteral", "BooleanLiteral"].includes(node.type)) return node.value;
  if (node.type === "NullLiteral") return null;
  if (node.type === "UnaryExpression" && node.operator === "-" && node.argument?.type === "NumericLiteral") {
    return -node.argument.value;
  }
  if (node.type === "ArrayExpression") return node.elements.map(staticValue);
  if (node.type === "ObjectExpression") {
    const result = {};
    for (const property of node.properties) {
      if (property.type !== "ObjectProperty") continue;
      const name = propertyName(property);
      if (name) result[name] = staticValue(property.value);
    }
    return result;
  }
  return undefined;
}

function attributeValue(attribute) {
  if (!attribute.value) return true;
  if (attribute.value.type === "StringLiteral") return attribute.value.value;
  if (attribute.value.type === "JSXExpressionContainer") return staticValue(attribute.value.expression);
  return undefined;
}

function parseSource(source, filename) {
  try {
    return { ast: parser.parse(source, parseOptions), error: null };
  } catch (error) {
    return { ast: null, error: `${filename}: ${error.message}` };
  }
}

function findFunction(ast, preferredName) {
  const functions = [];
  walk(ast, (node) => {
    if (node.type === "FunctionDeclaration" && node.id?.name && /^Card[A-Za-z0-9_$]*$|^GeneratedCard$/.test(node.id.name)) {
      functions.push(node);
    }
  });
  if (preferredName) return functions.find((node) => node.id.name === preferredName) || null;
  return functions.length === 1 ? functions[0] : null;
}

function returnExpression(functionNode) {
  let result = null;
  walk(functionNode?.body, (node) => {
    if (!result && node.type === "ReturnStatement") result = node.argument;
  });
  return result;
}

function openingElements(node) {
  const result = [];
  walk(node, (candidate) => {
    if (candidate.type === "JSXOpeningElement") result.push(candidate);
  });
  return result;
}

function normalizeInputSource(source, componentName) {
  const trimmed = source.trim().replace(/^```(?:jsx|javascript|js)?\s*/i, "").replace(/\s*```$/, "").trim();
  if (trimmed.startsWith("<")) {
    const name = componentName || "GeneratedCard";
    return { source: `function ${name}() {\n  return (\n${trimmed}\n  );\n}\n`, componentName: name };
  }
  const parsed = parseSource(trimmed, "candidate.jsx");
  if (parsed.error) return { source: trimmed, componentName, parseError: parsed.error };
  const fn = findFunction(parsed.ast, componentName);
  if (!fn) {
    return {
      source: trimmed,
      componentName,
      parseError: componentName
        ? `candidate.jsx: cannot find function ${componentName}`
        : "candidate.jsx: expected exactly one zero-argument Card* function",
    };
  }
  return { source: trimmed, componentName: fn.id.name };
}

function pythonFrozenset(source, name) {
  const escapedName = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = source.match(
    new RegExp(`${escapedName}\\s*=\\s*frozenset\\(\\s*\\{([\\s\\S]*?)\\}\\s*\\)`),
  );
  return new Set(
    match
      ? [...match[1].matchAll(/["']([A-Z][A-Za-z0-9_]*)["']/g)].map((item) => item[1])
      : [],
  );
}

function sizeScopedGenerationComponents(source, common) {
  const block = source.match(/GENERATION_COMPONENTS_BY_SIZE\s*=\s*\{([\s\S]*?)\r?\n\}/);
  const result = new Map();
  if (!block) return result;
  for (const match of block[1].matchAll(/["'](2x[24])["']\s*:\s*frozenset\(\{([\s\S]*?)\}\)/g)) {
    const specific = [...match[2].matchAll(/["']([A-Z][A-Za-z0-9_]*)["']/g)]
      .map((item) => item[1]);
    result.set(match[1], new Set([...common, ...specific]));
  }
  return result;
}

function directJsxChildren(element) {
  if (element?.type !== "JSXElement") return [];
  return element.children.flatMap((child) => {
    if (child.type === "JSXElement") return [child];
    if (child.type === "JSXExpressionContainer" && child.expression?.type === "JSXElement") {
      return [child.expression];
    }
    return [];
  });
}

function elementProps(element) {
  return new Map((element?.openingElement?.attributes || [])
    .filter((attribute) => attribute.type === "JSXAttribute")
    .map((attribute) => [jsxName(attribute.name), attributeValue(attribute)]));
}

function cardButtonSlotDimensions(parent, childIndex) {
  const parentName = jsxName(parent?.openingElement?.name);
  const props = elementProps(parent);
  if (parentName === "Stack") {
    const width = props.get("width");
    const height = props.get("height");
    return {
      width: Number.isFinite(width) ? width : null,
      height: Number.isFinite(height) ? height : null,
    };
  }
  if (parentName !== "Grid") return { width: null, height: null };

  const columns = props.get("columns") ?? 2;
  if (!Number.isInteger(columns) || columns <= 0) return { width: null, height: null };
  const gridWidth = props.get("width");
  const columnGap = props.get("columnGap") ?? props.get("gap") ?? 0;
  const width = Number.isFinite(gridWidth) && Number.isFinite(columnGap)
    ? Math.max(0, gridWidth - columnGap * Math.max(0, columns - 1)) / columns
    : null;

  let height = null;
  const rows = props.get("rows");
  if (typeof rows === "string") {
    const tokens = rows.trim().split(/\s+/);
    const rowCount = Math.ceil(directJsxChildren(parent).length / columns);
    if (tokens.length === rowCount && tokens.every((token) => /^\d+(?:\.\d+)?px$/.test(token))) {
      height = Number(tokens[Math.floor(childIndex / columns)].slice(0, -2));
    }
  }
  return { width, height };
}

function isCardButtonSlot(element) {
  if (jsxName(element?.openingElement?.name) === "CardButton") return true;
  if (jsxName(element?.openingElement?.name) !== "Stack") return false;
  const children = directJsxChildren(element);
  return children.length === 1 && jsxName(children[0].openingElement.name) === "CardButton";
}

function validateCardButtonSlots(root, cardSize) {
  const findings = [];
  const visit = (element) => {
    const children = directJsxChildren(element);
    const parentName = jsxName(element.openingElement.name);
    const directCardButtons = children.filter((child) => jsxName(child.openingElement.name) === "CardButton");
    if (cardSize === "2x4" && parentName === "Card" && directCardButtons.length) {
      findings.push(finding(
        "error",
        "card-button-parent-slot",
        "CardButton must be placed in a half-card Stack slot or a documented Grid cell",
      ));
    }
    if (cardSize === "2x4" && parentName === "Stack" && directCardButtons.length
      && !(children.length === 1 && directCardButtons.length === 1)) {
      findings.push(finding(
        "error",
        "card-button-parent-slot",
        "each CardButton in a Stack must be the only child of its own explicit or flex-allocated slot; Grid cells are already slots",
      ));
    }
    if (cardSize === "2x4" && children.filter(isCardButtonSlot).length >= 2) {
      const props = elementProps(element);
      const columns = props.get("columns") ?? 2;
      const multiColumnGrid = parentName === "Grid" && (
        (Number.isInteger(columns) && columns > 1)
        || (typeof columns === "string" && columns.trim().split(/\s+/).length > 1)
      );
      if (multiColumnGrid) {
        const slotCount = children.filter(isCardButtonSlot).length;
        if (columns !== 2 || ![3, 4].includes(slotCount)) {
          findings.push(finding(
            "error",
            "card-button-grid-layout",
            "a multi-column CardButton Grid must be the documented Type 9 layout with two columns and three or four actions",
          ));
        }
      } else if (["Card", "Stack"].includes(parentName) && (props.get("direction") ?? "column") === "row") {
        findings.push(finding(
          "error",
          "card-button-horizontal-layout",
          "outside the documented Type 9 Grid, 2x4 CardButton actions must be stacked vertically; a single horizontal row is not allowed",
        ));
      }
    }
    children.forEach((child, index) => {
      if (jsxName(child.openingElement.name) === "CardButton") {
        const { width, height } = cardButtonSlotDimensions(element, index);
        if (Number.isFinite(width) && Number.isFinite(height) && width < height) {
          findings.push(finding(
            "error",
            "card-button-slot-aspect",
            `<CardButton> parent slot must be at least as wide as it is tall; found ${width}×${height}vp`,
          ));
        }
        if (Number.isFinite(width) && width > 144) {
          findings.push(finding(
            "error",
            "card-button-slot-width",
            `<CardButton> parent slot must stay within one half-card region of at most 144vp; found ${width}vp`,
          ));
        }
        if (Number.isFinite(height) && (height < 48 || height > 64)) {
          findings.push(finding(
            "error",
            "card-button-slot-height",
            `<CardButton> parent slot height must be between 48vp and 64vp; found ${height}vp`,
          ));
        }
      }
      visit(child);
    });
  };
  visit(root);
  return findings;
}

function runtimeSchema() {
  const runtimeSource = fs.readFileSync(runtimePath, "utf8");
  const parsed = parseSource(runtimeSource, runtimePath);
  if (parsed.error) throw new Error(parsed.error);
  const functionProps = new Map();
  const contracts = new Map();
  let publicComponents = new Set();
  let appearances = new Set();

  walk(parsed.ast, (node) => {
    if (node.type === "FunctionDeclaration" && node.id && node.params[0]?.type === "ObjectPattern") {
      const props = new Set();
      for (const property of node.params[0].properties) {
        if (property.type !== "ObjectProperty") continue;
        const name = propertyName(property);
        if (name) props.add(name);
      }
      functionProps.set(node.id.name, props);
    }
    if (node.type === "VariableDeclarator" && node.id?.name === "CARD_APPEARANCES") {
      const object = unwrapObjectExpression(node.init);
      if (object) appearances = new Set(object.properties.map(propertyName).filter(Boolean));
    }
    if (node.type === "VariableDeclarator" && node.id?.name === "componentContracts") {
      const object = unwrapObjectExpression(node.init);
      if (object) {
        for (const property of object.properties) {
          const name = propertyName(property);
          const value = staticValue(property.value);
          if (name && value) contracts.set(name, value);
        }
      }
    }
    if (node.type === "AssignmentExpression") {
      const left = node.left;
      if (left?.type !== "MemberExpression" || left.computed || left.object?.name !== "global" || left.property?.name !== "ClawWidgetDesignSystem") return;
      const object = unwrapObjectExpression(node.right);
      if (object) publicComponents = new Set(object.properties.map(propertyName).filter((name) => name && /^[A-Z]/.test(name)));
    }
  });

  const contractSource = fs.readFileSync(generationContractPath, "utf8");
  const safeMatch = contractSource.match(
    /GENERATION_COMPONENTS\s*=\s*frozenset\(\s*\{([\s\S]*?)\}\s*\)/,
  );
  const generationSafe = new Set(safeMatch ? [...safeMatch[1].matchAll(/["']([A-Z][A-Za-z0-9_]*)["']/g)].map((match) => match[1]) : []);
  const generationCommon = pythonFrozenset(contractSource, "GENERATION_COMPONENTS_COMMON");
  const generationSafeBySize = sizeScopedGenerationComponents(contractSource, generationCommon);
  const templateSource = fs.readFileSync(templatePath, "utf8");
  const templateMatch = templateSource.match(/const\s*\{([\s\S]*?)\}\s*=\s*window\.ClawWidgetDesignSystem\s*;/);
  if (!templateMatch) {
    throw new Error("template.html must destructure window.ClawWidgetDesignSystem for generated JSX");
  }
  const templateComponents = new Set(
    templateMatch[1]
      .split(",")
      .map((name) => name.trim())
      .filter(Boolean),
  );
  const missingTemplateComponents = [...generationSafe]
    .filter((name) => !templateComponents.has(name))
    .sort();
  if (missingTemplateComponents.length) {
    throw new Error(`template.html does not register generation-safe components: ${missingTemplateComponents.join(", ")}`);
  }
  if (!publicComponents.size || !generationSafe.size || !appearances.size) {
    throw new Error("cannot derive runtime exports, Card appearances, or JSX generation-safe components");
  }
  for (const size of Object.keys(CARD_SIZE_PRESETS)) {
    const scoped = generationSafeBySize.get(size);
    if (!scoped?.size) {
      throw new Error(`cannot derive JSX generation-safe components for Card size=${JSON.stringify(size)}`);
    }
    const drift = [...scoped].filter((name) => !generationSafe.has(name));
    if (drift.length) {
      throw new Error(`Card size=${JSON.stringify(size)} declares components outside GENERATION_COMPONENTS: ${drift.join(", ")}`);
    }
  }
  return {
    runtimeSource,
    functionProps,
    contracts,
    publicComponents,
    generationSafe,
    generationSafeBySize,
    appearances,
  };
}

function finding(severity, code, message, details) {
  return { severity, code, message, ...(details === undefined ? {} : { details }) };
}

function browserFinding(severity, code, message, diagnostic = {}) {
  return {
    severity,
    code,
    message,
    ...diagnostic,
  };
}

function rounded(value) {
  return Number.isFinite(value) ? Math.round(value * 100) / 100 : value;
}

function diagnosticComponentLabel(item) {
  if (item?.component) {
    return item.componentText
      ? `${item.component}「${item.componentText}」`
      : item.component;
  }
  if (item?.element?.className) return `${item.element.tag}.${item.element.className}`;
  return item?.element?.tag || "未知 DOM 节点";
}

function strongestDiagnostics(items, score) {
  const strongest = new Map();
  for (const item of items || []) {
    const key = item?.component
      ? `${item.component}\u0000${item.componentText || ""}`
      : `${item?.element?.tag || ""}\u0000${item?.element?.className || ""}\u0000${item?.element?.text || ""}`;
    const previous = strongest.get(key);
    if (!previous || score(item) > score(previous)) strongest.set(key, item);
  }
  return [...strongest.values()];
}

function normalizeSemantic(value) {
  return String(value ?? "")
    .normalize("NFKC")
    .replace(/°C|℃/gi, "°")
    .replace(/[\s｜|·,:：，。、“”‘’()（）\-–—]/g, "")
    .toLowerCase();
}

function basename(value) {
  return typeof value === "string" && value ? path.posix.basename(value.replaceAll("\\", "/")) : "";
}

function collectSignature(root) {
  const resources = [];
  const controls = [];
  const collectNestedResources = (component, prop, value) => {
    if (value && typeof value === "object") {
      if (typeof value.icon === "string") {
        resources.push({ component, prop: `${prop}.icon`, value: value.icon });
      }
      for (const [key, nested] of Object.entries(value)) {
        if (key !== "icon") collectNestedResources(component, `${prop}.${key}`, nested);
      }
    }
  };
  for (const opening of openingElements(root)) {
    const component = jsxName(opening.name) || "<member>";
    const props = {};
    for (const attribute of opening.attributes) {
      if (attribute.type !== "JSXAttribute") continue;
      const prop = jsxName(attribute.name);
      props[prop] = attributeValue(attribute);
      if (["icon", "src", "checkIcon"].includes(prop) && typeof props[prop] === "string") {
        resources.push({ component, prop, value: props[prop] });
      }
      if (prop === "items" && Array.isArray(props[prop])) {
        for (const item of props[prop]) {
          if (item && typeof item.icon === "string") resources.push({ component, prop: "items.icon", value: item.icon });
        }
      }
      if (prop === "visual") collectNestedResources(component, prop, props[prop]);
    }
    if (["PillButton", "CircleButton", "CardButton"].includes(component)) {
      let label = "";
      if (typeof props.label === "string") label = props.label;
      else if (typeof props.text === "string") label = props.text;
      controls.push({
        component,
        label,
        ariaLabel: typeof props.ariaLabel === "string" ? props.ariaLabel : "",
        icon: typeof props.icon === "string" ? props.icon : "",
        actionId: typeof props.actionId === "string" ? props.actionId : "",
        line: opening.loc?.start.line || null,
      });
    }
  }
  return { resources, controls };
}

function validateStructure(source, componentName, schema, task) {
  const findings = [];
  const parsed = parseSource(source, "candidate.jsx");
  if (parsed.error) return { findings: [finding("error", "jsx-parse", parsed.error)], root: null, signature: null, cardSize: null };
  const topLevel = parsed.ast.program.body.filter((node) => node.type !== "EmptyStatement");
  const fn = findFunction(parsed.ast, componentName);
  if (!fn) return { findings: [finding("error", "generated-card-count", `expected exactly one function named ${componentName || "Card*"}`)], root: null, signature: null, cardSize: null };
  if (topLevel.length !== 1) findings.push(finding("error", "extra-top-level-code", "only one generated card function is allowed"));
  if (fn.params.length) findings.push(finding("error", "generated-card-params", `${fn.id.name} must be a zero-argument function`));
  const root = returnExpression(fn);
  const rootName = root?.type === "JSXElement" ? jsxName(root.openingElement.name) : null;
  if (rootName !== "Card") findings.push(finding("error", "card-root", `generated card root must be <Card>, found ${rootName || root?.type || "nothing"}`));
  if (/(?:#[0-9a-f]{3,8}\b|\brgba?\s*\(|\b(?:linear|radial)-gradient\s*\()/i.test(source)) {
    findings.push(finding("error", "hardcoded-color", "hard-coded colors or gradients are forbidden"));
  }
  if (!root) return { findings, root: null, signature: null, cardSize: null };

  const rootProps = new Map(root.openingElement.attributes
    .filter((attribute) => attribute.type === "JSXAttribute")
    .map((attribute) => [jsxName(attribute.name), attributeValue(attribute)]));
  const cardAppearance = rootProps.get("appearance");

  const cardModeComponents = new Set(["PillButton", "CircleButton", "ProgressCircleSingle", "ProgressCircle", "NumericRatio", "NumericRatioStack"]);
  const ariaComponents = new Set(["CircleButton", "ProgressCircleSingle", "ProgressCircle"]);
  const taskSize = task?.size;
  const taskCardSize = CARD_SIZE_PRESETS[taskSize] || null;
  if (taskSize != null && !taskCardSize) {
    findings.push(finding("error", "task-card-size", `task.size must be \"2x2\" or \"2x4\", found ${JSON.stringify(taskSize)}`));
  }
  let resolvedCardSize = taskCardSize;
  for (const opening of openingElements(root)) {
    const name = jsxName(opening.name);
    if (!name) {
      findings.push(finding("error", "member-jsx", `member/namespaced JSX at line ${opening.loc?.start.line}`));
      continue;
    }
    if (/^[a-z]/.test(name)) findings.push(finding("error", "native-jsx", `native <${name}> at line ${opening.loc?.start.line}`));
    else if (!schema.generationSafe.has(name)) findings.push(finding("error", "unsafe-component", `<${name}> is not generation-safe at line ${opening.loc?.start.line}`));
    else if (!schema.publicComponents.has(name)) findings.push(finding("error", "unknown-component", `<${name}> is not exported by the runtime at line ${opening.loc?.start.line}`));

    const allowed = schema.functionProps.get(name) || new Set();
    const provided = new Map();
    for (const attribute of opening.attributes) {
      if (attribute.type === "JSXSpreadAttribute") {
        findings.push(finding("error", "spread-props", `spread props on <${name}> at line ${attribute.loc?.start.line}`));
        continue;
      }
      const prop = jsxName(attribute.name);
      const value = attributeValue(attribute);
      provided.set(prop, value);
      if (["className", "style"].includes(prop)) findings.push(finding("error", "forbidden-prop", `${prop} is forbidden on <${name}> at line ${attribute.loc?.start.line}`));
      const compilerMetadata = prop === "dataValueMaps" && allowed.has("dataIds");
      if (prop && !allowed.has(prop) && !compilerMetadata) findings.push(finding("error", "unknown-prop", `unknown prop ${prop} on <${name}> at line ${attribute.loc?.start.line}`));
      if (["size", "padding", "gap", "flex", "basis", "minWidth", "minHeight", "mt", "mb", "ml", "mr", "top", "right", "bottom", "left", "columns"].includes(prop)
        && typeof value === "string" && /^-?\d+(?:\.\d+)?$/.test(value)) {
        findings.push(finding("error", "numeric-string-prop", `${name}.${prop} must use a JSX number expression, not ${JSON.stringify(value)}`));
      }
    }
    const contract = schema.contracts.get(name);
    for (const required of contract?.required || []) {
      if (!provided.has(required)) findings.push(finding("error", "missing-required-prop", `<${name}> is missing required prop ${required}`));
    }
    if (contract?.requiredOneOf?.length && !contract.requiredOneOf.some((prop) => provided.has(prop))) {
      findings.push(finding("error", "missing-one-of-prop", `<${name}> requires one of: ${contract.requiredOneOf.join(", ")}`));
    }
    if (name === "Card") {
      const actualSize = provided.get("size");
      if (taskCardSize && actualSize !== taskCardSize.token) {
        findings.push(finding(
          "error",
          "card-size",
          `task.size=${JSON.stringify(taskCardSize.token)} requires Card.size=${JSON.stringify(taskCardSize.token)}, found ${JSON.stringify(actualSize)}`,
        ));
      } else if (!taskCardSize && !CARD_SIZE_PRESETS[actualSize] && actualSize !== 160) {
        findings.push(finding("error", "card-size", `Card.size must be \"2x2\" or \"2x4\", found ${JSON.stringify(actualSize)}`));
      }
      resolvedCardSize = taskCardSize || CARD_SIZE_PRESETS[actualSize] || (actualSize === 160 ? CARD_SIZE_PRESETS["2x2"] : null);
      if (!schema.appearances.has(provided.get("appearance"))) findings.push(finding("error", "card-appearance", `unsupported Card.appearance: ${JSON.stringify(provided.get("appearance"))}`));
      const padding = provided.has("padding") ? provided.get("padding") : 12;
      if (padding !== 12 && padding !== "12px") {
        findings.push(finding("error", "card-padding", "Card.padding must be omitted or equal to 12vp"));
      }
    }
    if (cardModeComponents.has(name) && provided.get("appearance") !== "card") {
      findings.push(finding("error", "card-mode", `<${name}> inside Card must declare appearance="card"`));
    }
    if (ariaComponents.has(name) && !String(provided.get("ariaLabel") || "").trim()) {
      findings.push(finding("error", "missing-aria-label", `<${name}> must declare a non-empty ariaLabel`));
    }
    for (const [prop, allowedValues] of Object.entries(contract || {})) {
      if (["required", "optional", "requiredOneOf", "itemsMinLength"].includes(prop) || !Array.isArray(allowedValues) || !provided.has(prop)) continue;
      if (!allowedValues.includes(provided.get(prop))) findings.push(finding("error", "invalid-enum-prop", `<${name}> prop ${prop} has invalid value ${JSON.stringify(provided.get(prop))}`));
    }
    if (Number.isInteger(contract?.itemsMinLength)) {
      const items = provided.get("items");
      if (!Array.isArray(items) || items.length < contract.itemsMinLength) findings.push(finding("error", "component-items", `<${name}> requires at least ${contract.itemsMinLength} items`));
    }
    if (name === "NumericRatioStack" && Array.isArray(provided.get("items"))
      && provided.get("items").length !== 3) {
      findings.push(finding(
        "error",
        "component-items",
        "<NumericRatioStack> requires exactly three items",
      ));
    }
    const itemRules = {
      TopTextBottomValue: { required: ["label", "value", "unit"], staticText: ["label", "unit"] },
      TableText: { required: ["label", "parameter"], staticText: ["label"] },
      TextBlock: { required: ["label", "parameter"], staticText: ["label"] },
      H_BarChart: { required: ["label", "valueUnit", "percent"], staticText: ["label"] },
    }[name];
    if (itemRules && Array.isArray(provided.get("items"))) {
      provided.get("items").forEach((item, index) => {
        if (!item || typeof item !== "object" || Array.isArray(item)) {
          findings.push(finding("error", "component-item-shape", `<${name}> items[${index}] must be an object`));
          return;
        }
        const missing = itemRules.required.filter((prop) => !Object.hasOwn(item, prop));
        if (missing.length) findings.push(finding("error", "component-item-shape", `<${name}> items[${index}] is missing: ${missing.join(", ")}`));
        for (const prop of itemRules.staticText) if (typeof item[prop] !== "string" || !item[prop].trim()) findings.push(finding("error", "component-item-shape", `<${name}> items[${index}].${prop} must be a non-empty string`));
        if (name === "H_BarChart" && (!Number.isFinite(item.percent) || item.percent < 0 || item.percent > 100)) findings.push(finding("error", "component-item-shape", `<H_BarChart> items[${index}].percent must be a number from 0 to 100`));
      });
    }
    if (["ProgressLine2", "H_BarChart", "Gauge"].includes(name)) {
      const expectedMode = typeof cardAppearance === "string" && cardAppearance.endsWith("-gradient") ? "dark" : "light";
      if (provided.get("mode") !== expectedMode) findings.push(finding("error", "component-mode", `<${name}> on Card appearance=${JSON.stringify(cardAppearance)} must use mode=${JSON.stringify(expectedMode)}`));
    }
    if (name === "InfoBlock") {
      const visual = provided.get("visual");
      const visualKeys = visual && typeof visual === "object" && !Array.isArray(visual) ? Object.keys(visual) : [];
      if (!visual || !["icon", "progressCircle"].includes(visual.type) || typeof visual.icon !== "string" || !visual.icon.trim()) {
        findings.push(finding("error", "info-block-visual", '<InfoBlock> visual must select icon or progressCircle and provide a non-empty icon src'));
      } else {
        const allowedKeys = visual.type === "icon" ? ["type", "icon", "color"] : ["type", "icon"];
        if (visualKeys.some((key) => !allowedKeys.includes(key)) || (visual.type === "icon" && ![undefined, "native"].includes(visual.color))) findings.push(finding("error", "info-block-visual", '<InfoBlock> visual contains unsupported fields or color'));
      }
    }
    if (name === "Gauge") {
      const value = provided.get("value");
      const minimum = provided.has("min") ? provided.get("min") : 1;
      const maximum = provided.has("max") ? provided.get("max") : 100;
      if (!Number.isFinite(Number(value))) findings.push(finding("error", "gauge-value", "<Gauge> value must be numeric"));
      if (!Number.isFinite(minimum) || !Number.isFinite(maximum) || minimum >= maximum) findings.push(finding("error", "gauge-range", "<Gauge> requires numeric min < max"));
    }
    if (name === "CardButton" && (typeof provided.get("text") !== "string" || !provided.get("text").trim())) {
      findings.push(finding("error", "card-button-text", "<CardButton> text must be a non-empty string"));
    }
  }
  findings.push(...validateCardButtonSlots(root, resolvedCardSize?.token));
  const scopedComponents = schema.generationSafeBySize.get(resolvedCardSize?.token);
  if (scopedComponents) {
    const componentNames = new Set(openingElements(root).map((opening) => jsxName(opening.name)));
    for (const name of componentNames) {
      if (schema.generationSafe.has(name) && !scopedComponents.has(name)) {
        findings.push(finding(
          "error",
          "component-card-size",
          `<${name}> is not available for Card size=${JSON.stringify(resolvedCardSize.token)}`,
        ));
      }
    }
  }
  const infoBlocks = openingElements(root).filter((opening) => jsxName(opening.name) === "InfoBlock");
  if (resolvedCardSize?.token === "2x2" && infoBlocks.length && infoBlocks.length !== 2) {
    findings.push(finding("error", "info-block-count", 'Card size="2x2" must contain exactly two InfoBlock components'));
  }
  return { findings, root, signature: collectSignature(root), cardSize: resolvedCardSize };
}

function validateResources(signature, task) {
  if (!task) return [];
  const candidates = Array.isArray(task.assetCandidates) ? task.assetCandidates : [];
  const allowed = new Set(candidates
    .map((candidate) => typeof candidate?.src === "string" ? candidate.src.replaceAll("\\", "/") : null)
    .filter(Boolean));
  const findings = [];
  for (const resource of signature?.resources || []) {
    const normalized = resource.value.replaceAll("\\", "/");
    if (!allowed.has(normalized)) {
      findings.push(finding(
        "error",
        "resource-not-candidate",
        `${resource.component}.${resource.prop}=${JSON.stringify(resource.value)} is not an exact src from input assetCandidates`,
      ));
    }
  }
  return findings;
}

function controlsMatch(left, right) {
  const leftText = normalizeSemantic(left.label || left.ariaLabel);
  const rightText = normalizeSemantic(right.label || right.ariaLabel);
  const textMatch = leftText.length >= 2 && rightText.length >= 2 && (leftText.includes(rightText) || rightText.includes(leftText));
  const leftIcon = basename(left.icon);
  const rightIcon = basename(right.icon);
  return textMatch || Boolean(leftIcon && rightIcon && leftIcon === rightIcon);
}

function validateDuplicateActions(signature, task) {
  const findings = [];
  const controls = signature?.controls || [];
  let actions = [];
  if (Array.isArray(task?.actions)) actions = task.actions;
  else if (Array.isArray(task?.eventCandidates)) actions = task.eventCandidates;
  const knownActionIds = new Set(actions.map((action) => action?.id).filter((id) => typeof id === "string" && id));
  const reported = new Set();

  for (const actionId of new Set(controls.map((control) => control.actionId).filter(Boolean))) {
    const matches = controls.filter((control) => control.actionId === actionId);
    if (!knownActionIds.has(actionId)) {
      findings.push(finding("error", "unknown-action-id", `actionId ${JSON.stringify(actionId)} is not present in task.actions`, matches));
    }
    if (matches.length > 1) {
      const key = matches.map((item) => `${item.component}:${item.line}`).join("|");
      reported.add(key);
      findings.push(finding("error", "duplicate-action-control", `actionId ${JSON.stringify(actionId)} is represented by ${matches.length} controls`, matches));
    }
  }
  for (let left = 0; left < controls.length; left += 1) {
    for (let right = left + 1; right < controls.length; right += 1) {
      if (controls[left].actionId || controls[right].actionId) continue;
      if (!controlsMatch(controls[left], controls[right])) continue;
      const pair = [controls[left], controls[right]];
      const key = pair.map((item) => `${item.component}:${item.line}`).join("|");
      if (reported.has(key)) continue;
      findings.push(finding("error", "duplicate-action-control", "two controls appear to represent the same action", pair));
    }
  }
  return findings;
}

function localizeBrowserRuntimes(template) {
  let localized = template;
  for (const runtime of LOCAL_BROWSER_RUNTIMES) {
    if (!fs.existsSync(runtime.localFile)) {
      throw new Error(`${runtime.name} browser runtime is missing: ${runtime.localFile}; run npm install`);
    }
    const escapedSource = runtime.external.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const scriptPattern = new RegExp(
      `<script\\b[^>]*\\bsrc=["']${escapedSource}["'][^>]*>\\s*<\\/script>`,
      "i",
    );
    if (!scriptPattern.test(localized)) {
      throw new Error(`template.html does not contain the expected ${runtime.name} CDN script`);
    }
    localized = localized.replace(scriptPattern, `<script src="${runtime.localUrl}"></script>`);
  }
  return localized;
}

function htmlPreview(source, componentName, runtimeSource) {
  const template = localizeBrowserRuntimes(fs.readFileSync(templatePath, "utf8"));
  if (/<\/script/i.test(source)) throw new Error("candidate JSX contains a closing script tag");
  if (/<\/script/i.test(runtimeSource)) throw new Error("design-system-runtime.jsx contains a closing script tag");
  const alias = componentName === "GeneratedCard" ? "" : `\nconst GeneratedCard = ${componentName};`;
  const generated = `${source.trim()}${alias}`;
  const marker = /(\s*\/\/ === BEGIN GENERATED CARD ===)[\s\S]*?(\/\/ === END GENERATED CARD ===)/;
  if (!marker.test(template)) throw new Error("template.html generated-card marker is missing");
  return template
    .replace("{{TITLE}}", "Generated Card Validation")
    .replace("{{BASE_HREF}}", "/")
    .replace("{{DESIGN_SYSTEM_RUNTIME}}", runtimeSource)
    .replace(marker, `$1\n${generated}\n    $2`);
}

function mimeType(filePath) {
  return ({
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".jsx": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
  })[path.extname(filePath).toLowerCase()] || "application/octet-stream";
}

async function startStaticServer(previewHtml) {
  const previewRoute = "/__generated_card_validation__.html";
  const server = http.createServer((request, response) => {
    let pathname;
    try {
      pathname = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
    } catch (_) {
      response.writeHead(400).end("Bad request");
      return;
    }
    if (pathname === previewRoute) {
      response.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" });
      response.end(previewHtml);
      return;
    }
    const isResourceRequest = pathname === "/resources"
      || pathname.startsWith("/resources/");
    const staticRoot = isResourceRequest ? resourceRoot : repoRoot;
    const relativeRequest = isResourceRequest
      ? pathname.replace(/^\/resources\/?/, "")
      : `.${pathname}`;
    const candidate = path.resolve(staticRoot, relativeRequest);
    const relative = path.relative(staticRoot, candidate);
    if (relative.startsWith("..") || path.isAbsolute(relative)) {
      response.writeHead(403).end("Forbidden");
      return;
    }
    fs.stat(candidate, (error, stat) => {
      if (error || !stat.isFile()) {
        response.writeHead(404).end("Not found");
        return;
      }
      response.writeHead(200, { "content-type": mimeType(candidate), "cache-control": "no-store" });
      const stream = fs.createReadStream(candidate);
      stream.once("error", () => response.destroy());
      stream.pipe(response);
    });
  });
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  return { server, url: `http://127.0.0.1:${server.address().port}${previewRoute}` };
}

async function waitForAssets(page) {
  await page.evaluate(() => document.fonts?.ready);
  await page.evaluate(() => Promise.all(Array.from(document.images).map((image) => {
    if (image.complete) return undefined;
    return new Promise((resolve) => {
      image.addEventListener("load", resolve, { once: true });
      image.addEventListener("error", resolve, { once: true });
    });
  })));
  await page.waitForTimeout(100);
}

async function inspectBrowserCard(page) {
  return page.evaluate(async () => {
    const errorPanel = document.querySelector("#preview-error");
    const cards = Array.from(document.querySelectorAll(".generated-card-frame"));
    const card = cards[0];
    const result = {
      mountState: document.documentElement.dataset.generatedCard || null,
      errorPanel: errorPanel && !errorPanel.hidden ? errorPanel.textContent : null,
      cardCount: cards.length,
      card: null,
      outsideBounds: [],
      verticalClipping: [],
      horizontalClipping: [],
      visibleHorizontalOverflow: [],
      semanticComponents: [],
      edgeSpacingViolations: [],
      heightOverflowComponents: [],
      semanticOverlaps: [],
      semanticContentOverflows: [],
      resourceElements: [],
    };
    if (!card) return result;
    const cardRect = card.getBoundingClientRect();
    result.card = {
      width: cardRect.width,
      height: cardRect.height,
      clientWidth: card.clientWidth,
      clientHeight: card.clientHeight,
      scrollWidth: card.scrollWidth,
      scrollHeight: card.scrollHeight,
    };
    const tolerance = 0.75;
    const semanticSelector = [
      ".title-demo-row", ".badge", ".data-display", ".info-block", ".top-text-bottom-value", ".table-text", ".text-block", ".bar-chart", ".gauge", ".ed", ".emphasis-text", ".secondary-body",
      ".summary-text", ".pb", ".pl2", ".pc-single-combo", ".pc-component",
      ".numeric-ratio-stack", ".numeric-ratio", ".cli", ".ec", ".pill-btn", ".circle-btn", ".card-action-btn",
    ].join(",");
    const textOf = (node) => (node?.textContent || "").trim().replace(/\s+/g, " ").slice(0, 100);
    const classOf = (node) => String(node?.className?.baseVal || node?.className || "");
    const semanticName = (node) => {
      const names = [
        ["title-demo-row", "Title"], ["badge", "Badge"], ["data-display", "DataDisplay"], ["info-block", "InfoBlock"], ["top-text-bottom-value", "TopTextBottomValue"], ["table-text", "TableText"], ["text-block", "TextBlock"], ["bar-chart", "H_BarChart"], ["gauge", "Gauge"], ["ed", "EmphasizedData"],
        ["emphasis-text", "EmphasisText"], ["secondary-body", "SecondaryBody"],
        ["summary-text", "Summary"], ["pb", "ProgressLine1"], ["pl2", "ProgressLine2"],
        ["pc-single-combo", "ProgressCircleSingle"], ["pc-component", "ProgressCircle"],
        ["numeric-ratio-stack", "NumericRatioStack"], ["numeric-ratio", "NumericRatio"],
        ["cli", "ChecklistItem"], ["ec", "EventCard"], ["pill-btn", "PillButton"],
        ["circle-btn", "CircleButton"], ["card-action-btn", "CardButton"],
      ];
      return names.find(([className]) => node?.classList?.contains(className))?.[1] || null;
    };
    const axisOverflow = (css, axis) => {
      const value = axis === "x" ? css.overflowX : css.overflowY;
      return value === "visible" ? css.overflow : value;
    };
    const visibleRect = (node) => {
      const rect = node.getBoundingClientRect();
      const css = getComputedStyle(node);
      const width = axisOverflow(css, "x") === "visible"
        ? Math.max(rect.width, node.scrollWidth)
        : rect.width;
      const height = axisOverflow(css, "y") === "visible"
        ? Math.max(rect.height, node.scrollHeight)
        : rect.height;
      return {
        x: rect.x,
        y: rect.y,
        left: rect.left,
        top: rect.top,
        right: rect.left + width,
        bottom: rect.top + height,
        width,
        height,
      };
    };
    const paintedRect = (node) => {
      const borderRect = node.getBoundingClientRect();
      const rootCss = getComputedStyle(node);
      let left = borderRect.left;
      let top = borderRect.top;
      let right = borderRect.right;
      let bottom = borderRect.bottom;

      // scrollWidth is reliable for visible single-line/fixed-child overflow,
      // while scrollHeight can include font leading that is not actually
      // painted outside the border box. Expand horizontally here and derive
      // any vertical expansion from real descendant rectangles below.
      if (axisOverflow(rootCss, "x") === "visible") {
        right = Math.max(right, borderRect.left + node.scrollWidth);
      }

      for (const descendant of node.querySelectorAll("*")) {
        const css = getComputedStyle(descendant);
        const rect = descendant.getBoundingClientRect();
        if (
          css.display === "none"
          || css.visibility === "hidden"
          || Number(css.opacity) === 0
          || rect.width === 0
          || rect.height === 0
        ) continue;

        let visibleLeft = rect.left;
        let visibleTop = rect.top;
        let visibleRight = rect.right;
        let visibleBottom = rect.bottom;
        for (let ancestor = descendant.parentElement; ancestor; ancestor = ancestor.parentElement) {
          const ancestorCss = getComputedStyle(ancestor);
          const ancestorRect = ancestor.getBoundingClientRect();
          if (axisOverflow(ancestorCss, "x") !== "visible") {
            visibleLeft = Math.max(visibleLeft, ancestorRect.left);
            visibleRight = Math.min(visibleRight, ancestorRect.right);
          }
          if (axisOverflow(ancestorCss, "y") !== "visible") {
            visibleTop = Math.max(visibleTop, ancestorRect.top);
            visibleBottom = Math.min(visibleBottom, ancestorRect.bottom);
          }
          if (ancestor === node) break;
        }
        if (visibleRight <= visibleLeft || visibleBottom <= visibleTop) continue;
        left = Math.min(left, visibleLeft);
        top = Math.min(top, visibleTop);
        right = Math.max(right, visibleRight);
        bottom = Math.max(bottom, visibleBottom);
      }
      return {
        x: left,
        y: top,
        left,
        top,
        right,
        bottom,
        width: right - left,
        height: bottom - top,
      };
    };
    const relativeRect = (rect) => ({
      x: rect.x - cardRect.x,
      y: rect.y - cardRect.y,
      width: rect.width,
      height: rect.height,
    });
    const parentLayout = (node) => {
      const parent = node?.parentElement;
      if (!parent || parent === document.documentElement) return null;
      const rect = parent.getBoundingClientRect();
      const css = getComputedStyle(parent);
      return {
        tag: parent.tagName.toLowerCase(),
        className: classOf(parent),
        rect: relativeRect(rect),
        display: css.display,
        flexDirection: css.flexDirection,
        gap: css.gap,
        overflowX: css.overflowX,
        overflowY: css.overflowY,
      };
    };
    const describeNode = (node, rect = node.getBoundingClientRect()) => {
      const owner = node.matches(semanticSelector) ? node : node.closest(semanticSelector);
      return {
        component: owner ? semanticName(owner) : null,
        componentText: owner ? textOf(owner) : "",
        element: {
          tag: node.tagName.toLowerCase(),
          className: classOf(node),
          text: textOf(node),
        },
        rect: relativeRect(rect),
        parentLayout: parentLayout(node),
      };
    };
    for (const node of card.querySelectorAll("*")) {
      if (node.closest(".generated-card-background")) continue;
      const rect = node.getBoundingClientRect();
      const css = getComputedStyle(node);
      if (css.display === "none" || css.visibility === "hidden" || rect.width === 0 || rect.height === 0) continue;
      const overflow = {
        left: Math.max(0, cardRect.left - rect.left),
        top: Math.max(0, cardRect.top - rect.top),
        right: Math.max(0, rect.right - cardRect.right),
        bottom: Math.max(0, rect.bottom - cardRect.bottom),
      };
      if (Math.max(...Object.values(overflow)) > tolerance) {
        result.outsideBounds.push({
          ...describeNode(node, rect),
          overflow,
        });
      }
      const clipsX = node.scrollWidth > node.clientWidth + 1;
      const clipsY = node.scrollHeight > node.clientHeight + 1;
      const clips = {
        ...describeNode(node, rect),
        availableSize: { width: node.clientWidth, height: node.clientHeight },
        requiredSize: { width: node.scrollWidth, height: node.scrollHeight },
      };
      const brokenImage = node.tagName === "IMG" && (!node.complete || node.naturalWidth === 0);
      const overflowX = axisOverflow(css, "x");
      const overflowY = axisOverflow(css, "y");
      const intentionalGaugeCrop = Boolean(node.closest(".gauge"));
      if (!brokenImage && !intentionalGaugeCrop && clipsY && ["hidden", "clip"].includes(overflowY)) result.verticalClipping.push(clips);
      if (!brokenImage && clipsX && ["hidden", "clip"].includes(overflowX)) result.horizontalClipping.push(clips);
      if (
        !brokenImage
        && clipsX
        && overflowX === "visible"
        && node.matches(semanticSelector)
      ) {
        result.visibleHorizontalOverflow.push(clips);
      }
    }

    const semanticCandidates = Array.from(card.querySelectorAll(semanticSelector)).filter((node) => {
      const rect = node.getBoundingClientRect();
      const css = getComputedStyle(node);
      return rect.width > 0 && rect.height > 0 && css.display !== "none" && css.visibility !== "hidden" && Number(css.opacity) !== 0;
    });
    const semanticNodes = semanticCandidates.filter((node) => !semanticCandidates.some((candidate) => candidate !== node && candidate.contains(node)));
    const describe = (node, rect) => ({
      component: semanticName(node),
      componentText: textOf(node),
      element: { tag: node.tagName.toLowerCase(), className: classOf(node) },
      rect: relativeRect(rect),
      parentLayout: parentLayout(node),
    });
    const semanticPaintedRects = new Map(
      semanticNodes.map((node) => [node, paintedRect(node)]),
    );
    result.semanticComponents = semanticNodes.map((node) => describe(
      node,
      semanticPaintedRects.get(node),
    ));
    // Text ranges include a few pixels of normal font leading. Allow that
    // baseline slack, but reject larger excursions caused by flex/grid shrink
    // or wrapped content escaping the semantic component that owns it.
    const contentOverflowTolerance = 6;
    for (const owner of semanticNodes) {
      const ownerRect = owner.getBoundingClientRect();
      const textElements = [owner, ...owner.querySelectorAll("*")].filter((node) => {
        const css = getComputedStyle(node);
        return css.display !== "none"
          && css.visibility !== "hidden"
          && Number(css.opacity) !== 0
          && Array.from(node.childNodes).some((child) => child.nodeType === Node.TEXT_NODE && child.textContent.trim());
      });
      for (const textElement of textElements) {
        for (const textNode of Array.from(textElement.childNodes).filter(
          (child) => child.nodeType === Node.TEXT_NODE && child.textContent.trim(),
        )) {
          const range = document.createRange();
          range.selectNodeContents(textNode);
          for (const textRect of range.getClientRects()) {
            if (textRect.width === 0 || textRect.height === 0) continue;
            const fragmentText = textNode.textContent.trim().replace(/\s+/g, " ").slice(0, 100);
            const ownerOverflow = {
              left: Math.max(0, ownerRect.left - textRect.left),
              top: Math.max(0, ownerRect.top - textRect.top),
              right: Math.max(0, textRect.right - ownerRect.right),
              bottom: Math.max(0, textRect.bottom - ownerRect.bottom),
            };
            const cardOverflow = {
              left: Math.max(0, cardRect.left - textRect.left),
              top: Math.max(0, cardRect.top - textRect.top),
              right: Math.max(0, textRect.right - cardRect.right),
              bottom: Math.max(0, textRect.bottom - cardRect.bottom),
            };
            // A single-line ellipsis intentionally keeps the painted text
            // inside its element even though Range reports the unclipped text
            // width. horizontalClipping already records this as a warning;
            // do not duplicate it as a blocking semantic overflow error.
            const textCss = getComputedStyle(textElement);
            const horizontalClip = ["hidden", "clip"].includes(axisOverflow(textCss, "x"));
            const verticalOwnerOverflow = Math.max(ownerOverflow.top, ownerOverflow.bottom);
            const verticalCardOverflow = Math.max(cardOverflow.top, cardOverflow.bottom);
            if (
              horizontalClip
              && verticalOwnerOverflow <= contentOverflowTolerance
              && verticalCardOverflow <= tolerance
            ) continue;
            if (
              Math.max(...Object.values(ownerOverflow)) <= contentOverflowTolerance
              && Math.max(...Object.values(cardOverflow)) <= tolerance
            ) continue;
            result.semanticContentOverflows.push({
              ...describe(owner, ownerRect),
              text: {
                element: {
                  tag: textElement.tagName.toLowerCase(),
                  className: classOf(textElement),
                  text: fragmentText,
                },
                rect: relativeRect(textRect),
              },
              ownerOverflow,
              cardOverflow,
            });
          }
        }
      }
    }
    const requiredCardInset = 12;
    for (const node of semanticNodes) {
      const rect = visibleRect(node);
      const distances = {
        left: rect.left - cardRect.left,
        top: rect.top - cardRect.top,
        right: cardRect.right - rect.right,
        bottom: cardRect.bottom - rect.bottom,
      };
      // Nodes outside Card are already reported by browser-overflow. Avoid
      // emitting a second, less useful safe-area error for the same geometry.
      if (Math.min(...Object.values(distances)) < -tolerance) continue;
      const shortfall = Object.fromEntries(Object.entries(distances).map(
        ([edge, distance]) => [edge, Math.max(0, requiredCardInset - distance)],
      ));
      if (Math.max(...Object.values(shortfall)) <= tolerance) continue;
      result.edgeSpacingViolations.push({
        ...describe(node, rect),
        requiredInset: requiredCardInset,
        distances,
        shortfall,
      });
    }
    result.heightOverflowComponents = result.semanticComponents
      .map((item) => ({
        ...item,
        overflowTop: Math.max(0, -item.rect.y),
        overflowBottom: Math.max(0, item.rect.y + item.rect.height - cardRect.height),
      }))
      .filter((item) => Math.max(item.overflowTop, item.overflowBottom) > tolerance);
    result.resourceElements = Array.from(card.querySelectorAll("[src]")).map((node) => ({
      ...describeNode(node),
      url: node.currentSrc || node.src || node.getAttribute("src") || "",
      alt: node.getAttribute("alt") || "",
    }));
    for (let left = 0; left < semanticNodes.length; left += 1) {
      const leftNode = semanticNodes[left];
      // Use the painted/scrollable extent for overlap checks. Some components
      // (for example TextBlock) keep a narrow border box while fixed-minimum-
      // width children visibly overflow it. Comparing border boxes alone makes
      // that content look non-overlapping to the validator even when it is
      // painted on top of an adjacent semantic component.
      const leftRect = semanticPaintedRects.get(leftNode);
      for (let right = left + 1; right < semanticNodes.length; right += 1) {
        const rightNode = semanticNodes[right];
        if (leftNode.contains(rightNode) || rightNode.contains(leftNode)) continue;
        const rightRect = semanticPaintedRects.get(rightNode);
        const overlapWidth = Math.min(leftRect.right, rightRect.right) - Math.max(leftRect.left, rightRect.left);
        const overlapHeight = Math.min(leftRect.bottom, rightRect.bottom) - Math.max(leftRect.top, rightRect.top);
        if (overlapWidth <= 1.5 || overlapHeight <= 1.5) continue;
        const overlapArea = overlapWidth * overlapHeight;
        const smallerArea = Math.min(leftRect.width * leftRect.height, rightRect.width * rightRect.height);
        const smallerCoverage = smallerArea ? overlapArea / smallerArea : 0;
        if (overlapArea < 16 || smallerCoverage < 0.08) continue;
        result.semanticOverlaps.push({
          first: describe(leftNode, leftRect),
          second: describe(rightNode, rightRect),
          overlap: { width: overlapWidth, height: overlapHeight, area: overlapArea, smallerCoverage },
        });
      }
    }
    return result;
  });
}

function runtimeAssetUrl(value) {
  if (/^(?:[a-z]+:|\/|\.|data:)/i.test(value) || value.includes("/")) return value;
  return `resources/base/media/${value.includes(".") ? value : `${value}.svg`}`;
}

async function browserValidation(previewHtml, screenshotPath, resources) {
  // Resolve the executable before starting the HTTP server. A missing browser
  // must fail immediately instead of leaving the server alive until Python's
  // validator timeout expires.
  const { chromium, executablePath } = loadChromium();
  const serverInfo = await startStaticServer(previewHtml);
  let browser = null;
  let context = null;
  let page = null;
  try {
    const assetBaseUrl = new URL("/", serverInfo.url);
    const allowedUnavailableResources = new Set((resources || []).map((resource) => (
      new URL(runtimeAssetUrl(resource.value), assetBaseUrl).href
    )));
    browser = await chromium.launch({ 
      headless: false,
      executablePath,
    });
    context = await browser.newContext({ viewport: { width: 520, height: 420 }, deviceScaleFactor: 1 });
    page = await context.newPage();
    const runtimeErrors = [];
    const failedRequests = [];
    page.on("console", (message) => {
      const text = message.text();
      if (
        message.type() === "error"
        && !text.includes("favicon.ico")
        && !text.startsWith("Failed to load resource:")
      ) runtimeErrors.push({
        message: text,
        source: "console",
        location: message.location(),
      });
    });
    page.on("pageerror", (error) => runtimeErrors.push({
      message: error.message,
      source: "pageerror",
      stack: error.stack || null,
    }));
    page.on("requestfailed", (request) => {
      if (!allowedUnavailableResources.has(request.url())) {
        failedRequests.push({ url: request.url(), error: request.failure()?.errorText || "failed" });
      }
    });
    page.on("response", (response) => {
      if (response.status() >= 400 && !allowedUnavailableResources.has(response.url())) {
        failedRequests.push({ url: response.url(), status: response.status() });
      }
    });
    await page.goto(serverInfo.url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForFunction(
      () => (
        (typeof window.React !== "undefined"
          && typeof window.ReactDOM !== "undefined"
          && typeof window.Babel !== "undefined")
        || !document.querySelector("#preview-error")?.hidden
      ),
      null,
      { timeout: 15000 },
    );
    await page.waitForFunction(
      () => document.documentElement.dataset.generatedCard === "mounted" || !document.querySelector("#preview-error")?.hidden,
      null,
      { timeout: 15000 },
    );
    await waitForAssets(page);
    const metrics = await inspectBrowserCard(page);
    metrics.failedRequests = failedRequests.map((request) => {
      const owner = metrics.resourceElements.find((resource) => resource.url === request.url);
      return { ...request, ...(owner ? { owner } : {}) };
    });
    if (screenshotPath && metrics.cardCount === 1) {
      fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
      await page.locator(".generated-card-frame").screenshot({ path: screenshotPath, animations: "disabled" });
    }
    return { runtimeErrors, failedRequests, ...metrics };
  } finally {
    if (page) await page.close().catch(() => {});
    if (context) await context.close().catch(() => {});
    if (browser) await browser.close().catch(() => {});
    await new Promise((resolve) => serverInfo.server.close(resolve));
  }
}

function browserFindings(metrics, cardSize) {
  const findings = [];
  const expected = cardSize || CARD_SIZE_PRESETS["2x2"];
  for (const runtimeError of metrics.runtimeErrors || []) {
    const error = typeof runtimeError === "string" ? { message: runtimeError } : runtimeError;
    findings.push(browserFinding(
      "error",
      "browser-runtime",
      `Card 浏览器运行时错误：${error.message || "未知错误"}`,
      {
        component: "Card/runtime",
        evidence: error,
        likelyCause: "生成 JSX、组件属性或 runtime 执行期间抛出了 JavaScript 错误。仅凭浏览器错误不一定能唯一定位组件，应结合 stack 和错误文本检查 JSX。",
        suggestion: "优先按照错误 stack、组件名和属性名修复 JSX；不要通过隐藏出错节点规避运行时错误。",
      },
    ));
  }
  if (metrics.errorPanel) {
    findings.push(browserFinding(
      "error",
      "browser-runtime",
      `Card 预览未正常挂载：${metrics.errorPanel}`,
      {
        component: "Card/runtime",
        evidence: { errorPanel: metrics.errorPanel, mountState: metrics.mountState },
        likelyCause: "React 渲染生成卡片时失败，预览错误面板已显示异常。",
        suggestion: "根据错误面板中的组件名或属性错误修改 JSX，确保 Card 可以独立挂载。",
      },
    ));
  }
  for (const request of metrics.failedRequests || []) {
    const owner = request.owner;
    const label = owner ? diagnosticComponentLabel(owner) : "Card/runtime";
    findings.push(browserFinding(
      "error",
      "browser-resource-request",
      `${label} 请求资源失败：${request.url}`,
      {
        component: owner?.component || "Card/runtime",
        ...(owner?.componentText ? { componentText: owner.componentText } : {}),
        evidence: request,
        likelyCause: owner
          ? "该组件使用的 src 无法由浏览器加载，可能是资源路径错误、文件缺失或资源服务不可达。"
          : "浏览器请求失败，但当前 DOM 中没有找到使用该 URL 的具体组件，可能是 runtime 或样式资源。",
        suggestion: owner
          ? "将该组件的资源属性改为输入 assetCandidates 中存在且可访问的 src。"
          : "检查失败 URL 的来源；如果属于组件资源，请使用输入 assetCandidates 提供的完整 src。",
      },
    ));
  }
  if (metrics.cardCount !== 1) findings.push(browserFinding(
    "error",
    "browser-card-count",
    `预期渲染 1 个 Card，实际找到 ${metrics.cardCount} 个`,
    {
      component: "Card",
      evidence: { expectedCount: 1, actualCount: metrics.cardCount },
      likelyCause: metrics.cardCount === 0
        ? "生成函数没有成功返回可挂载的 Card，或渲染过程提前失败。"
        : "生成函数返回了多个 Card 根节点。",
      suggestion: "确保生成函数只返回一个 Card 根组件。",
    },
  ));
  if (metrics.card && (Math.abs(metrics.card.width - expected.width) > 0.25 || Math.abs(metrics.card.height - expected.height) > 0.25)) {
    findings.push(browserFinding(
      "error",
      "browser-card-size",
      `Card 实际尺寸为 ${rounded(metrics.card.width)}×${rounded(metrics.card.height)}vp，${expected.token} 规格应为 ${expected.width}×${expected.height}vp`,
      {
        component: "Card",
        evidence: {
          expected: { size: expected.token, width: expected.width, height: expected.height },
          actual: metrics.card,
          delta: {
            width: rounded(metrics.card.width - expected.width),
            height: rounded(metrics.card.height - expected.height),
          },
        },
        likelyCause: "Card 的 size 与任务 size 不一致，或 JSX 样式覆盖了 runtime 的固定卡片尺寸。",
        suggestion: `使用 <Card size="${expected.token}">，不要通过 style、width 或 height 覆盖 Card 的 ${expected.width}×${expected.height}vp 固定尺寸。`,
      },
    ));
  }
  if (metrics.card && metrics.card.scrollHeight > metrics.card.clientHeight + 1) {
    const offenders = (metrics.heightOverflowComponents || []).slice(0, 4);
    findings.push(browserFinding(
      "error",
      "browser-height-overflow",
      `Card 内容需要 ${metrics.card.scrollHeight}vp 高度，但可用高度只有 ${metrics.card.clientHeight}vp，纵向超出 ${metrics.card.scrollHeight - metrics.card.clientHeight}vp`,
      {
        component: "Card",
        evidence: {
          availableHeight: metrics.card.clientHeight,
          requiredHeight: metrics.card.scrollHeight,
          overflowHeight: metrics.card.scrollHeight - metrics.card.clientHeight,
          offendingComponents: offenders,
        },
        likelyCause: offenders.length
          ? `靠近或超出卡片底部的组件包括：${offenders.map(diagnosticComponentLabel).join("、")}。内容总高度、固定 height/basis 或纵向 gap 超出了 Card 高度。`
          : "内容总高度、固定 height/basis 或纵向 gap 超出了 Card 高度，但浏览器未能唯一定位某个语义组件。",
        suggestion: "优先调整父级 Stack 的 flex、height/basis 和纵向 gap，或重新分组内容；不要依靠 overflow、裁剪或压缩固定尺寸组件。",
      },
    ));
  }
  for (const item of strongestDiagnostics(metrics.outsideBounds, (entry) => Math.max(...Object.values(entry.overflow)))) {
    const directions = Object.entries(item.overflow)
      .filter(([, value]) => value > 0.75)
      .map(([direction, value]) => `${direction} ${rounded(value)}vp`)
      .join("、");
    const label = diagnosticComponentLabel(item);
    findings.push(browserFinding(
      "error",
      "browser-overflow",
      `${label} 超出 Card 边界：${directions}`,
      {
        component: item.component || "未知 DOM 节点",
        ...(item.componentText ? { componentText: item.componentText } : {}),
        evidence: item,
        likelyCause: "组件的固定尺寸、绝对定位，或父级 Stack/Grid 分配的空间与组件实际尺寸不兼容。",
        suggestion: "根据 overflow 方向检查该组件及父级容器的 width/height、basis、flex、position 和 gap，保证组件完整位于 Card 安全区内。",
      },
    ));
  }
  for (const item of strongestDiagnostics(metrics.edgeSpacingViolations, (entry) => Math.max(...Object.values(entry.shortfall)))) {
    const maximumShortfall = Math.max(...Object.values(item.shortfall));
    // Browser flex/text layout commonly introduces sub-pixel rounding around a
    // nominal 12vp inset. Keep 10-12vp visible in diagnostics, but only make a
    // clearly smaller inset block generation.
    const severity = maximumShortfall > 2 ? "error" : "warning";
    const edges = Object.entries(item.shortfall)
      .filter(([, value]) => value > 0.75)
      .map(([edge]) => `${edge} ${rounded(item.distances[edge])}vp`)
      .join("、");
    const label = diagnosticComponentLabel(item);
    findings.push(browserFinding(
      severity,
      "browser-edge-spacing",
      `${label} 距离 Card 边缘不足 12vp：${edges}`,
      {
        component: item.component || "未知 DOM 节点",
        ...(item.componentText ? { componentText: item.componentText } : {}),
        evidence: item,
        likelyCause: "组件位置、尺寸或父级布局占用了 Card 的 12vp 安全内边距。",
        suggestion: "调整父级 Stack/Grid 的 padding、width、height、basis、flex 或定位，使组件四边均位于 Card 的 12vp 安全区内。",
      },
    ));
  }
  for (const item of strongestDiagnostics(metrics.verticalClipping, (entry) => entry.requiredSize.height - entry.availableSize.height)) {
    const missing = item.requiredSize.height - item.availableSize.height;
    const label = diagnosticComponentLabel(item);
    findings.push(browserFinding(
      "error",
      "browser-vertical-clipping",
      `${label} 需要 ${item.requiredSize.height}vp 高度，但当前只有 ${item.availableSize.height}vp，纵向裁剪 ${missing}vp`,
      {
        component: item.component || "未知 DOM 节点",
        ...(item.componentText ? { componentText: item.componentText } : {}),
        evidence: item,
        likelyCause: "内容发生换行或组件高度增长，但自身或父级容器仍限制为更小的固定高度，并设置了 hidden/clip。",
        suggestion: "增加该组件或父级 Stack 的可用高度，或减少相邻内容和 gap；不要依靠 overflow hidden/clip 隐藏必需内容。",
      },
    ));
  }
  for (const item of strongestDiagnostics(metrics.visibleHorizontalOverflow, (entry) => entry.requiredSize.width - entry.availableSize.width)) {
    const missing = item.requiredSize.width - item.availableSize.width;
    const label = diagnosticComponentLabel(item);
    const rejectsTruncation = item.component === "TopTextBottomValue";
    findings.push(browserFinding(
      rejectsTruncation ? "error" : "warning",
      "browser-visible-horizontal-overflow",
      `${label} 内容宽度 ${item.requiredSize.width}vp 超出可用宽度 ${item.availableSize.width}vp（超出 ${missing}vp）`,
      {
        component: item.component || "未知 DOM 节点",
        ...(item.componentText ? { componentText: item.componentText } : {}),
        evidence: item,
        likelyCause: rejectsTruncation
          ? "TopTextBottomValue 要求每项完整单行显示，但当前 items 的自然宽度总和超过父级可用宽度。"
          : "组件内容为单行或含固定宽度子项，而父级分配宽度不足。",
        suggestion: rejectsTruncation
          ? "减少或重新分组 TopTextBottomValue.items，或改用更适合密集信息的组件；不得依赖压缩、裁剪或省略号。"
          : "检查父级 width/basis/flex；若组件规范允许换行，应提供足够高度并允许换行。",
      },
    ));
  }
  for (const overlap of metrics.semanticOverlaps || []) {
    const firstLabel = diagnosticComponentLabel(overlap.first);
    const secondLabel = diagnosticComponentLabel(overlap.second);
    const vertical = overlap.overlap.height <= overlap.overlap.width;
    findings.push(browserFinding(
      "error",
      "browser-semantic-overlap",
      `${firstLabel} 与 ${secondLabel} 发生重叠，重叠区域约 ${rounded(overlap.overlap.width)}×${rounded(overlap.overlap.height)}vp`,
      {
        components: [overlap.first.component, overlap.second.component],
        componentTexts: [overlap.first.componentText, overlap.second.componentText],
        evidence: overlap,
        likelyCause: `${vertical ? "纵向" : "横向"}槽位、gap、固定尺寸或绝对定位不足以容纳这两个独立组件。`,
        suggestion: `调整两个组件共同父级的 ${vertical ? "height/basis、flex 或纵向 gap" : "width/basis、flex 或横向 gap"}，使其矩形不再相交；不要通过隐藏其中一个必需组件规避问题。`,
      },
    ));
  }
  for (const item of strongestDiagnostics(metrics.semanticContentOverflows, (entry) => Math.max(
    ...Object.values(entry.ownerOverflow || {}),
    ...Object.values(entry.cardOverflow || {}),
  ))) {
    const label = diagnosticComponentLabel(item);
    const outsideCard = Math.max(...Object.values(item.cardOverflow || {})) > 0.75;
    findings.push(browserFinding(
      "error",
      "browser-semantic-content-overflow",
      `${label} 内文字“${item.text.element.text}”${outsideCard ? "超出 Card 边界" : "超出组件可见区域"}`,
      {
        component: item.component || "未知组件",
        ...(item.componentText ? { componentText: item.componentText } : {}),
        evidence: item,
        likelyCause: "父级 flex/grid 将组件高度压缩到不足以容纳内部文字，或文字换行后组件仍使用过小的固定高度。",
        suggestion: "增加组件及父级槽位的可用高度、减少同槽内容，或重新分组；不要依赖 flex shrink、overflow 或 Card 裁剪隐藏必需文字。",
      },
    ));
  }
  for (const item of strongestDiagnostics(metrics.horizontalClipping, (entry) => entry.requiredSize.width - entry.availableSize.width)) {
    const missing = item.requiredSize.width - item.availableSize.width;
    const label = diagnosticComponentLabel(item);
    findings.push(browserFinding(
      "warning",
      "browser-horizontal-clipping",
      `${label} 内容宽度 ${item.requiredSize.width}vp，当前仅显示 ${item.availableSize.width}vp，横向裁剪 ${missing}vp`,
      {
        component: item.component || "未知 DOM 节点",
        ...(item.componentText ? { componentText: item.componentText } : {}),
        evidence: item,
        likelyCause: "文字或内部内容超过组件宽度，并被 overflow hidden/clip 或 ellipsis 截断。",
        suggestion: "确认截断是否符合组件规范；如果不是，请增加父级可用宽度、调整布局分栏或使用允许换行的组件。",
      },
    ));
  }
  return findings;
}

function loadTask(taskPath, taskId) {
  if (!taskPath) return null;
  const payload = JSON.parse(fs.readFileSync(taskPath, "utf8"));
  let tasks = [payload];
  if (Array.isArray(payload)) tasks = payload;
  else if (Array.isArray(payload?.tasks)) tasks = payload.tasks;
  if (taskId !== null) {
    const task = tasks.find((item) => String(item?.id) === taskId);
    if (!task) throw new Error(`cannot find task id ${taskId} in ${taskPath}`);
    return task;
  }
  if (tasks.length !== 1) throw new Error("--task-id is required when --task contains multiple tasks");
  return tasks[0];
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  let input;
  if (options.stdin) input = await readStdin();
  else if (options.input) input = parseInputPayload(fs.readFileSync(options.input, "utf8"), "--input");
  else {
    input = {
      source: fs.readFileSync(options.jsx, "utf8"),
      task: loadTask(options.task, options.taskId),
    };
  }
  const normalized = normalizeInputSource(input.source, input.componentName);
  const schema = runtimeSchema();
  const findings = [];
  if (normalized.parseError) findings.push(finding("error", "jsx-parse", normalized.parseError));
  let structural = { root: null, signature: null, findings: [], cardSize: null };
  if (!normalized.parseError) {
    structural = validateStructure(normalized.source, normalized.componentName, schema, input.task);
    findings.push(...structural.findings);
    findings.push(...validateResources(structural.signature, input.task));
    findings.push(...validateDuplicateActions(structural.signature, input.task));
  }

  let browser = null;
  if (options.browser && !findings.some((item) => item.severity === "error")) {
    const preview = htmlPreview(normalized.source, normalized.componentName, schema.runtimeSource);
    browser = await browserValidation(
      preview,
      options.screenshot || input.screenshot || null,
      structural.signature?.resources || [],
    );
    findings.push(...browserFindings(browser, structural.cardSize));
  }
  const result = {
    ok: !findings.some((item) => item.severity === "error"),
    kind: "validation",
    componentName: normalized.componentName || null,
    findings,
    browser,
  };
  const output = JSON.stringify(result, null, 2) + "\n";
  if (options.report) {
    fs.mkdirSync(path.dirname(options.report), { recursive: true });
    fs.writeFileSync(options.report, output);
  }
  process.stdout.write(output);
  process.exitCode = result.ok ? 0 : 1;
}

main().catch((error) => {
  const result = {
    ok: false,
    kind: "infrastructure",
    findings: [finding("error", "validator-infrastructure", `${error.name || "Error"}: ${error.message}`)],
  };
  const output = JSON.stringify(result, null, 2) + "\n";
  const reportIndex = process.argv.indexOf("--report");
  const reportArgument = reportIndex >= 0 ? process.argv[reportIndex + 1] : null;
  if (reportArgument) {
    const reportPath = path.resolve(reportArgument);
    fs.mkdirSync(path.dirname(reportPath), { recursive: true });
    fs.writeFileSync(reportPath, output);
  }
  process.stdout.write(output);
  process.exitCode = 2;
});
