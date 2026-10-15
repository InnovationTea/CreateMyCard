import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { importQualityBatch, type QualityImportSample } from '../batchApi';

const MAX_BYTES = 64 * 1024 * 1024;

async function dslText(file: File) {
  // 保留 UTF-8 BOM 与换行字节，避免旧清单的 SHA-256 因浏览器解码而失配。
  return new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(await file.arrayBuffer());
}

function imageData(file: File): Promise<string> {
  if (file.size > 8 * 1024 * 1024) throw new Error('单张截图不能超过 8 MiB');
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.onerror = () => reject(new Error('图片读取失败'));
    reader.readAsDataURL(file);
  });
}

type ManifestRow = {
  id: string; query: string; size: string; dsl: string; image: string; cardspec?: string;
  expectedIntents?: string[];
  sourceSha256?: string; imageSha256?: string;
};

// 只读取用户通过文件选择器明确选择的文件；清单中的路径不能访问电脑其他目录。
export async function readImportFolder(files: File[]): Promise<QualityImportSample[]> {
  const byPath = new Map<string, File>();
  for (const file of files) {
    const relative = file.webkitRelativePath || file.name;
    const path = relative.includes('/') ? relative.slice(relative.indexOf('/') + 1) : relative;
    if (byPath.has(path)) throw new Error('选择的文件路径重复');
    byPath.set(path, file);
  }
  const manifests = ['quality-import.json', 'dataset-manifest.json'].filter((name) => byPath.has(name));
  if (manifests.length !== 1) throw new Error('所选目录根部需有且只有一份 quality-import.json 或 dataset-manifest.json');
  const manifestFile = byPath.get(manifests[0])!;
  if (manifestFile.size > 8 * 1024 * 1024) throw new Error('清单过大');
  const manifest = JSON.parse(await manifestFile.text());
  let rows: ManifestRow[];
  if (manifests[0] === 'dataset-manifest.json') {
    if (!Array.isArray(manifest.cards)) throw new Error('旧交付清单缺少 cards');
    rows = manifest.cards.map((card: { key: string; query: string; size: string; files: Array<{role: string; path: string; sha256?: string}> }) => {
      if (!Array.isArray(card.files) || typeof card.key !== 'string') throw new Error('旧交付清单的卡片记录无效');
      const role = (name: string) => {
        const matches = card.files.filter((file) => file.role === name);
        if (matches.length > 1) throw new Error(`重复的 ${name} 文件`);
        return matches[0];
      };
      const dsl = role('dsl'), image = role('image');
      if (!dsl || !image) throw new Error('每条卡片都必须有 DSL 和图片');
      return { id: card.key.replaceAll('/', '__'), query: card.query, size: card.size,
        dsl: dsl.path, image: image.path, cardspec: role('cardspec')?.path,
        sourceSha256: dsl.sha256, imageSha256: image.sha256 };
    });
  } else rows = manifest.samples;
  if (!Array.isArray(rows) || !rows.length || rows.length > 500) throw new Error('每次导入 1–500 条；大数据集请拆分清单');
  let bytes = 0;
  const requiredFile = (path: string): File => {
    if (typeof path !== 'string' || path.includes('..') || path.includes('\\') || path.includes(':') || path.startsWith('/')) {
      throw new Error('清单文件路径必须是目录内的相对路径');
    }
    const file = byPath.get(path);
    if (!file) throw new Error(`缺少文件：${path}`);
    bytes += file.size;
    if (bytes > 40 * 1024 * 1024) throw new Error('本批文件超过 40 MiB，请分批导入');
    return file;
  };
  const samples: QualityImportSample[] = [];
  for (const row of rows) {
    const dsl = requiredFile(row.dsl);
    if (dsl.size > 2 * 1024 * 1024) throw new Error('单条 DSL 不能超过 2 MiB');
    const image = requiredFile(row.image);
    const spec = row.cardspec ? requiredFile(row.cardspec) : undefined;
    samples.push({ id: row.id, query: row.query, size: row.size, dsl: await dslText(dsl),
      imageBase64: await imageData(image), cardSpec: spec ? JSON.parse(await spec.text()) : undefined,
      expectedIntents: row.expectedIntents, sourceSha256: row.sourceSha256, imageSha256: row.imageSha256 });
  }
  return samples;
}

