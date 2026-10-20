import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath, URL } from 'node:url';
import type { Plugin, ViteDevServer } from 'vite';

const resourceRoot = resolve(fileURLToPath(
  new URL('../a2ui_render/entry/src/main/resources/', import.meta.url),
));
const backgroundRoot = resolve(fileURLToPath(
  new URL('./assets/background_assets/', import.meta.url),
));
const harmonyFontRoot = resolve(fileURLToPath(
  new URL('./assets/fonts/harmonyos/', import.meta.url),
));

const CONTENT_TYPES: Record<string, string> = {
  '.gif': 'image/gif',
  '.jpeg': 'image/jpeg',
  '.jpg': 'image/jpeg',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ttf': 'font/ttf',
  '.webp': 'image/webp',
};

export function rendererAssets(): Plugin {
  return {
    name: 'renderer-assets',
    configureServer(server: ViteDevServer) {
      const serve = (prefix: string, root: string) => {
        server.middlewares.use(prefix, async (
          request: IncomingMessage,
          response: ServerResponse,
          next: () => void,
        ) => {
          const relative = decodeURIComponent((request.url ?? '').split('?')[0]).replace(/^\/+/, '');
          const candidate = resolve(root, relative);
          if (candidate !== root && !candidate.startsWith(`${root}${sep}`)) {
            response.statusCode = 400;
            response.end('invalid asset path');
            return;
          }
          try {
            if (!(await stat(candidate)).isFile()) {
              next();
              return;
            }
            response.setHeader('Content-Type', CONTENT_TYPES[extname(candidate).toLowerCase()]
              ?? 'application/octet-stream');
            createReadStream(candidate).pipe(response);
          } catch {
            next();
          }
        });
      };
      serve('/resources', resourceRoot);
      serve('/background_assets', backgroundRoot);
      serve('/fonts/harmonyos', harmonyFontRoot);
    },
  };
}
