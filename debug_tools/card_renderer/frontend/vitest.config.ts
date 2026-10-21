import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    include: ['../../tests/frontend/card_renderer/**/*.test.{ts,tsx}'],
    environment: 'node',
    globals: true,
  },
});
