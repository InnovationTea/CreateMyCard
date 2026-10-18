import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  detectExpectPayload, getExpectOptions, getExpectSample, getExpectSampleIds,
  importExpectBatch, updateExpectSample,
  type ExpectDetection, type ExpectImportSample, type ExpectOption, type ExpectOptions,
  type ExpectPurpose, type ExpectFingerprint, type ExpectSampleId,
} from '../batchApi';
import { TokenPicker } from '../components/TokenPicker';

const EMPTY_OPTIONS: ExpectOptions = { data: [], actions: [], icons: [] };
/** 识别结果按三个维度都存在才有意义；后端指纹里 icons 可选，页面里统一收紧成必填。 */
type DetectedFingerprint = Record<'data' | 'actions' | 'icons', string[]>;
const EMPTY_FINGERPRINT: DetectedFingerprint = { data: [], actions: [], icons: [] };

/**
 * 批次名由导入时间自动生成，页面不让人填：它只用于「期望数据画廊」按批次分组、看来源与整批删除，
 * 对比页不按批次筛选，没有需要人工命名的场景。
 */
function defaultBatchName(purpose: ExpectPurpose): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, '0');
  const prefix = purpose === 'actual' ? '实际导入' : '期望导入';
  return `${prefix} · ${now.getFullYear()}/${pad(now.getMonth() + 1)}/${pad(now.getDate())}`
    + ` ${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

const MAX_BYTES = 64 * 1024 * 1024;
/** 协议只承认这两种尺寸；其它声明一律拒绝，缺失时由后端按 DSL（＋截图）判定。 */
const LEGAL_SIZES = ['2x2', '2x4'];
/** 预置数据分类；允许自定义，随批次落盘并在对比页用于筛选。 */
const PRESET_CATEGORIES = ['天气', '电量', '日程', '音乐', '运动', '健康', '待办', '通用'];
const CUSTOM_CATEGORY = '__custom__';

/** 导入页挂在期望对比、期望画廊与质量评分下，落地位置和按钮语义由入口决定。 */
export type ExpectImportOrigin = 'expect' | 'quality' | 'gallery';

/**
 * 拖进来的文件夹会被浏览器当成一条「文件」交给我们：没有扩展名、体积 0、没有 MIME 类型，
 * 读它只会得到系统级报错（如 Windows 的"找不到文件"）。这里先拦下来，换成能照做的话。
 */
function assertSelectableFile(file: File) {
  if (file.size === 0 && !file.type && !/\.[A-Za-z0-9]+$/.test(file.name)) {
    throw new Error(`「${file.name}」是文件夹而不是文件：请点开它选里面的文件，`
      + '或改用「批量：整个文件夹」');
  }
}

async function fileText(file: File) {
  assertSelectableFile(file);
  try {
    // 保留 UTF-8 BOM 与换行字节，避免旧清单的 SHA-256 因浏览器解码而失配。
    return new TextDecoder('utf-8', { fatal: true, ignoreBOM: true })
      .decode(await file.arrayBuffer());
  } catch (reason) {
    throw new Error(`无法读取「${file.name}」：${reasonText(reason)}`);
  }
}

function stripBom(text: string) {
  return text.replace(/^\uFEFF/, '');
}

function imageData(file: File): Promise<string> {
  assertSelectableFile(file);
  if (file.size > 8 * 1024 * 1024) throw new Error('单张截图不能超过 8 MiB');
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(new Error('图片读取失败'));
    reader.readAsDataURL(file);
  });
}

type ManifestRow = {
  /** ID／Query／截图／CardSpec 都可以省略：真实输出常常只有一份 DSL。 */
  id?: string; query?: string; size?: string; dsl: string; image?: string;
  cardspec?: string;
  expectedIntents?: string[];
  expectedData?: string[]; expectedActions?: string[]; expectedIcons?: string[];
  category?: string;
  sourceSha256?: string; imageSha256?: string;
};

function declaredSize(value: unknown, sampleId: string): string | undefined {
  const size = String(value ?? '').trim();
  if (!size) return undefined;
  if (!LEGAL_SIZES.includes(size)) {
    throw new Error(`样本 ${sampleId} 声明了 ${size}；协议只有 2x2 与 2x4，请按最接近的一种声明`);
  }
  return size;
}

/**
 * 批量导入时只看结构判断一份内容是 genui DSL 还是 CardSpec，不看文件名。
 *
 * 规则与后端 `/debug/expect/detect`（`expect_compare.detect_payload`）一致：带数据绑定／
 * 规格字段而没有组件树字段的 JSON 对象是 CardSpec，其余能解析成 JSON／JSONL 的都按 DSL 处理。
 * 这里只决定「文件放哪个位置」，指纹与需求项一律由后端在导入与比对时重新提取；
 * 逐条调识别接口会让一次 500 条的导入产生 500 个请求，不值得。
 */
const SPEC_KEYS = ['dataBindings', 'suggestSize', 'capabilityId', 'writeResultTo',
  'candidateAssetIds', 'assets', 'imageDomainWhitelist', 'interactions', 'events'];
const GENUI_KEYS = ['component', 'components', 'createSurface', 'updateComponents',
  'updateDataModel', 'children', 'layout', 'root', 'surfaceId'];
export type PayloadKind = 'cardspec' | 'dsl' | 'empty' | 'unknown';

function classifyObject(value: unknown): PayloadKind {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return 'dsl';
  const keys = Object.keys(value as Record<string, unknown>);
  const hasSpec = SPEC_KEYS.some((key) => keys.includes(key));
  const hasGenui = GENUI_KEYS.some((key) => keys.includes(key));
  return hasSpec && !hasGenui ? 'cardspec' : 'dsl';
}

export function classifyContentText(text: string): PayloadKind {
  const raw = stripBom(text).trim();
  if (!raw) return 'empty';
  try {
    return classifyObject(JSON.parse(raw));
  } catch {
    // 多行 JSONL 不是合法的单篇 JSON：退回去看第一条能解析的行。
  }
  for (const line of raw.split('\n')) {
    if (!line.trim()) continue;
    try {
      return classifyObject(JSON.parse(line));
    } catch {
      // 继续找。
    }
  }
  return 'unknown';
}

/**
 * 一份内容是否真的像 genui DSL：数据集目录里常混着说明文档、交付清单与渲染脚本输入，
 * 它们同样能被 JSON.parse 接受，但不该变成一条以文件名当样本 ID 的假样本。
 * 认 genui 的两种形态：含 `version`／组件树字段的对象，或 `["id", "Component", {…}]` 行。
 */
const GENUI_HINTS = ['version', 'createSurface', 'updateComponents', 'updateDataModel',
  'components', 'component', 'children', 'layout', 'root', 'surfaceId'];

function looksLikeGenui(text: string): boolean {
  /** 一行 genui：紧凑行 `["id", "Component", {…}]`，或带组件树／version 字段的对象。 */
  const rowIsGenui = (value: unknown) => {
    if (Array.isArray(value)) {
      return value.length >= 2 && typeof value[0] === 'string' && typeof value[1] === 'string';
    }
    if (!value || typeof value !== 'object') return false;
    const keys = Object.keys(value as Record<string, unknown>);
    // 空对象形态不明，按兼容处理；有字段时才要求命中组件树／version 特征。
    return keys.length === 0 || keys.some((key) => GENUI_HINTS.includes(key));
  };
  const check = (value: unknown) => {
    if (Array.isArray(value)) {
      if (typeof value[0] === 'string' && typeof value[1] === 'string') return true;
      // 空数组与 `[]` 这类占位内容形态不明，交给后端按尺寸与指纹判，不当辅助文件忽略。
      if (!value.length) return true;
      // 整篇数组：每个元素都得像一行 genui（交付清单那种 {id,file} 数组会被排除）。
      return value.length > 0 && value.every((item) => rowIsGenui(item));
    }
    return rowIsGenui(value);
  };
  const raw = stripBom(text).trim();
  if (!raw) return false;
  try {
    return check(JSON.parse(raw));
  } catch {
    // 多行 JSONL：任意一行像 genui 就算。
  }
  for (const line of raw.split('\n')) {
    if (!line.trim()) continue;
    try {
      if (check(JSON.parse(line))) return true;
    } catch {
      // 继续找。
    }
  }
  return false;
}

/**
 * 同一主干有多张截图时取哪一张：只看路径，不认目录名（目录叫什么都行）。
 * 截图不参与指纹与筛选，只作参考图并给尺寸判定当辅助证据，所以这里取字典序第一张、
 * 把其余候选连同取用结果一起报出来；要钉死用哪张，在目录根部放 quality-import.json
 * 并在该样本写 image 字段（清单优先，与目录名无关）。
 */
function pickImage(paths: string[]): { path?: string; notice?: ImportNotice } {
  if (paths.length <= 1) return { path: paths[0] };
  const sorted = [...paths].sort((left, right) => left.localeCompare(right));
  return {
    path: sorted[0],
    notice: {
      name: sampleStem(sorted[0]),
      detail: `有 ${sorted.length} 张同名截图，取 ${sorted[0]}，未使用 ${sorted.slice(1).join('、')}`,
    },
  };
}

/** 去掉扩展名与 `.genui`／`.cardspec` 这类角色后缀，得到用于配对的主干名。 */
export function sampleStem(name: string): string {
  const base = name.replace(/^.*\//, '').replace(/\.[^.]*$/, '');
  return base.replace(/\.(genui|dsl|compact|cardspec|spec)$/i, '');
}

/**
 * CardSpec 顶层的 ``userQuery`` 是用户原话，DSL 与截图都不带它。
 * 与后端 ``quality_import.cardspec_user_query`` 同一套口径：Query 留空时从这里补，
 * 补齐后两侧才能按 Query 配对。
 */
export function cardspecUserQuery(spec: Record<string, unknown> | undefined): string {
  const value = spec?.userQuery;
  return typeof value === 'string' ? value.trim() : '';
}

/** 批量导入的结果：合格样本、不合格文件与自动取舍分开列，都要看得见才好修。 */
export type ImportFailure = { name: string; reason: string };
/** 不是失败、但用户需要知道的一次自动判断（例如同名的多张截图取了哪一张）。 */
export type ImportNotice = { name: string; detail: string };
export type ImportPlan = {
  samples: ExpectImportSample[]; failures: ImportFailure[]; notices: ImportNotice[];
};

const isImageName = (name: string) => /\.(png|jpe?g)$/i.test(name);
const isTextName = (name: string) => /\.(jsonl|json|txt)$/i.test(name);

/** 目录里的一条用例：路径都还是清单里的相对路径，读取与预算统计在统一循环里做。 */
type FolderEntry = {
  id: string; query?: string; size?: string; category?: string;
  dslPath: string; imagePath?: string; specPath?: string;
  sourceSha256?: string; imageSha256?: string;
  expectedIntents?: string[]; expectedData?: string[];
  expectedActions?: string[]; expectedIcons?: string[];
};

/** 三个来源都已经解析成文件对象的一条用例：清单、整个文件夹与多选文件都归到这里。 */
type SourceEntry = {
  id: string; query?: string; size?: string; category?: string;
  dsl?: File; image?: File; spec?: File;
  sourceSha256?: string; imageSha256?: string;
  expectedIntents?: string[]; expectedData?: string[];
  expectedActions?: string[]; expectedIcons?: string[];
};

/** 单条 DSL、整批体积与条数上限都与后端校验一致。 */
const MAX_SAMPLE_DSL_BYTES = 2 * 1024 * 1024;
const MAX_BATCH_BYTES = 40 * 1024 * 1024;
const MAX_SAMPLES = 500;

/** 预算超限要把整批停下来，不能变成每条样本各自「失败」刷满清单。 */
class BudgetError extends Error {}

function reasonText(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

function rowsFromManifest(manifest: { samples?: ManifestRow[] }): FolderEntry[] {
  if (!Array.isArray(manifest.samples)) throw new Error('清单缺少 samples');
  if (!manifest.samples.length) return [];
  return manifest.samples.map((row) => {
    // DSL 可选：清单只给 id＋截图时同样是一条样本。
    const fallback = row?.image ? sampleStem(row.image) : (row?.dsl ? sampleStem(row.dsl) : '');
    const id = (row?.id ?? '').trim() || fallback;
    if (!id) throw new Error('每条样本至少要有 id 或文件名可作样本 ID');
    return {
      ...row,
      id,
      dslPath: row?.dsl,
      imagePath: row?.image,
      specPath: row?.cardspec,
    };
  });
}

/** 旧交付清单（`dataset-manifest.json`）按 role 取文件；截图同样可以是可选的。 */
function rowsFromLegacyCards(manifest: { cards?: unknown[] }): FolderEntry[] {
  if (!Array.isArray(manifest.cards)) throw new Error('旧交付清单缺少 cards');
  type LegacyFile = { role: string; path: string; sha256?: string };
  type LegacyCard = { key?: string; query?: string; size?: string; files?: LegacyFile[] };
  return (manifest.cards as LegacyCard[]).map((card) => {
    if (!Array.isArray(card.files)) throw new Error('旧交付清单的卡片记录无效');
    const role = (label: string) => {
      const matches = card.files!.filter((item) => item.role === label);
      if (matches.length > 1) throw new Error(`重复的 ${label} 文件`);
      return matches[0];
    };
    const dsl = role('dsl');
    const image = role('image');
    // DSL 可选：ID 依次取 key → 截图主干 → DSL 主干。
    const fallback = image ? sampleStem(image.path) : (dsl ? sampleStem(dsl.path) : '');
    const id = (card.key ?? '').trim() ? card.key!.replaceAll('/', '__') : fallback;
    if (!id) throw new Error('每条卡片至少要有 key 或文件名可作样本 ID');
    return {
      id, query: card.query, size: card.size,
      dslPath: dsl?.path, imagePath: image?.path, specPath: role('cardspec')?.path,
      sourceSha256: dsl?.sha256, imageSha256: image?.sha256,
    };
  });
}

/**
 * 没有清单时按文件名主干归组：`Q001.genui.jsonl`＋`Q001.png`＋`Q001.cardspec.json` 算一条用例，
 * 样本 ID 取主干名 `Q001`。这正是「名称匹配对应」——主干名与期望样本 ID 一致就能配上。
 *
 * 一条用例的问题只记进失败清单，不拖垮同批其它用例：批量导入本来就会混进少量坏文件。
 */
async function rowsFromNames(paths: string[], textOf: (path: string) => Promise<string>)
  : Promise<{ entries: FolderEntry[]; failures: ImportFailure[]; notices: ImportNotice[] }> {
  const groups = new Map<string, { images: string[]; texts: string[] }>();
  for (const path of paths) {
    const stem = sampleStem(path);
    if (!stem) continue;
    const group = groups.get(stem) ?? { images: [], texts: [] };
    if (isImageName(path)) group.images.push(path);
    else if (isTextName(path)) group.texts.push(path);
    groups.set(stem, group);
  }
  if (!groups.size) {
    throw new Error('所选目录里没有可导入的文件：需要 Q001.genui.jsonl 这类命名，或 quality-import.json 清单');
  }
  const entries: FolderEntry[] = [];
  const failures: ImportFailure[] = [];
  const notices: ImportNotice[] = [];
  for (const [stem, group] of [...groups.entries()].sort((left, right) => (
    left[0].localeCompare(right[0])
  ))) {
    const picked = pickImage(group.images);
    if (picked.notice) notices.push(picked.notice);
    const classified: { path: string; kind: PayloadKind }[] = [];
    for (const path of group.texts) {
      const text = await textOf(path);
      const kind = classifyContentText(text);
      // 说明文档、交付清单、渲染脚本输入也能被 JSON 解析，但不是 genui：忽略并说明，
      // 否则会多出一条拿文件名当样本 ID 的假样本。
      if (kind === 'dsl' && !looksLikeGenui(text)) {
        notices.push({ name: sampleStem(path), detail: `${path} 不像 genui DSL，已忽略` });
        continue;
      }
      classified.push({ path, kind });
    }
    if (!classified.length && !picked.path) continue;
    const unusable = classified.filter((item) => item.kind === 'unknown');
    if (unusable.length) {
      failures.push({
        name: stem, reason: `${unusable.map((item) => item.path).join('、')} 既不是 JSON 也不是 JSONL`,
      });
      continue;
    }
    const dsls = classified.filter((item) => item.kind === 'dsl');
    const specs = classified.filter((item) => item.kind === 'cardspec');
    if (dsls.length > 1) {
      failures.push({ name: stem, reason: `有多份 DSL：${dsls.map((item) => item.path).join('、')}` });
      continue;
    }
    if (!dsls.length) {
      failures.push({ name: stem, reason: '缺少 genui DSL：只有 CardSpec 或截图不能参与对比' });
      continue;
    }
    entries.push({
      id: stem, dslPath: dsls[0].path, imagePath: picked.path,
      specPath: specs[0]?.path,
    });
  }
  return { entries, failures, notices };
}

/**
 * 只读取用户明确选中的文件；清单里的路径不能访问电脑其他目录。
 * 同一份文件可能被「按内容识别」与「组装样本」各读一次，体积只按一次计入预算。
 */
/** 清单里的路径必须留在目录内：越界按清单本身错误处理，不降级成一条失败样本。 */
function assertRelativePath(path: string) {
  if (typeof path !== 'string' || path.includes('..') || path.includes('\\')
    || path.includes(':') || path.startsWith('/')) {
    throw new Error('清单文件路径必须是目录内的相对路径');
  }
}

function buildReader(files: File[]) {
  const byPath = new Map<string, File>();
  for (const file of files) {
    const relative = file.webkitRelativePath || file.name;
    const path = relative.includes('/') ? relative.slice(relative.indexOf('/') + 1) : relative;
    if (!path) continue;
    if (byPath.has(path)) throw new Error(`文件路径重复：${path}`);
    byPath.set(path, file);
  }
  let bytes = 0;
  const counted = new Set<string>();
  const take = (path: string, required: boolean): File | undefined => {
    const file = byPath.get(path);
    if (!file) {
      if (required) throw new Error(`缺少文件：${path}`);
      return undefined;
    }
    if (!counted.has(path)) {
      counted.add(path);
      bytes += file.size;
    }
    if (bytes > MAX_BATCH_BYTES) throw new BudgetError('本批文件超过 40 MiB，请分批导入');
    return file;
  };
  return { take };
}

/** 清单／目录里的一条用例解析成文件对象；清单声明了文件却没给到，只让这一条失败。 */
function resolveEntries(entries: FolderEntry[], take: (path: string, required: boolean) => File | undefined)
  : { sources: SourceEntry[]; failures: ImportFailure[] } {
  const sources: SourceEntry[] = [];
  const failures: ImportFailure[] = [];
  for (const entry of entries) {
    const name = (entry.id ?? '').trim() || entry.dslPath || entry.imagePath || '未命名';
    // 路径越界是清单本身的问题：整批停下来，其余条目照常靠失败清单报告。
    if (entry.dslPath) assertRelativePath(entry.dslPath);
    if (entry.imagePath) assertRelativePath(entry.imagePath);
    if (entry.specPath) assertRelativePath(entry.specPath);
    try {
      sources.push({
        id: entry.id, query: entry.query, size: entry.size, category: entry.category,
        dsl: entry.dslPath ? take(entry.dslPath, true) : undefined,
        image: entry.imagePath ? take(entry.imagePath, true) : undefined,
        spec: entry.specPath ? take(entry.specPath, true) : undefined,
        sourceSha256: entry.sourceSha256, imageSha256: entry.imageSha256,
        expectedIntents: entry.expectedIntents, expectedData: entry.expectedData,
        expectedActions: entry.expectedActions, expectedIcons: entry.expectedIcons,
      });
    } catch (reason) {
      if (reason instanceof BudgetError) throw reason;
      failures.push({ name, reason: reasonText(reason) });
    }
  }
  return { sources, failures };
}

async function readSpec(file: File): Promise<Record<string, unknown>> {
  const parsed = JSON.parse(stripBom(await fileText(file)));
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('CardSpec 必须是 JSON 对象');
  }
  return parsed as Record<string, unknown>;
}

/** 逐条读取与校验；不合格的样本只进失败清单，同批其它样本照常导入。 */
async function materialize(
  sources: SourceEntry[], failures: ImportFailure[], notices: ImportNotice[] = [],
): Promise<ImportPlan> {
  if (sources.length > MAX_SAMPLES) {
    throw new Error(`每次导入 1–${MAX_SAMPLES} 条；大数据集请拆分导入`);
  }
  const samples: ExpectImportSample[] = [];
  const seen = new Set<string>();
  for (const entry of sources) {
    const name = entry.id.trim() || entry.dsl?.name || entry.image?.name || '未命名';
    try {
      // 三个来源都先确认是文件：拖进来的文件夹在这里就出局，不让它变成一条假样本。
      for (const file of [entry.dsl, entry.image, entry.spec]) {
        if (file) assertSelectableFile(file);
      }
      const id = entry.id.trim();
      if (!id) throw new Error('样本 ID 不能为空：请在清单里补 id，或按 Q001.genui.jsonl 命名文件');
      if (seen.has(id.toLowerCase())) {
        throw new Error(`样本 ID 重复：${id}（请更换其中一个的 ID）`);
      }
      seen.add(id.toLowerCase());
      if (entry.dsl && entry.dsl.size > MAX_SAMPLE_DSL_BYTES) {
        throw new Error('单条 DSL 不能超过 2 MiB');
      }
      const dsl = entry.dsl ? await fileText(entry.dsl) : '';
      // 槽位放错：把规格当 genui 导进去会让这条用例整条失效，直接说清怎么改。
      if (dsl && classifyContentText(dsl) === 'cardspec') {
        throw new Error('这份文件其实是 CardSpec：请放到 CardSpec 槽位');
      }
      const spec = entry.spec ? await readSpec(entry.spec) : undefined;
      samples.push({
        id, size: declaredSize(entry.size, id), dsl,
        query: (entry.query ?? '').trim() || cardspecUserQuery(spec),
        imageBase64: entry.image ? await imageData(entry.image) : undefined,
        cardSpec: spec,
        expectedIntents: entry.expectedIntents, expectedData: entry.expectedData,
        expectedActions: entry.expectedActions, expectedIcons: entry.expectedIcons,
        category: entry.category,
        sourceSha256: entry.sourceSha256, imageSha256: entry.imageSha256,
      });
    } catch (reason) {
      failures.push({ name, reason: reasonText(reason) });
    }
  }
  return { samples, failures, notices };
}

/**
 * 批量文件夹导入：有清单按清单取文件，没清单按命名约定归组。
 * 清单里已声明的字段保持原样；没声明的 ID／Query 与没截图的样本照常导入。
 * 单条不合格只记失败清单，不静默丢弃，也不因为一个坏文件放弃整批。
 */
export async function readImportFolder(files: File[]): Promise<ImportPlan> {
  const { take } = buildReader(files);
  const names = files.map((file) => {
    const relative = file.webkitRelativePath || file.name;
    return relative.includes('/') ? relative.slice(relative.indexOf('/') + 1) : relative;
  });
  const found = ['quality-import.json', 'dataset-manifest.json'].filter((name) => names.includes(name));
  if (found.length > 1) {
    throw new Error('清单只能有一份：删掉多余的 quality-import.json 或 dataset-manifest.json');
  }
  let entries: FolderEntry[];
  let failures: ImportFailure[] = [];
  let notices: ImportNotice[] = [];
  if (found.length) {
    const manifestFile = take(found[0], true)!;
    if (manifestFile.size > 8 * 1024 * 1024) throw new Error('清单过大');
    const manifest = JSON.parse(await manifestFile.text());
    entries = found[0] === 'dataset-manifest.json'
      ? rowsFromLegacyCards(manifest)
      : rowsFromManifest(manifest);
  } else {
    const grouped = await rowsFromNames(names, async (path) => fileText(take(path, true)!));
    entries = grouped.entries;
    failures = grouped.failures;
    notices = grouped.notices;
  }
  const resolved = resolveEntries(entries, take);
  return materialize(
    resolved.sources, [...failures, ...resolved.failures], notices,
  );
}

/**
 * 多选文件的批量导入：DSL／截图／CardSpec 各选一批，按文件名主干归组，
 * 主干名就是样本 ID（`Q001.genui.jsonl`＋`Q001.png`＋`Q001.cardspec.json` 合成一条用例）。
 * 槽位是人工指定的，所以不再按内容猜格式；缺 DSL、重复截图这类问题只影响那一条用例。
 */
export async function readImportSelection(
  input: { dsl: File[]; images: File[]; specs: File[] },
): Promise<ImportPlan> {
  if (!input.dsl.length) throw new Error('批量导入至少要有一个 DSL 文件');
  const bytes = [...input.dsl, ...input.images, ...input.specs]
    .reduce((total, file) => total + file.size, 0);
  if (bytes > MAX_BATCH_BYTES) throw new Error('本批文件超过 40 MiB，请分批导入');
  // 目录条目先挑出来：它们是「选错了」，不是「没有同名 DSL」，报错要能照做。
  const rejected: ImportFailure[] = [];
  const usable = (files: File[]) => files.filter((file) => {
    try {
      assertSelectableFile(file);
      return true;
    } catch (reason) {
      rejected.push({ name: file.name, reason: reasonText(reason) });
      return false;
    }
  });
  const dslFiles = usable(input.dsl);
  const imageFiles = usable(input.images);
  const specFiles = usable(input.specs);
  if (!dslFiles.length) {
    throw new Error(input.dsl.length
      ? '没有可用的 DSL 文件：选中的条目里有文件夹，请点开它选择文件'
      : '批量导入至少要有一个 DSL 文件');
  }
  const buckets = new Map<string, { dsl: File[]; images: File[]; specs: File[] }>();
  const bucketOf = (file: File) => {
    const stem = sampleStem(file.name);
    const bucket = buckets.get(stem) ?? { dsl: [], images: [], specs: [] };
    buckets.set(stem, bucket);
    return { stem, bucket };
  };
  for (const file of dslFiles) bucketOf(file).bucket.dsl.push(file);
  for (const file of imageFiles) bucketOf(file).bucket.images.push(file);
  for (const file of specFiles) bucketOf(file).bucket.specs.push(file);
  const sources: SourceEntry[] = [];
  const failures: ImportFailure[] = [...rejected];
  const notices: ImportNotice[] = [];
  for (const [stem, bucket] of [...buckets.entries()].sort((left, right) => (
    left[0].localeCompare(right[0])
  ))) {
    if (!stem) {
      failures.push({ name: '（文件名没有主干）', reason: '文件名无法提取样本 ID' });
      continue;
    }
    if (bucket.dsl.length > 1) {
      failures.push({ name: stem, reason: `有多份 DSL：${bucket.dsl.map((f) => f.name).join('、')}` });
      continue;
    }
    if (!bucket.dsl.length) {
      failures.push({ name: stem, reason: '没有同名 DSL 文件：只有截图或 CardSpec 不能参与对比' });
      continue;
    }
    // 同名多张截图与文件夹模式同一套规则：取一张并留提示，不因为多选了两张就放弃这条。
    const pickedImage = pickImage(bucket.images.map((file) => file.name));
    if (pickedImage.notice) notices.push(pickedImage.notice);
    if (bucket.specs.length > 1) {
      failures.push({ name: stem, reason: `有多份 CardSpec：${bucket.specs.map((f) => f.name).join('、')}` });
      continue;
    }
    sources.push({
      id: stem, dsl: bucket.dsl[0],
      image: bucket.images.find((file) => file.name === pickedImage.path) ?? bucket.images[0],
      spec: bucket.specs[0],
    });
  }
  return materialize(sources, failures, notices);
}

function TokenList({ label, items, labels }:
  { label: string; items: string[]; labels: Record<string, string> }) {
  return <div className="expect-line"><span className="expect-key">{label}</span>
    {items.length
      ? <div className="expect-chips">{items.map((item) => (
        <span key={item} className="expect-chip is-hit"
          title={labels[item] ? `${labels[item]} · ${item}` : item}>
          {labels[item] && <strong className="expect-chip-label">{labels[item]}</strong>}
          <code className="expect-chip-raw">{item}</code>
        </span>
      ))}</div>
      : <span className="expect-empty">未识别</span>}
  </div>;
}

/** 候选库里的中文名：自动识别出的 token 带上中文，否则一眼看不出对错。 */
function labelMap(items: ExpectOption[]): Record<string, string> {
  return Object.fromEntries(items.map((item) => [item.value, item.label]));
}

/** 识别结果：说明每个文件被认成了什么，并摆出自动提取到的数据／动作／图标，方便确认没认错。 */
function DetectionPreview({ detections, fingerprint, options }:
  { detections: { name: string; kind: string }[]; fingerprint: DetectedFingerprint;
    options: ExpectOptions }) {
  if (!detections.length) return null;
  return <div className="expect-side-tokens" aria-label="自动识别结果">
    <p className="quality-warning">
      已识别：{detections.map((item) => (
        `${item.name}→${item.kind === 'cardspec' ? 'CardSpec' : 'genui DSL'}`
      )).join('，')}
      ；数据、动作与图标由比对用的同一套口径自动提取。
    </p>
    <TokenList label="数据" items={fingerprint.data} labels={labelMap(options.data)} />
    <TokenList label="动作" items={fingerprint.actions} labels={labelMap(options.actions)} />
    <TokenList label="图标" items={fingerprint.icons} labels={labelMap(options.icons)} />
  </div>;
}

function mergeFingerprints(items: ExpectFingerprint[]): DetectedFingerprint {
  const key = (dimension: keyof DetectedFingerprint) => [...new Set(
    items.flatMap((item) => item[dimension] ?? []),
  )].sort((left, right) => left.localeCompare(right));
  return { data: key('data'), actions: key('actions'), icons: key('icons') };
}

/** 只在对应输入框还空着时填自动结果，用户手写的期望项不会被覆盖。 */
function fillWhenEmpty(tokens: string[], next: string[], apply: (values: string[]) => void) {
  if (next.length && !tokens.length) apply(next);
}

export function ExpectImportRoute({
  origin = 'expect', purpose = 'expect',
}: { origin?: ExpectImportOrigin; purpose?: ExpectPurpose }) {
  const navigate = useNavigate();
  /**
   * 编辑模式：带 runId＋sampleId 进来就回填这一条，保存走 PUT 就地更新。
   * 就地更新不会产生同 ID 的第二条，也不需要新建批次。
   */
  const [params] = useSearchParams();
  const editRunId = params.get('runId') ?? '';
  const editSampleId = params.get('sampleId') ?? '';
  const isEdit = Boolean(editRunId && editSampleId);
  const [editImageUrl, setEditImageUrl] = useState<string | null>(null);
  /** 默认不勾选：样本 ID 由系统按内容哈希生成，用户不必操心唯一性。 */
  const [customIds, setCustomIds] = useState(false);
  const [mode, setMode] = useState('single');
  const [category, setCategory] = useState('');
  const [customCategory, setCustomCategory] = useState('');
  const [source, setSource] = useState('unknown');
  const [id, setId] = useState('Q001');
  const [query, setQuery] = useState('');
  const [size, setSize] = useState('');
  const [dslPick, setDslPick] = useState<{ name: string; text: string; detection?: ExpectDetection }>();
  const [specPick, setSpecPick] = useState<{
    name: string; spec: Record<string, unknown>; detection?: ExpectDetection }>();
  const [detectError, setDetectError] = useState('');
  const [detectBusy, setDetectBusy] = useState(false);
  const [image, setImage] = useState<File>();
  const [dslFiles, setDslFiles] = useState<File[]>([]);
  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const [specFiles, setSpecFiles] = useState<File[]>([]);
  const [options, setOptions] = useState<ExpectOptions>(EMPTY_OPTIONS);
  const [dataTokens, setDataTokens] = useState<string[]>([]);
  const [actionTokens, setActionTokens] = useState<string[]>([]);
  const [iconTokens, setIconTokens] = useState<string[]>([]);
  const [folder, setFolder] = useState<File[]>([]);
  const [failures, setFailures] = useState<ImportFailure[]>([]);
  const [notices, setNotices] = useState<ImportNotice[]>([]);
  const [notice, setNotice] = useState('');
  const [knownIds, setKnownIds] = useState<Record<string, ExpectSampleId>>({});
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const isActual = purpose === 'actual';
  useEffect(() => {
    if (!isEdit) return;
    let cancelled = false;
    getExpectSample(editRunId, editSampleId)
      .then((item) => {
        if (cancelled) return;
        // 回填以「导入时显式填写的期望项」为准，而不是自动指纹：那才是这条期望的真正要求。
        setMode('single');
        setId(item.sampleId);
        setQuery(item.query ?? '');
        setSize(LEGAL_SIZES.includes(item.size) ? item.size : '');
        const itemCategory = (item.category ?? '').trim();
        if (itemCategory) {
          setCategory(PRESET_CATEGORIES.includes(itemCategory)
            ? itemCategory : CUSTOM_CATEGORY);
          setCustomCategory(itemCategory);
        }
        if ((item.genui ?? '').trim()) {
          setDslPick({ name: '（当前 DSL）', text: item.genui });
        }
        setDataTokens(item.explicit?.data ?? []);
        setActionTokens(item.explicit?.actions ?? []);
        setIconTokens(item.explicit?.icons ?? []);
        setEditImageUrl(item.imageUrl ?? null);
      })
      .catch((reason) => { if (!cancelled) setError(`读取这条期望失败：${reasonText(reason)}`); });
    return () => { cancelled = true; };
  }, [isEdit, editRunId, editSampleId]);
  useEffect(() => {
    let cancelled = false;
    // 候选只服务输入提示；拿不到时仍可手写 token，所以失败不报错。
    getExpectOptions()
      .then((items) => { if (!cancelled) setOptions(items); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    let cancelled = false;
    // ID 冲突提示只是提交前的提醒：拿不到索引时按「没有历史样本」处理，不影响导入。
    getExpectSampleIds(purpose)
      .then((index) => {
        if (cancelled) return;
        setKnownIds(Object.fromEntries(index.items
          .filter((item) => item.id)
          .map((item) => [item.id.toLowerCase(), item])));
      })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [purpose]);

  /** DSL／CardSpec 各自的识别结果先分开存：指纹要合并，槽位错误要能单独退回。 */
  const picks: { name: string; detection?: ExpectDetection }[] = [dslPick, specPick]
    .flatMap((item) => (item ? [{ name: item.name, detection: item.detection }] : []));
  const detections = picks.filter((item) => item.detection)
    .map((item) => ({ name: item.name, kind: String(item.detection?.kind ?? '') }));
  const fingerprint = mergeFingerprints(picks
    .flatMap((item) => (item.detection ? [item.detection.fingerprint] : [])));
  /** 单条模式下该 ID 是否已在该侧导入过：同名按最新批次生效，提交前先提醒。 */
  // 编辑模式下 ID 就是它自己；留空时由后端按哈希生成，都不算「与已有样本同名」。
  const idConflict = mode === 'single' && !isEdit && customIds && id.trim()
    ? knownIds[id.trim().toLowerCase()] : undefined;

  /** 自动填充只服务期望侧需求项，且只填空着的输入框，不覆盖人工写的内容。 */
  function refreshAutoFill(next: (ExpectDetection | undefined)[]) {
    if (isActual) return;
    const merged = mergeFingerprints(next
      .filter((item): item is ExpectDetection => Boolean(item))
      .map((item) => item.fingerprint));
    fillWhenEmpty(dataTokens, merged.data, setDataTokens);
    fillWhenEmpty(actionTokens, merged.actions, setActionTokens);
    fillWhenEmpty(iconTokens, merged.icons, setIconTokens);
  }

  /**
   * DSL 槽只认 genui DSL：先把文件读进来占住槽位，格式识别失败也不挡导入
   * （指纹由后端在导入时按同一套口径重提）。槽里放了 CardSpec 才退回并说明。
   */
  async function chooseDsl(file?: File) {
    setDetectError('');
    if (!file) { setDslPick(undefined); return; }
    setDetectBusy(true);
    let text = '';
    try {
      if (file.size > MAX_SAMPLE_DSL_BYTES) throw new Error('单条 DSL 不能超过 2 MiB');
      text = await fileText(file);
    } catch (reason) {
      setDslPick(undefined);
      setDetectBusy(false);
      setDetectError(`DSL 文件读取失败：${reasonText(reason)}`);
      return;
    }
    setDslPick({ name: file.name, text });
    try {
      const detection = await detectExpectPayload(text);
      if (detection.kind !== 'dsl') {
        setDslPick(undefined);
        setDetectError(detection.kind === 'cardspec'
          ? '这份文件其实是 CardSpec：请放到 CardSpec 槽位'
          : '这份文件既不是 genui DSL 也不是 CardSpec');
      } else {
        setDslPick({ name: file.name, text, detection });
        refreshAutoFill([detection, specPick?.detection]);
      }
    } catch (reason) {
      setDetectError(`格式识别不可用（${reasonText(reason)}）：仍可导入，数据、动作与图标由后端在导入时提取`);
    } finally {
      setDetectBusy(false);
    }
  }

  /**
   * CardSpec 槽：解析成 JSON 对象，并在 Query 还空着时用它的 userQuery 补上
   * （真实输出的清单常常只有 DSL 与 CardSpec，没有单独的 Query 字段）。
   */
  async function chooseSpec(file?: File) {
    setDetectError('');
    if (!file) { setSpecPick(undefined); return; }
    setDetectBusy(true);
    try {
      const spec = await readSpec(file);
      if (!query.trim()) {
        const extracted = cardspecUserQuery(spec);
        if (extracted) setQuery(extracted);
      }
      setSpecPick({ name: file.name, spec });
      try {
        const detection = await detectExpectPayload(JSON.stringify(spec));
        setSpecPick({ name: file.name, spec, detection });
        refreshAutoFill([dslPick?.detection, detection]);
      } catch (reason) {
        setDetectError(`格式识别不可用（${reasonText(reason)}）：仍可导入，期望指纹由后端在导入时提取`);
      }
    } catch (reason) {
      setSpecPick(undefined);
      setDetectError(`CardSpec 读取失败：${reasonText(reason)}`);
    } finally {
      setDetectBusy(false);
    }
  }

  async function submit() {
    setError(''); setNotice(''); setFailures([]); setNotices([]); setBusy(true);
    try {
      const resolved = category === CUSTOM_CATEGORY ? customCategory.trim() : category;
      if (resolved.length > 40) throw new Error('数据分类不能超过 40 个字符');
      let samples: ExpectImportSample[];
      let planFailures: ImportFailure[] = [];
      let planNotices: ImportNotice[] = [];
      if (mode === 'folder' || mode === 'files') {
        const plan = mode === 'folder'
          ? await readImportFolder(folder)
          : await readImportSelection({ dsl: dslFiles, images: imageFiles, specs: specFiles });
        samples = plan.samples;
        planFailures = plan.failures;
        planNotices = plan.notices;
      } else if (mode === 'single') {
        if (customIds && !id.trim()) throw new Error('勾选了自定义 ID，请填写样本 ID');
        // 编辑时截图留空表示保留原截图（浏览器无法把已有截图回填进 file 输入框）。
        if (!image && !isEdit) throw new Error('请选择截图：导入只强制截图');
        if (detectBusy) throw new Error('正在读取文件，稍等片刻');
        const text = dslPick?.text ?? '';
        samples = [{
          id: customIds ? id.trim() : '', size: size || undefined, dsl: text,
          query: query.trim() || cardspecUserQuery(specPick?.spec),
          imageBase64: image ? await imageData(image) : undefined,
          cardSpec: specPick?.spec,
          ...(isActual ? {} : {
            expectedData: dataTokens.length ? dataTokens : undefined,
            expectedActions: actionTokens.length ? actionTokens : undefined,
            expectedIcons: iconTokens.length ? iconTokens : undefined,
          }),
        }];
      } else {
        throw new Error('未知的导入方式');
      }
      if (isEdit) {
        const [draft] = samples;
        await updateExpectSample(editRunId, editSampleId, {
          query: draft.query, size: draft.size, dsl: draft.dsl,
          imageBase64: draft.imageBase64, cardSpec: draft.cardSpec,
          expectedData: draft.expectedData, expectedActions: draft.expectedActions,
          expectedIcons: draft.expectedIcons, category: draft.category,
        });
        navigate('/expect/gallery');
        return;
      }
      if (!customIds) {
        // 不勾选自定义 ID：清单／文件名里的主干一律不用，改由后端按内容哈希生成。
        samples = samples.map((item) => ({ ...item, id: '' }));
      }
      // 同名不会丢数据，但会盖住旧样本：提交前把冲突列出来，让用户决定换 ID 还是覆盖。
      const conflicts = samples
        .map((item) => knownIds[item.id.trim().toLowerCase()])
        .filter((item): item is ExpectSampleId => Boolean(item));
      setFailures(planFailures);
      setNotices(planNotices);
      if (!samples.length) {
        throw new Error(planFailures.length
          ? `没有可导入的样本：${planFailures.length} 个文件不合格，见下方失败清单`
          : '没有可导入的样本');
      }
      const payload = {
        name: defaultBatchName(purpose), imageSource: source, purpose,
        category: resolved || undefined, samples,
      };
      if (new Blob([JSON.stringify(payload)]).size > MAX_BYTES) {
        throw new Error('上传内容超过 64 MiB，请分批');
      }
      const run = await importExpectBatch(payload);
      if (planFailures.length || conflicts.length) {
        // 批次已经导入，但失败清单与同名提示必须能当场看到：导航走了就看不到了。
        const parts = [`已导入 ${samples.length} 条`];
        if (planFailures.length) {
          parts.push(`${planFailures.length} 个条目没有导入，见下方失败清单`);
        }
        if (conflicts.length) {
          parts.push(`其中 ${conflicts.length} 个样本 ID 与该侧已有样本同名：`
            + `${conflicts.map((item) => item.id).join('、')}`
            + '（同名按最新批次生效，要与旧样本并存请更换 ID 后重新导入）');
        }
        setNotice(`${parts.join('；')}。`);
        return;
      }
      if (origin === 'gallery') {
        navigate(`/expect/gallery?imported=${encodeURIComponent(run.runId)}`);
      } else {
        // 对比页不再按批次筛选，导入完直接过去；新批次自动进它所属的那一侧。
        navigate(origin === 'expect' ? '/expect' : `/quality?runId=${encodeURIComponent(run.runId)}`);
      }
    } catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }

  /** 页头文案按编辑／期望／实际三种入口各写一份，避免在 JSX 里嵌套三元。 */
  const pageTitle = isEdit ? '编辑期望样本'
    : (isActual ? '导入实际输出' : '导入期望输出');
  const pageIntro = isEdit
    ? '就地修改这一条期望：保存后原批次与同批其它样本都不变，也不会出现同 ID 的第二条。'
      + '截图留空即保留原截图，其余字段以这里填的为准。'
    : (isActual
      ? '单条或批量导入真实输出（多选文件／整个文件夹）：只有样本 ID 与截图必填，'
        + 'DSL、CardSpec、Query 都可以留空。Query 留空时从 CardSpec 的 userQuery 补；'
        + '样本 ID 与期望一致也能配对。批次按导入时间自动命名。'
      : '单条或批量导入期望输出（多选文件／整个文件夹）：只有样本 ID 与截图必填，'
        + 'DSL、CardSpec、Query、尺寸都可以留空；期望数据、期望动作与期望图标可以手填，'
        + '留空时按 DSL／CardSpec 识别结果自动提取。作为期望对比的左侧基线，批次按导入时间自动命名。');

  return <div className="quality-page expect-import">
    <header className="batch-center-header"><div><h1>{pageTitle}</h1>
      <p>{pageIntro}</p></div>
      <nav className="quality-links" aria-label="期望对比工具">
        {/* 模块之间用左侧主导航切换；这里只保留期望对比模块内的落地位置。 */}
        {origin === 'gallery' && <Link to="/expect/gallery">返回画廊</Link>}
        <Link to="/expect">期望对比</Link>
        <Link to={isActual ? '/expect/import' : '/expect/actual-import'}>
          {isActual ? '导入期望输出' : '导入实际输出'}
        </Link>
        {!isActual && <Link to="/expect/gallery">期望数据画廊</Link>}
      </nav></header>
    {isEdit && <div className="quality-card">
      <p><span className="expect-key">编辑对象</span>
        <span className="expect-value">{editSampleId}（批次 {editRunId}）</span></p>
      {editImageUrl
        ? <p className="expect-line"><span className="expect-key">当前截图</span>
          <a href={editImageUrl} target="_blank" rel="noreferrer">查看</a>
          <span className="expect-empty">不重新上传就保留这张</span></p>
        : <p className="expect-empty">这条样本还没有截图</p>}
    </div>}
    {error && <div role="alert" className="batch-error">{error}</div>}
    <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <fieldset className="quality-card" disabled={busy}>
        <legend>选择输入</legend>
        <label className="quality-field">数据分类
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">不分类</option>
            {PRESET_CATEGORIES.map((item) => <option key={item} value={item}>{item}</option>)}
            <option value={CUSTOM_CATEGORY}>自定义…</option>
          </select></label>
        {category === CUSTOM_CATEGORY && <label className="quality-field">自定义分类
          <input maxLength={40} value={customCategory} placeholder="最多 40 个字符"
            onChange={(e) => setCustomCategory(e.target.value)} /></label>}
        <label className="expect-field-toggle">
          <input type="checkbox" checked={customIds} disabled={isEdit}
            onChange={(e) => setCustomIds(e.target.checked)} />
          使用自定义样本 ID
        </label>
        <p className="expect-dimension-note">{customIds
          ? '使用你提供的样本 ID（单条模式在下方填写，批量导入取清单／文件名主干）；ID 唯一，重复会被拒绝。'
          : '默认不勾选：样本 ID 由系统按内容（Query＋DSL＋期望项＋截图）哈希生成，同内容得同一个 ID，'
            + '你不用操心唯一性；批量导入时清单／文件名里的 ID 也不采用。需要人工命名就勾上复选框。'}</p>
        <label className="quality-field">导入方式
          <select value={mode} disabled={isEdit} onChange={(e) => setMode(e.target.value)}>
            <option value="single">单条：DSL＋截图＋CardSpec</option>
            <option value="files">批量：多选 DSL／截图／CardSpec 文件</option>
            <option value="folder">批量：整个文件夹（含清单）</option>
          </select></label>
        <label className="quality-field">截图来源
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="unknown">来源未知</option>
            <option value="web">Web 截图</option>
            <option value="native">模拟器／真机截图</option>
          </select></label>
        {mode === 'single' ? <>
          {(customIds || isEdit) && <label className="quality-field">样本 ID
            <input required readOnly={isEdit} value={id}
              onChange={(e) => setId(e.target.value)} /></label>}
          {idConflict && <p className="quality-warning" role="status">
            该侧已有同 ID 样本 <code>{idConflict.id}</code>（批次「{idConflict.runName}」）：
            同名按最新批次生效——要修正这个样本就用同一个 ID 重新导入，要让两条并存请更换 ID。
          </p>}
          <label className="quality-field">Query（可选）
            <textarea value={query}
              placeholder="填了才能按 Query 配对；留空时只按样本 ID 配对"
              onChange={(e) => setQuery(e.target.value)} /></label>
          <label className="quality-field">尺寸
            <select value={size} onChange={(e) => setSize(e.target.value)}>
              <option value="">自动判定（2x2／2x4）</option>
              {LEGAL_SIZES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select></label>
          <label className="quality-field">导入 DSL（可选）
            <input type="file" accept=".json,.jsonl,.txt"
              onChange={(e) => { void chooseDsl(e.target.files?.[0]); }} /></label>
          <label className="quality-field">{isEdit ? '导入截图（留空保留原截图）' : '导入截图'}
            <input required={!isEdit} type="file" accept="image/png,image/jpeg"
              onChange={(e) => setImage(e.target.files?.[0])} /></label>
          <p className="expect-dimension-note">只有样本 ID 与截图必填；DSL、CardSpec、Query、尺寸、
            期望数据／动作／图标都可以留空（留空时这条期望的指纹只由显式填写的那几项提供）。</p>
          <label className="quality-field">导入 CardSpec（可选）
            <input type="file" accept=".json,.jsonl,.txt"
              onChange={(e) => { void chooseSpec(e.target.files?.[0]); }} /></label>
          {detectBusy && <p className="quality-warning">正在读取文件…</p>}
          {detectError && <p className="quality-warning" role="alert">{detectError}</p>}
          <DetectionPreview detections={detections} fingerprint={fingerprint}
            options={options} />
          {isActual
            ? <p className="quality-warning">实际输出不需要声明需求项：数据、动作与图标由后端从 DSL
              自动提取，期望项一律来自左侧的期望批次。</p>
            : <>
              <TokenPicker legend="期望数据" options={options.data} tokens={dataTokens}
                onChange={setDataTokens}
                note="可输入中文（如「天气 当前」）或具体字段路径，输入时给出候选提示；候选外的写法会按原文比较。数组字段要用具体下标（如 /data/weather/daily/1/condition），候选默认给 0 号槽位。留空则回退 DSL／CardSpec 自动提取。"
                placeholder="/data/weather/current/condition 或 天气 当前" />
              <TokenPicker legend="期望动作" options={options.actions} tokens={actionTokens}
                onChange={setActionTokens}
                note="动作按「函数:目标」比较；可只写目标（如 Weather_CityCode），也可输入中文（如「跳转 天气」）。"
                placeholder="clickToDeeplink:Weather_CityCode 或 跳转 天气" />
              <TokenPicker legend="期望图标" options={options.icons} tokens={iconTokens}
                onChange={setIconTokens}
                note="图标按资源文件名比较，可写完整路径或只写名字（如 bell_fill）。"
                placeholder="resources/base/media/bell_fill.svg 或 bell_fill" />
            </>}
        </> : mode === 'files' ? <>
          <label className="quality-field">导入 DSL（可多选）
            <input type="file" multiple accept=".json,.jsonl,.txt"
              onChange={(e) => setDslFiles(Array.from(e.target.files ?? []))} /></label>
          <label className="quality-field">导入截图（可多选）
            <input type="file" multiple accept="image/png,image/jpeg"
              onChange={(e) => setImageFiles(Array.from(e.target.files ?? []))} /></label>
          <label className="quality-field">导入 CardSpec（可多选）
            <input type="file" multiple accept=".json,.jsonl,.txt"
              onChange={(e) => setSpecFiles(Array.from(e.target.files ?? []))} /></label>
          <p>三个槽位各自多选：按文件名主干归组，
            <code>Q001.genui.jsonl</code>＋<code>Q001.png</code>＋<code>Q001.cardspec.json</code>
            合成一条用例，样本 ID 取主干名 <code>Q001</code>，与期望样本同名就能配对。
            Query 留空时先用 CardSpec 的 <code>userQuery</code> 补。每次最多 500 条、文件共 40 MiB。</p>
          <p className="quality-warning">不合格的文件不会拖垮整批：导完后列在下方失败清单里，
            其余样本照常导入。</p>
          </> : <>
          <label className="quality-field">数据文件夹
            <input type="file" multiple {...{ webkitdirectory: '' }}
              onChange={(e) => setFolder(Array.from(e.target.files ?? []))} /></label>
          <p>整个文件夹导入会自己挑，并全部列进下方「自动取舍」：同一主干有多张截图时取路径
            字典序第一张（目录名不分主次，截图也不参与匹配；要钉死用哪张就在目录根部放
            <code>quality-import.json</code> 并写该样本的 <code>image</code>）；
            <code>payload.json</code>、<code>render-manifest.json</code> 这类不像 genui 的
            JSON 与说明文档会被忽略，不会变成假样本。</p>
          <p>两种放法都支持：目录根部放 <code>quality-import.json</code>（或旧交付
            <code>dataset-manifest.json</code>）就按清单取文件；没有清单时按文件名主干归组，
            例如 <code>Q001.genui.jsonl</code>＋<code>Q001.png</code>＋<code>Q001.cardspec.json</code>
            合成一条用例，样本 ID 取主干名 <code>Q001</code>。
            每次最多 500 条、文件共 40 MiB，不自动截取样本；不合格的条目列进失败清单，不拖垮整批。</p>
          <details><summary>批量清单格式</summary><pre>{JSON.stringify({
            samples: [{
              id: 'Q001', query: '显示天气', size: '2x2', category: '天气',
              dsl: 'dsl/Q001.genui.jsonl', image: 'images/Q001.png',
              cardspec: 'dsl/Q001.cardspec.json',
              expectedData: ['/data/weather/current/condition'],
              expectedActions: ['Weather_CityCode'],
            }],
          }, null, 2)}</pre></details>
          <details><summary>没有清单时的命名约定</summary><pre>{`dataset/
  Q001.genui.jsonl   ← genui DSL（必须）
  Q001.png           ← 截图（可选）
  Q001.cardspec.json ← CardSpec（可选，按内容识别）
  Q002.genui.jsonl   ← 另一条用例`}</pre></details>
        </>}
        <p className="quality-warning">Query 与截图都可以不填：Query 留空时先取 CardSpec 的
          <code>userQuery</code>，仍然空才只按样本 ID 配对；截图只作参考图、不参与筛选。尺寸可以不填，由 DSL 的布局名前缀、
          仅 2x4 可用的组件与截图宽高比自动判定，判定与声明冲突时保留声明并给出提示。
          数据分类随批次保存，并可在期望对比页按分类筛选；批量清单可用样本级 category 覆盖。
          期望批次附带 CardSpec 时（期望侧），其中的数据绑定、事件与资产优先成为期望指纹，
          缺失维度改用 DSL；显式填写的数据／动作／图标仍优先于两者。
          中文名称仅用于展示与输入提示，匹配始终按原始 token 比较。</p>
        {notice && <p className="quality-warning" role="status">{notice}</p>}
        {notices.length > 0 && <div className="quality-warning" role="status">
          <strong>自动取舍：{notices.length} 处</strong>
          <ul>{notices.map((item) => (
            <li key={`${item.name}｜${item.detail}`}>{item.name}：{item.detail}</li>
          ))}</ul>
        </div>}
        {failures.length > 0 && <div className="quality-warning" role="alert">
          <strong>失败文件：{failures.length} 个条目没有导入</strong>
          <ul>{failures.map((item) => (
            <li key={`${item.name}｜${item.reason}`}>{item.name}：{item.reason}</li>
          ))}</ul>
        </div>}
        <button className="batch-create-submit" disabled={busy || detectBusy}>
          {busy ? '正在导入…'
            : origin === 'gallery' ? '导入并返回画廊'
              : origin === 'expect' ? '导入并前往期望对比' : '导入并选择评分样本'}
        </button>
      </fieldset>
    </form>
  </div>;
}
