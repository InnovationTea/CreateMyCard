/**
 * v0.9 protocol → graph command normalization + JsonlStreamParser smoke test.
 * Run: npx tsx parser/test-v09.ts
 */

import { UIGraph, CREATE_SURFACE_CMD_KEY, UPDATE_DATA_MODEL_CMD_KEY } from "@genui-sdk/graph";
import { JsonlStreamParser, tryNormalizeV09Protocol, UPDATE_DATA_MODEL_KEY } from "./src/index.js";

function assert(cond: boolean, msg: string) {
  if (!cond) {
    console.error("FAIL:", msg);
    process.exit(1);
  }
  console.log("ok:", msg);
}

// Direct normalization
const cs = tryNormalizeV09Protocol({
  version: "v0.9",
  createSurface: { surfaceId: "main" },
});
assert(
  cs !== null &&
    CREATE_SURFACE_CMD_KEY in cs &&
    (cs as { __createSurface: { surfaceId: string } }).__createSurface.surfaceId === "main",
  "createSurface → __createSurface",
);

const uc = tryNormalizeV09Protocol({
  version: "v0.9",
  updateComponents: {
    surfaceId: "main",
    component: {
      id: "root",
      component: "Extended.Column",
      children: ["a", "b"],
      space: 12,
      styles: { width: 100, height: 200 },
    },
  },
});
assert(
  uc !== null && !Array.isArray(uc) && "root" in uc,
  "updateComponents has root key",
);
const rootCmd = uc as { root: { type: string; props: Record<string, unknown>; children: string[] } };
assert(rootCmd.root.type === "Extended.Column", "type Extended.Column");
assert(rootCmd.root.children.length === 2, "children length");
assert(rootCmd.root.props.space === 12, "space in props");
assert((rootCmd.root.props.styles as { width: number }).width === 100, "nested styles");

// Batch normalization (components[])
const ucs = tryNormalizeV09Protocol({
  version: "v0.9",
  updateComponents: {
    surfaceId: "main",
    components: [
      { id: "h1", component: "Extended.Text", content: "hello", styles: {} },
      { id: "h2", component: "Extended.Text", content: "world", styles: {} },
    ],
  },
});
assert(
  ucs !== null && Array.isArray(ucs) && ucs.length === 2,
  "updateComponents components[] → 2 commands",
);
const cmd0 = ucs as Array<Record<string, unknown>>;
assert("h1" in cmd0[0]!, "first command has h1");
assert("h2" in cmd0[1]!, "second command has h2");

assert(UPDATE_DATA_MODEL_KEY === UPDATE_DATA_MODEL_CMD_KEY, "parser + graph use same updateDataModel cmd key");

const udm = tryNormalizeV09Protocol({
  version: "v0.9",
  updateDataModel: { surfaceId: "main", path: "/card/title", value: "Hello" },
});
assert(
  udm !== null &&
    !Array.isArray(udm) &&
    UPDATE_DATA_MODEL_CMD_KEY in udm &&
    (udm as Record<string, { surfaceId: string; path: string; value: string }>)[UPDATE_DATA_MODEL_CMD_KEY]
      .surfaceId === "main" &&
    (udm as Record<string, { path: string; value: string }>)[UPDATE_DATA_MODEL_CMD_KEY].path === "/card/title" &&
    (udm as Record<string, { value: string }>)[UPDATE_DATA_MODEL_CMD_KEY].value === "Hello",
  "updateDataModel → __updateDataModel",
);

const udmValueOmitted = tryNormalizeV09Protocol({
  version: "v0.9",
  updateDataModel: { surfaceId: "main", path: "/x" },
});
assert(
  udmValueOmitted !== null &&
    !Array.isArray(udmValueOmitted) &&
    !Object.prototype.hasOwnProperty.call(
      (udmValueOmitted as Record<string, Record<string, unknown>>)[UPDATE_DATA_MODEL_CMD_KEY]!,
      "value",
    ),
  "updateDataModel without value key omits value in payload",
);

assert(
  tryNormalizeV09Protocol({
    version: "v0.9",
    createSurface: { surfaceId: "a" },
    updateDataModel: { surfaceId: "a", path: "/p", value: 1 },
  }) === null,
  "reject v0.9 object mixing createSurface and updateDataModel",
);

assert(
  tryNormalizeV09Protocol({
    version: "v0.9",
    updateDataModel: { surfaceId: "main", path: "/x" },
    note: "extra",
  } as Record<string, unknown>) === null,
  "reject updateDataModel with extra top-level keys",
);

// Parser stream
const lines = [
  '{"version":"v0.9","createSurface":{"surfaceId":"main"}}',
  '{"version":"v0.9","updateComponents":{"surfaceId":"main","component":{"id":"root","component":"Extended.Text","content":"hi","styles":{}}}}',
  '{"version":"v0.9","updateComponents":{"surfaceId":"main","components":[{"id":"a","component":"Extended.Text","content":"A","styles":{}},{"id":"b","component":"Extended.Text","content":"B","styles":{}}]}}',
  '{"version":"v0.9","updateDataModel":{"surfaceId":"main","path":"/card/title","value":"From model"}}',
];
const graph = new UIGraph();
graph.applyCommand({ x: { type: "Text", props: { content: "old" } } });
assert(graph.size === 1, "seed graph");

let count = 0;
const parser = new JsonlStreamParser<Record<string, unknown>>({
  onMessage: (obj) => {
    count++;
    graph.applyCommand(obj);
  },
});
for (const line of lines) {
  parser.push(line);
}
parser.end();

assert(count === 5, "five messages (createSurface + component + 2x batch + updateDataModel)");
assert(graph.getRoot()?.id === "root", "root id after createSurface reset + root node");
assert(graph.getNode("root")?.type === "Extended.Text", "Extended.Text type");
assert((graph.getNode("root")?.props.content as string) === "hi", "content prop");
assert(graph.getNode("a")?.type === "Extended.Text", "batch node a type");
assert(graph.getNode("b")?.type === "Extended.Text", "batch node b type");
assert(graph.getActiveSurfaceId() === "main", "active surface id from createSurface");
assert(graph.getDataModelValue("main", "/card/title") === "From model", "data model path value");

console.log("\nAll v0.9 tests passed.");
