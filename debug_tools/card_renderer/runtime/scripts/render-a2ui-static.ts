import { readFileSync } from 'node:fs';

type RuntimeGraph = {
  applyCommand: (command: Record<string, unknown>) => void;
  getRoot: () => unknown;
};

type RuntimeGraphConstructor = new () => RuntimeGraph;

type RuntimeParser = {
  push: (source: string) => void;
  end: () => void;
};

type RuntimeParserConstructor = new (options: {
  onMessage: (command: Record<string, unknown>) => void;
  onParseError: (raw: string, error: unknown) => void;
}) => RuntimeParser;

type RuntimeModules = {
  Graph: RuntimeGraphConstructor;
  Parser: RuntimeParserConstructor;
  registry: Record<string, unknown>;
  renderTree: (
    graph: RuntimeGraph,
    registry: Record<string, unknown>,
  ) => unknown;
  renderToStaticMarkup: (tree: never) => string;
};

async function loadRuntime(runtime: string): Promise<RuntimeModules> {
  const react = await import('react');
  const reactDomServer = await import('react-dom/server');
  // SDK 源码仍有 classic JSX；独立进程不像 Vite 那样自动注入 React。
  Object.assign(globalThis, { React: react.default });
  if (runtime === 'debug') {
    const graph = await import('../graph/src/graph.ts');
    const parser = await import('../parser/src/parser.ts');
    const renderer = await import('../renderer/src/index.ts');
    return {
      Graph: graph.UIGraph as RuntimeGraphConstructor,
      Parser: parser.JsonlStreamParser as RuntimeParserConstructor,
      registry: renderer.defaultRegistry,
      renderTree: renderer.renderTree,
      renderToStaticMarkup: reactDomServer.renderToStaticMarkup,
    } as RuntimeModules;
  }
  if (runtime === 'platform') {
    const graph = await import('../../../../render/genui-sdk/graph/src/graph.ts');
    const parser = await import('../../../../render/genui-sdk/parser/src/parser.ts');
    const renderer = await import('../../../../render/genui-sdk/renderer/src/index.ts');
    return {
      Graph: graph.UIGraph as RuntimeGraphConstructor,
      Parser: parser.JsonlStreamParser as RuntimeParserConstructor,
      registry: renderer.defaultRegistry,
      renderTree: renderer.renderTree,
      renderToStaticMarkup: reactDomServer.renderToStaticMarkup,
    } as RuntimeModules;
  }
  throw new Error(`未知 Renderer Runtime：${runtime}`);
}

async function main(): Promise<void> {
  const runtimeName = process.argv[2];
  const fixturePath = process.argv[3];
  if (!runtimeName || !fixturePath) {
    throw new Error('用法：render-a2ui-static.ts <debug|platform> <a2ui.jsonl>');
  }

  const runtime = await loadRuntime(runtimeName);
  const graph = new runtime.Graph();
  const parseErrors: string[] = [];
  const parser = new runtime.Parser({
    onMessage: command => graph.applyCommand(command),
    onParseError: (raw, error) => {
      parseErrors.push(`${String(error)}\n${raw}`);
    },
  });
  parser.push(readFileSync(fixturePath, 'utf8'));
  parser.end();
  if (parseErrors.length > 0) {
    throw new Error(parseErrors.join('\n'));
  }
  if (!graph.getRoot()) {
    throw new Error(`A2UI fixture 没有根组件：${fixturePath}`);
  }

  const tree = runtime.renderTree(graph, runtime.registry);
  process.stdout.write(runtime.renderToStaticMarkup(tree as never));
}

main().catch((error: unknown) => {
  process.stderr.write(`${String(error)}\n`);
  process.exitCode = 1;
});
