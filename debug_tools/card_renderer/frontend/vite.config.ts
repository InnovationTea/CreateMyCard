import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { rendererAssets } from '../asset-routes';

export default defineConfig({
  plugins: [react(), rendererAssets()],
  base: '/debug/',
  server: {
    proxy: { '/debug/renderer/convert': { target: 'http://127.0.0.1:8888' } },
  },
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
});

