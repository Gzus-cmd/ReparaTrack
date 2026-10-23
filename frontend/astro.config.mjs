import { defineConfig } from 'astro/config';
import node from '@astrojs/node';

// SSR: cada página hace `serverFetch` en el frontmatter contra FastAPI
// (http://127.0.0.1:8000 por defecto, sobrescribible con API_BASE_URL).
// El proxy de `/api` cubre las llamadas cliente→servidor en desarrollo.
export default defineConfig({
  output: 'server',
  adapter: node({ mode: 'standalone' }),
  vite: {
    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
  },
});
