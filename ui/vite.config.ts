import { defineConfig } from "vite";

// Tauri loads the dev server on a fixed port and the built files from dist/.
export default defineConfig({
  clearScreen: false,
  server: { port: 5173, strictPort: true },
  build: { target: "es2022", chunkSizeWarningLimit: 1500 },
});
