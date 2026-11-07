/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Flask serves the built SPA from the root path, so assets resolve at `/`.
// In development the Vite server proxies API and WebSocket traffic to Flask on :5000.
const BACKEND = process.env.BACKEND_URL ?? 'http://localhost:5000';

export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true, ws: true },
      '/v1': { target: BACKEND, changeOrigin: true },
      '/legacy': { target: BACKEND, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
});
