import { constants as fsConstants } from 'node:fs';
import { access, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, '../../../..');
const runtimeRoot = path.resolve(scriptDirectory, '..');
const upstreamRoot = path.join(repositoryRoot, 'render/genui-sdk');
const packages = ['graph', 'parser', 'components', 'interactions', 'renderer'];

async function listFiles(directory, prefix = '') {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
    const relativePath = prefix ? path.posix.join(prefix, entry.name) : entry.name;
    if (entry.isDirectory()) {
      files.push(...await listFiles(path.join(directory, entry.name), relativePath));
    } else if (entry.isFile()) {
      files.push(relativePath);
    }
  }
  return files;
}

async function fileExists(filePath) {
  try {
    await access(filePath, fsConstants.F_OK);
    return true;
  } catch {
    return false;
  }
}

function applyLocalAdaptations(packageName, relativePath, source) {
  if (packageName !== 'components' || relativePath !== 'extended/ExtendedMedia.tsx') {
    return source;
  }

  const content = source.toString('utf8');
  const newline = content.includes('\r\n') ? '\r\n' : '\n';
  const proxyDocumentationLine = content.indexOf(' * Rewrites external http(s) image URLs');
  const proxyDocumentationStart = proxyDocumentationLine < 0
    ? -1 : content.lastIndexOf('/**', proxyDocumentationLine);
  const imageFunctionStart = content.indexOf('export function ExtendedImage', proxyDocumentationStart);
  if (proxyDocumentationStart < 0 || imageFunctionStart < 0) {
    throw new Error('无法从上游 ExtendedMedia 定位 /img-proxy 适配块');
  }
  const withoutProxyFunction =
    content.slice(0, proxyDocumentationStart) + content.slice(imageFunctionStart);
  const upstreamSourceLine =
    '  const source = toProxyUrl(src.startsWith("resources/") ? `/${src}` : src);';
  const debugSourceLines = [
    '  // Debug Tools deliberately does not expose the Next.js /img-proxy endpoint:',
    '  // external images remain browser-direct, while repository assets use /resources/.',
    '  const source = src.startsWith("resources/") ? `/${src}` : src;',
  ].join(newline);
  if (!withoutProxyFunction.includes(upstreamSourceLine)) {
    throw new Error('无法从上游 ExtendedMedia 定位 toProxyUrl 调用');
  }
  return Buffer.from(withoutProxyFunction.replace(upstreamSourceLine, debugSourceLines));
}

async function comparePackage(packageName) {
  const sourceDirectory = path.join(upstreamRoot, packageName, 'src');
  const targetDirectory = path.join(runtimeRoot, packageName, 'src');
  const sourceFiles = await listFiles(sourceDirectory);
  const targetFiles = await listFiles(targetDirectory);
  const sourceSet = new Set(sourceFiles);
  const problems = [];

  for (const relativePath of sourceFiles) {
    const targetPath = path.join(targetDirectory, relativePath);
    if (!await fileExists(targetPath)) {
      problems.push(`${packageName}: 缺少 ${relativePath}`);
      continue;
    }
    const [rawSource, target] = await Promise.all([
      readFile(path.join(sourceDirectory, relativePath)),
      readFile(targetPath),
    ]);
    const source = applyLocalAdaptations(packageName, relativePath, rawSource);
    if (!source.equals(target)) problems.push(`${packageName}: 内容漂移 ${relativePath}`);
  }

  for (const relativePath of targetFiles) {
    if (!sourceSet.has(relativePath)) problems.push(`${packageName}: 多余 ${relativePath}`);
  }
  return problems;
}

async function verifyExtendedMediaOverride() {
  const overridePath = path.join(
    runtimeRoot,
    'components/src/extended/ExtendedMedia.tsx',
  );
  const content = await readFile(overridePath, 'utf8');
  const problems = [];
  if (content.includes('/img-proxy/')) {
    problems.push('components: ExtendedMedia 不得依赖 Next.js /img-proxy');
  }
  if (!content.includes('src.startsWith("resources/")')) {
    problems.push('components: ExtendedMedia 必须保留 resources/ 本地素材适配');
  }
  return problems;
}

async function checkRuntime() {
  const problems = [];
  for (const packageName of packages) {
    problems.push(...await comparePackage(packageName));
  }
  problems.push(...await verifyExtendedMediaOverride());
  if (problems.length > 0) {
    for (const problem of problems) process.stderr.write(`- ${problem}\n`);
    throw new Error('Debug Tools Renderer Runtime 与 render/genui-sdk 不一致');
  }
  process.stdout.write('Renderer Runtime 已与 render/genui-sdk 对齐（保留 ExtendedMedia 本地适配）。\n');
}

async function syncPackage(packageName) {
  const sourceDirectory = path.join(upstreamRoot, packageName, 'src');
  const targetDirectory = path.join(runtimeRoot, packageName, 'src');
  const sourceFiles = await listFiles(sourceDirectory);
  const targetFiles = await listFiles(targetDirectory);
  const sourceSet = new Set(sourceFiles);

  for (const relativePath of sourceFiles) {
    const targetPath = path.join(targetDirectory, relativePath);
    await mkdir(path.dirname(targetPath), { recursive: true });
    const source = await readFile(path.join(sourceDirectory, relativePath));
    await writeFile(targetPath, applyLocalAdaptations(packageName, relativePath, source));
  }

  for (const relativePath of targetFiles) {
    if (!sourceSet.has(relativePath)) await rm(path.join(targetDirectory, relativePath));
  }
}

async function main() {
  const mode = process.argv[2] ?? '--check';
  if (mode === '--sync') {
    for (const packageName of packages) await syncPackage(packageName);
  } else if (mode !== '--check') {
    throw new Error(`未知参数 ${mode}；只支持 --check 或 --sync`);
  }
  await checkRuntime();
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
