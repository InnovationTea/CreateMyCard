import path from "node:path";
import { fileURLToPath } from "node:url";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
export default {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(__dirname, ".."),
  experimental: { externalDir: true },
  webpack(config) {
    config.resolve.extensionAlias = { ...config.resolve.extensionAlias, ".js": [".ts", ".tsx", ".js"], ".mjs": [".mts", ".mjs"] };
    for (const pkg of ["parser", "graph", "components", "renderer", "interactions"]) {
      config.resolve.alias["@genui-sdk/" + pkg] = path.join(__dirname, "../genui-sdk/" + pkg + "/src/index.ts");
    }
    return config;
  },
};
