import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  CardPreview,
  parseInput,
  resolveCardSize,
  type RendererDocument,
} from '@widget-debug/card-renderer';
import {
  getBatchRun,
  getBatchSample,
  type BatchAttempt,
  type BatchRun,
  type BatchSampleDetail,
} from '../batchApi';
import { DEFAULT_ASSET_BASE_URL } from '../config';

type CaptureItem = {
  id: string;
  document: RendererDocument | null;
  size: '2x2' | '2x4';
  error: string;
};

function renderedCardSize(
  document: RendererDocument,
  resolved: 'auto' | '2x2' | '2x4',
): '2x2' | '2x4' {
  if (resolved === '2x2' || resolved === '2x4') return resolved;
  return document.surface.width > document.surface.height ? '2x4' : '2x2';
}

function finalAttempt(detail: BatchSampleDetail): BatchAttempt | null {
  if (!detail.attempts.length) return null;
  const index = detail.summary.finalAttempt;
  if (typeof index === 'number') {
    return detail.attempts.find((item) => item.name === `attempt_${String(index).padStart(3, '0')}`)
      ?? detail.attempts.at(-1) ?? null;
  }
  return detail.attempts.at(-1) ?? null;
}

async function loadCaptureItems(run: BatchRun): Promise<CaptureItem[]> {
  const items: CaptureItem[] = [];
  for (const sample of run.samples ?? []) {
    try {
      const detail = await getBatchSample(run.runId, sample.id);
      const attempt = finalAttempt(detail);
      const source = attempt?.genui;
      if (!source) {
        const sampleSize = resolveCardSize(null, sample.query, sample.size);
        items.push({
          id: sample.id,
          document: null,
          size: sampleSize === '2x4' ? '2x4' : '2x2',
          error: sample.error || '该样本没有可渲染的 GenUI',
        });
        continue;
      }
      const cardSize = resolveCardSize(attempt.blocks, sample.query, sample.size);
      const document = parseInput(source, { cardSize });
      items.push({
        id: sample.id,
        document,
        size: renderedCardSize(document, cardSize),
        error: '',
      });
    } catch (reason) {
      items.push({
        id: sample.id,
        document: null,
        size: resolveCardSize(null, sample.query, sample.size) === '2x4' ? '2x4' : '2x2',
        error: reason instanceof Error ? reason.message : String(reason),
      });
    }
  }
  return items;
}

async function waitForAssets(): Promise<void> {
  if (document.fonts) await document.fonts.ready;
  const images = Array.from(document.images);
  await Promise.all(images.map((image) => {
    if (image.complete) return Promise.resolve();
    return new Promise<void>((resolve) => {
      image.addEventListener('load', () => resolve(), { once: true });
      image.addEventListener('error', () => resolve(), { once: true });
    });
  }));
  await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
}

export function BatchGalleryCaptureRoute() {
  const { runId = '' } = useParams();
  const [items, setItems] = useState<CaptureItem[]>([]);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.galleryCapture = 'loading';
    getBatchRun(runId)
      .then(loadCaptureItems)
      .then((nextItems) => {
        setItems(nextItems);
        setLoaded(true);
      })
      .catch((reason) => {
        setError(reason instanceof Error ? reason.message : String(reason));
        setLoaded(true);
      });
    return () => { delete document.documentElement.dataset.galleryCapture; };
  }, [runId]);

  const renderedCount = useMemo(
    () => items.filter((item) => item.document !== null).length,
    [items],
  );

  useEffect(() => {
    if (!loaded) return;
    waitForAssets()
      .then(() => { document.documentElement.dataset.galleryCapture = 'ready'; })
      .catch((reason) => {
        setError(reason instanceof Error ? reason.message : String(reason));
        document.documentElement.dataset.galleryCapture = 'ready';
      });
  }, [items, loaded]);

  return <main className="gallery-capture-page" aria-label="批跑画廊截图页面">
    {error && <div className="gallery-capture-fatal" role="alert">{error}</div>}
    {items.map((item) => (
      <section
        className="gallery-capture-item"
        data-sample-id={item.id}
        data-card-size={item.size}
        data-capture-error={item.error}
        key={item.id}
      >
        {item.document
          ? <div className="gallery-capture-card"><CardPreview
              document={item.document}
              assetBaseUrl={DEFAULT_ASSET_BASE_URL}
            /></div>
          : <div className="gallery-capture-placeholder">{item.error}</div>}
      </section>
    ))}
    {loaded && !items.length && !error && <div className="gallery-capture-fatal">批跑没有样本</div>}
    <output hidden>{renderedCount}</output>
  </main>;
}
