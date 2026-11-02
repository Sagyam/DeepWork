import { invoke } from "@tauri-apps/api/core";
import { mockDaemon } from "./mock";
import type {
  Config,
  Finished,
  PendingConfig,
  Request,
  Response,
  RoutineInfo,
  Status,
  World,
} from "./proto";

const inTauri = "__TAURI_INTERNALS__" in window;

/** Thrown when the daemon cannot be reached; refusals are `DaemonRefusal`. */
export class Unreachable extends Error {}
export class DaemonRefusal extends Error {}

/**
 * Sends one request to deepworkd through the Tauri shell. In a plain browser
 * (`bun run dev`) a canned daemon answers instead, picked with `?mock=`.
 */
export async function call(request: Request): Promise<Response> {
  let resp: Response;
  try {
    resp = inTauri ? await invoke<Response>("daemon", { request }) : mockDaemon(request);
  } catch (e) {
    throw new Unreachable(String(e));
  }
  if (resp.type === "error") throw new DaemonRefusal(resp.message);
  return resp;
}

export async function status(): Promise<Status> {
  const r = await call({ type: "status" });
  if (r.type !== "status") throw new Error(`unexpected reply ${r.type}`);
  return r;
}

export async function world(): Promise<World> {
  const r = await call({ type: "world" });
  if (r.type !== "world") throw new Error(`unexpected reply ${r.type}`);
  return r;
}

export async function history(since: number): Promise<Finished[]> {
  const r = await call({ type: "history", since });
  if (r.type !== "history") throw new Error(`unexpected reply ${r.type}`);
  return r.sessions;
}

export async function routines(): Promise<{ routines: RoutineInfo[]; skip_tokens_per_week: number }> {
  const r = await call({ type: "routines" });
  if (r.type !== "routines") throw new Error(`unexpected reply ${r.type}`);
  return r;
}

export async function pendingConfig(): Promise<PendingConfig | null> {
  const r = await call({ type: "config_status" });
  if (r.type !== "config") throw new Error(`unexpected reply ${r.type}`);
  return r.pending;
}

export interface SavedConfig {
  /** The config in effect. */
  config: Config;
  /** What a waiting loosening change would apply, if there is one. */
  pendingConfig: Config | null;
  pending: PendingConfig | null;
  message: string;
}

export async function getConfig(): Promise<SavedConfig> {
  const r = await call({ type: "get_config" });
  if (r.type !== "config_data") throw new Error(`unexpected reply ${r.type}`);
  return { config: r.config, pendingConfig: r.pending_config, pending: r.pending, message: r.message };
}

export async function saveConfig(config: Config): Promise<SavedConfig> {
  const r = await call({ type: "set_config", config });
  if (r.type !== "config_data") throw new Error(`unexpected reply ${r.type}`);
  return { config: r.config, pendingConfig: r.pending_config, pending: r.pending, message: r.message };
}

export async function exportBackup(): Promise<unknown> {
  const r = await call({ type: "export" });
  if (r.type !== "backup") throw new Error(`unexpected reply ${r.type}`);
  return r.backup;
}

export async function importBackup(backup: unknown): Promise<{ sessions: number; message: string; pending: PendingConfig | null }> {
  const r = await call({ type: "import", backup });
  if (r.type !== "imported") throw new Error(`unexpected reply ${r.type}`);
  return r;
}
