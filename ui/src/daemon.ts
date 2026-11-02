import { invoke } from "@tauri-apps/api/core";
import { mockDaemon } from "./mock";
import type { Finished, PendingConfig, Request, Response, RoutineInfo, Status, World } from "./proto";

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
