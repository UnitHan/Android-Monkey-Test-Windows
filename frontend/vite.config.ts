/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8765" },
    // Tauri watches Rust sources itself. Vite must not watch DLLs being linked on Windows.
    watch: { ignored: ["**/src-tauri/**"] },
  },
  test: { environment: "jsdom" },
});
