import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// All requests to /api/* are forwarded to the platform backend so the
// browser stays single-origin and we don't need CORS headers on either
// service. The platform backend in turn proxies a subset of routes to the
// runtime.
//
// Override the target with PLATFORM_BACKEND_URL when running the backend
// somewhere other than the default :9000.
const BACKEND_URL =
  process.env.PLATFORM_BACKEND_URL ?? "http://127.0.0.1:9000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 9173,
    strictPort: true, // fail loudly on a taken port instead of drifting to 9174
    proxy: {
      "/api": {
        target: BACKEND_URL,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
        // SSE / streaming responses must not be buffered by the proxy.
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            proxyRes.headers["x-accel-buffering"] = "no";
          });
        },
      },
    },
  },
});
