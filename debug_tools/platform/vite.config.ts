import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { rendererAssets } from '../card_renderer/asset-routes';

const platformRoot = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  plugins: [react(), rendererAssets(), {
    name: 'normalize-html-line-endings',
    transformIndexHtml: (html) => html.replace(/\r\n?/g, '\n'),
  }],
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
      '/debug/renderer/convert': {
        target: 'http://127.0.0.1:8888',
      },
      '/debug/batch': {
        target: 'http://127.0.0.1:8888',
      },
      '/debug/device/': {
        target: 'http://127.0.0.1:8888',
        ws: true,
      },
    },
  },
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
});