export function QualityImportRoute() {
  const navigate = useNavigate();
  const [mode, setMode] = useState('single');
  const [name, setName] = useState('外部卡片评估');
  const [source, setSource] = useState('unknown');
  const [id, setId] = useState('Q001');
  const [query, setQuery] = useState('');
  const [size, setSize] = useState('2x2');
  const [dsl, setDsl] = useState<File>();
  const [image, setImage] = useState<File>();
  const [spec, setSpec] = useState<File>();
  const [folder, setFolder] = useState<File[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit() {
    setError(''); setBusy(true);
    try {
      let samples: QualityImportSample[];
      if (mode === 'folder') samples = await readImportFolder(folder);
      else {
        if (!dsl || !image || !query.trim()) throw new Error('请提供 DSL、截图和 Query');
        if (dsl.size > 2 * 1024 * 1024 || (spec?.size ?? 0) > 2 * 1024 * 1024) throw new Error('JSON 文件不能超过 2 MiB');
        samples = [{ id, query, size, dsl: await dslText(dsl), imageBase64: await imageData(image),
          cardSpec: spec ? JSON.parse(await spec.text()) : undefined }];
      }
      const payload = { name, imageSource: source, samples };
      if (new Blob([JSON.stringify(payload)]).size > MAX_BYTES) throw new Error('上传内容超过 64 MiB，请分批');
      const run = await importQualityBatch(payload);
      navigate(`/quality?runId=${encodeURIComponent(run.runId)}`);
    } catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  }
  return <div className="quality-page">
    <header className="batch-center-header"><div><h1>导入已有卡片</h1><p>DSL＋截图＋Query；使用与 Web 批跑相同的评分模型，不调用生成模型、不修改原始文件。</p></div><Link to="/quality">返回评分</Link></header>
    {error && <div role="alert" className="batch-error">{error}</div>}
    <form onSubmit={(event) => { event.preventDefault(); void submit(); }}>
      <fieldset className="quality-card" disabled={busy}>
        <legend>选择输入</legend>
        <label className="quality-field">批次名称<input required value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="quality-field">导入方式<select value={mode} onChange={(e) => setMode(e.target.value)}><option value="single">单条 DSL＋图片</option><option value="folder">批量文件夹</option></select></label>
        <label className="quality-field">截图来源<select value={source} onChange={(e) => setSource(e.target.value)}><option value="unknown">来源未知</option><option value="web">Web 截图</option><option value="native">模拟器／真机截图</option></select></label>
        {mode === 'single' ? <>
          <label className="quality-field">样本 ID<input required value={id} onChange={(e) => setId(e.target.value)} /></label>
          <label className="quality-field">Query<textarea required value={query} onChange={(e) => setQuery(e.target.value)} /></label>
          <label className="quality-field">尺寸<select value={size} onChange={(e) => setSize(e.target.value)}>{['2x2','2x4','4x4'].map((s) => <option key={s}>{s}</option>)}</select></label>
          <label className="quality-field">DSL 文件<input required type="file" accept=".json,.jsonl" onChange={(e) => setDsl(e.target.files?.[0])} /></label>
          <label className="quality-field">截图文件<input required type="file" accept="image/png,image/jpeg" onChange={(e) => setImage(e.target.files?.[0])} /></label>
          <label className="quality-field">CardSpec（可选）<input type="file" accept=".json" onChange={(e) => setSpec(e.target.files?.[0])} /></label>
        </> : <>
          <label className="quality-field">数据文件夹<input type="file" multiple {...{ webkitdirectory: '' }} onChange={(e) => setFolder(Array.from(e.target.files ?? []))} /></label>
          <p>选择包含 quality-import.json 或旧交付 dataset-manifest.json 的目录。每次最多 500 条、文件共 40 MiB，不自动截取或丢弃样本。</p>
          <details><summary>批量清单格式</summary><pre>{JSON.stringify({ samples: [{id: 'Q001',query: '显示天气',size: '2x2',dsl: 'dsl/Q001.genui.jsonl',image: 'images/Q001.png',cardspec: 'dsl/Q001.cardspec.json'}]}, null, 2)}</pre></details>
        </>}
        <p className="quality-warning">导入后请确认样本并运行评分。请上传与 DSL 对应的截图；缺少 OCR 依赖时显示待评。</p>
        <button className="batch-create-submit" disabled={busy}>{busy ? '正在导入…' : '导入并选择评分样本'}</button>
      </fieldset>
    </form>
  </div>;
}
