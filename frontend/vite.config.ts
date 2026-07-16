import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on 5173; /api is proxied to the backend so the frontend can use
// relative URLs. In local dev the backend runs on localhost:8000; in Docker the
// built static app is served by nginx, which proxies /api to backend:8000
// (see nginx.conf) — so the dev-server proxy only matters locally.
const API_TARGET = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
