import { invoke } from "@tauri-apps/api/core";
import { mockDaemon } from "./mock";
import type { Request, Response, Status, World } from "./proto";

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
