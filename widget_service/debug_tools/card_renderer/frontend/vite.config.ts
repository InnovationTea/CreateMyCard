import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/debug/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
});

