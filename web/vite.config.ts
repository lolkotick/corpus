import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// base: './' — сайт работает из любой папки (GitHub Pages /corpus/, локальный preview).
// Маршрутизация через HashRouter, поэтому серверные перенаправления не нужны.
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  build: {
    target: 'es2022',
    chunkSizeWarningLimit: 700,
  },
});
