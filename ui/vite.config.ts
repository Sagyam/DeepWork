import { rmSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";

// Tauri loads the dev server on a fixed port and the built files from dist/.
export default defineConfig({
  clearScreen: false,
  server: { port: 5173, strictPort: true },
  build: { target: "es2022", chunkSizeWarningLimit: 1500 },
  plugins: [
    {
      // The realistic models (public/models) are downloaded on first run
      // (src/models.ts), not built into the app: keep them out of dist/,
      // which the binary embeds. The dev server still serves them.
      name: "no-models-in-dist",
      apply: "build",
      closeBundle() {
        rmSync(resolve(import.meta.dirname, "dist/models"), { recursive: true, force: true });
      },
    },
  ],
});
