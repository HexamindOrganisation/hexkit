import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Resolve react and agent-ui source from the project root's node_modules / src.
  resolve: {
    preserveSymlinks: true,
  },
  server: {
    port: 5173,
    open: true,
  },
});
