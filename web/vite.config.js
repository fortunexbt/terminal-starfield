import { defineConfig } from 'vite';

export default defineConfig({
  // The worker imports the Python package from the repository root.
  server: { fs: { allow: ['..'] } },
  build: { target: 'es2022' },
  worker: { format: 'es' },
});
