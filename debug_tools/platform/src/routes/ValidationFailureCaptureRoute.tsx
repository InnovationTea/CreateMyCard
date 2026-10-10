import { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import {
  CardPreview,
  parseInput,
  resolveCardSize,
  type RendererDocument,
} from '@widget-debug/card-renderer';
import { getValidationFailures } from '../batchApi';
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

async function loadCaptureItems(
  runId: string,
  offset: number,
  limit: number,
): Promise<CaptureItem[]> {
  const failures = await getValidationFailures(runId);
  const validations = failures.flatMap((failure) => failure.validations.map((validation) => ({
    failure,
    validation,
  }))).slice(offset, offset + limit);
  return validations.map(({ failure, validation }) => {
    try {
      const cardSize = resolveCardSize(null, failure.query, failure.size);
      const document = parseInput(validation.dsl, { cardSize });
      return {
        id: validation.captureId,
        document,
        size: renderedCardSize(document, cardSize),
        error: '',
      };
    } catch (reason) {
      return {
        id: validation.captureId,
        document: null,
        size: failure.size === '2x4' ? '2x4' : '2x2',
        error: reason instanceof Error ? reason.message : String(reason),
      };
    }
  });
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
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
  });
}

export function ValidationFailureCaptureRoute() {
  const { runId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const offset = Math.max(0, Number(searchParams.get('offset')) || 0);
  const limit = Math.max(1, Number(searchParams.get('limit')) || 20);
  const [items, setItems] = useState<CaptureItem[]>([]);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.galleryCapture = 'loading';
    loadCaptureItems(runId, offset, limit)
      .then(setItems)
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => setLoaded(true));
    return () => { delete document.documentElement.dataset.galleryCapture; };
  }, [limit, offset, runId]);

  const renderedCount = useMemo(
    () => items.filter((item) => item.document !== null).length,
    [items],
  );

  useEffect(() => {
    if (!loaded) return;
    waitForAssets()
      .catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)))
      .finally(() => { document.documentElement.dataset.galleryCapture = 'ready'; });
  }, [items, loaded]);

  return <main className="gallery-capture-page" aria-label="校验失败 DSL 截图页面">
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
    {loaded && !items.length && !error
      && <div className="gallery-capture-fatal">批跑中没有 VALIDATION_FAILED 样本</div>}
    <output hidden>{renderedCount}</output>
  </main>;
}
