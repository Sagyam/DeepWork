// Where the realistic city's models come from (docs/APP.md, "Model
// packs"). A release build downloads them on first run (the app's
// src-tauri/src/models.rs) and reads them through models://; until then the
// city is drawn with the low-poly kit. The dev server and the browser mock
// serve public/models as it is.
import { invoke } from "@tauri-apps/api/core";

export type ModelsStatus =
  | { state: "none" }
  | { state: "downloading"; done: number; total: number }
  | { state: "retrying"; done: number; total: number; error: string; retry_secs: number }
  /** `png`: PNGs are there too, for GPUs without BC7 (public/models; the pack has none). */
  | { state: "ready"; base: string; png?: boolean };

export async function modelsStatus(): Promise<ModelsStatus> {
  if (import.meta.env.DEV || !("__TAURI_INTERNALS__" in window)) {
    return { state: "ready", base: `${import.meta.env.BASE_URL}models/`, png: true };
  }
  try {
    return await invoke<ModelsStatus>("models");
  } catch (e) {
    console.warn("models", e);
    return { state: "none" };
  }
}
