import { defineConfig, type ViteDevServer } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { existsSync, readFileSync } from 'node:fs';
import { extname, resolve } from 'node:path';
import { viteStaticCopy } from 'vite-plugin-static-copy';

const cesiumBuildRoot = resolve('node_modules/cesium/Build/Cesium');
const contentTypes: Record<string, string> = {
  '.css': 'text/css',
  '.glb': 'model/gltf-binary',
  '.jpg': 'image/jpeg',
  '.json': 'application/json',
  '.js': 'text/javascript',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.wasm': 'application/wasm',
};

function serveCesiumAssets(server: ViteDevServer): void {
  server.middlewares.use('/cesium', (request, response, next) => {
    const relativePath = decodeURIComponent((request.url ?? '').split('?')[0]).replace(/^\/+/, '');
    const filePath = resolve(cesiumBuildRoot, relativePath);
    if (!filePath.startsWith(cesiumBuildRoot) || !existsSync(filePath)) {
      next();
      return;
    }
    response.statusCode = 200;
    response.setHeader('Content-Type', contentTypes[extname(filePath).toLowerCase()] ?? 'application/octet-stream');
    response.setHeader('Cache-Control', 'no-store');
    response.end(readFileSync(filePath));
  });
}

export default defineConfig({
  plugins: [
    react(),
    { name: 'serve-cesium-assets', configureServer: serveCesiumAssets },
    viteStaticCopy({
      targets: [
        { src: 'node_modules/cesium/Build/Cesium/Workers', dest: 'cesium' },
        { src: 'node_modules/cesium/Build/Cesium/ThirdParty', dest: 'cesium' },
        { src: 'node_modules/cesium/Build/Cesium/Assets', dest: 'cesium' },
        { src: 'node_modules/cesium/Build/Cesium/Widgets', dest: 'cesium' },
        { src: 'node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs', dest: '.' },
      ],
    }),
  ],
  define: {
    CESIUM_BASE_URL: JSON.stringify('/cesium/'),
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/audio-cache': 'http://127.0.0.1:8000',
    },
  },
});
