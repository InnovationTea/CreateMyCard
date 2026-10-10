import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { extname, resolve, sep } from 'node:path';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig, type Plugin, type ViteDevServer } from 'vite';
import react from '@vitejs/plugin-react';

const harmonyFontRoot = resolve(fileURLToPath(
  new URL('../../../render/platform/public/fonts/harmonyos/', import.meta.url),
));

const CONTENT_TYPES: Record<string, string> = {
  '.ttf': 'font/ttf',
};

function harmonyFontAssets(): Plugin {
  return {
    name: 'harmony-font-assets',
    configureServer(server: ViteDevServer) {
      server.middlewares.use('/fonts/harmonyos', async (
        request: IncomingMessage,
        response: ServerResponse,
        next: () => void,
      ) => {
        const relative = decodeURIComponent((request.url ?? '').split('?')[0])
          .replace(/^\/+/, '');
        const candidate = resolve(harmonyFontRoot, relative);
        if (candidate !== harmonyFontRoot && !candidate.startsWith(`${harmonyFontRoot}${sep}`)) {
          response.statusCode = 400;
          response.end('invalid asset path');
          return;
        }
        try {
          if (!(await stat(candidate)).isFile()) {
            next();
            return;
          }
          response.setHeader(
            'Content-Type',
            CONTENT_TYPES[extname(candidate).toLowerCase()] ?? 'application/octet-stream',
          );
          createReadStream(candidate).pipe(response);
        } catch {
          next();
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), harmonyFontAssets()],
  base: '/debug/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
});

