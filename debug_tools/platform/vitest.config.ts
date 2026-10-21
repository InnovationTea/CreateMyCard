import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    include: ['../tests/frontend/platform/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['../tests/frontend/platform/setup.ts'],
  },
});
