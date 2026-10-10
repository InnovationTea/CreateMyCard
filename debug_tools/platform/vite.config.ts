import { defineConfig, type Plugin, type ViteDevServer } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { extname, resolve, sep } from 'node:path';
import type { IncomingMessage, ServerResponse } from 'node:http';

const platformRoot = fileURLToPath(new URL('.', import.meta.url));
const resourceRoot = resolve(fileURLToPath(
  new URL('../../render/platform/public/resources/', import.meta.url),
));
const backgroundRoot = resolve(fileURLToPath(
  new URL('../../render/platform/public/background_assets/', import.meta.url),
));
const harmonyFontRoot = resolve(fileURLToPath(
  new URL('../../render/platform/public/fonts/harmonyos/', import.meta.url),
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

function rendererAssets(): Plugin {
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

export default defineConfig({
  plugins: [react(), rendererAssets()],
  base: '/debug/',
  resolve: {
    alias: {
      '@platform': `${platformRoot}/src`,
      '@widget-debug/end-to-end': fileURLToPath(
        new URL('../end_to_end_debug/frontend/src/index.ts', import.meta.url),
      ),
      '@widget-debug/interface': fileURLToPath(
        new URL('../interface_debug/frontend/src/index.ts', import.meta.url),
      ),
      '@widget-debug/card-renderer': fileURLToPath(
        new URL('../card_renderer/frontend/src/index.ts', import.meta.url),
      ),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Keep the SPA itself local so interface/renderer still work without
      // starting the optional Agent backend.  Only Agent/session endpoints
      // are proxied; microservice WebSockets use the browser-configured URL.
      '/debug/e2e/ws': {
        target: 'http://127.0.0.1:8888',
        ws: true,
      },
      '/debug/agent/ws': {
        target: 'http://127.0.0.1:8888',
        ws: true,
      },
      '/debug/health': {
        target: 'http://127.0.0.1:8888',
      },
      '/debug/skills': {
        target: 'http://127.0.0.1:8888',
      },
      '/debug/artifact': {
        target: 'http://127.0.0.1:8888',
      },
      '/debug/batch': {
        target: 'http://127.0.0.1:8888',
      },
    },
  },
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
});
