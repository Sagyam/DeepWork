import { execSync } from "node:child_process";
import { readFileSync, rmSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig } from "vite";

// What this build is, for Settings > About: the workspace's CalVer, the
// commit and when it was built (SOURCE_DATE_EPOCH if set, for reproducible
// builds). DEEPWORK_COMMIT overrides git where the tree has no history.
const cargo = readFileSync(resolve(import.meta.dirname, "../Cargo.toml"), "utf8");
const git = (args: string) => {
  try {
    return execSync(`git ${args}`, { cwd: import.meta.dirname, stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    return "";
  }
};
const epoch = Number(process.env.SOURCE_DATE_EPOCH);
const BUILD = {
  version: /^version\s*=\s*"([^"]+)"/m.exec(cargo)?.[1] ?? "unknown",
  commit: process.env.DEEPWORK_COMMIT || git("rev-parse --short=10 HEAD") || "unknown",
  committed: git("log -1 --format=%cI"),
  built: (epoch ? new Date(epoch * 1000) : new Date()).toISOString(),
};

// Tauri loads the dev server on a fixed port and the built files from dist/.
export default defineConfig({
  clearScreen: false,
  define: { __BUILD__: JSON.stringify(BUILD) },
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
