// File pickers for backups. Inside Tauri the native dialog hands back a path
// and the shell reads / writes it; in a plain browser (`bun run dev`) the same
// buttons download and upload through the DOM, so the flow stays testable.
import { invoke } from "@tauri-apps/api/core";
import { confirm as confirmDialog, open, save } from "@tauri-apps/plugin-dialog";

const inTauri = "__TAURI_INTERNALS__" in window;

/**
 * A yes / no question. Tauri's webview does not run `window.confirm`, so use
 * the native dialog there; the browser fallback keeps `bun run dev` usable.
 */
export async function confirmAction(text: string): Promise<boolean> {
  if (inTauri) return confirmDialog(text, { title: "DeepWork", kind: "warning" });
  return window.confirm(text);
}

/** Saves text and returns where it went, or null if the user cancelled. */
export async function saveText(defaultName: string, text: string): Promise<string | null> {
  if (inTauri) {
    const path = await save({
      defaultPath: defaultName,
      filters: [{ name: "DeepWork backup", extensions: ["json"] }],
    });
    if (typeof path !== "string") return null;
    await invoke("write_file", { path, contents: text });
    return path;
  }
  const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = defaultName;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return defaultName;
}

/** Asks for a text file and returns its name and contents, or null. */
export async function openText(): Promise<{ path: string; text: string } | null> {
  if (inTauri) {
    const path = await open({
      multiple: false,
      filters: [{ name: "DeepWork backup", extensions: ["json"] }],
    });
    if (typeof path !== "string") return null;
    const text = await invoke<string>("read_file", { path });
    return { path, text };
  }
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "application/json,.json";
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      input.remove();
      if (!file) return resolve(null);
      void file.text().then((text) => resolve({ path: file.name, text }));
    });
    input.style.display = "none";
    document.body.append(input);
    // A cancelled picker fires no event in some browsers; the promise simply
    // stays pending, which only leaks one hidden input element.
    input.click();
  });
}
