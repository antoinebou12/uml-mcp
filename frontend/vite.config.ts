/// <reference types="vitest/config" />
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Built assets ship inside the Python package (no Node needed to install uml-mcp).
export default defineConfig({
  base: "/admin/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: {
    outDir: path.resolve(__dirname, "../mcp_core/admin_ui/dist"),
    emptyOutDir: true,
    assetsDir: "assets",
    chunkSizeWarningLimit: 1200,
  },
  server: {
    // `npm run dev` + `uml-mcp admin --port 8765` (or uvicorn app:app --port 8765)
    proxy: {
      "/admin/api": "http://127.0.0.1:8765",
      "/mcp": "http://127.0.0.1:8765",
      "/health": "http://127.0.0.1:8765",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
