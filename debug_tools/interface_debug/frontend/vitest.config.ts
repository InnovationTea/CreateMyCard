import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['../../tests/frontend/interface/**/*.test.{ts,tsx}'],
    environment: 'node',
    globals: true,
  },
});
