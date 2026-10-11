import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The API and the pictures/video come from the local Python backend on port 8000.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/files': 'http://127.0.0.1:8000',
    },
  },
});
