// Frame timing for scripts/bench-app.ts (`?bench` in the URL): wall time
// between frames, CPU time in the render call and GPU time from timer
// queries, over 240 settled frames. Once they are in, `window.bench` holds
// the averages and the 99th percentiles (the 1% lows), draw calls and
// triangles. A dev tool; the app never sets `?bench`.
//
// Headless Chromium queues frames and its timer queries count more than the
// frame (an empty scene reads ~20 ms). `&finish` waits for the GPU before
// and after each frame instead, so `cpu` is the frame's true cost.
import * as THREE from "three";

const WARM = 90;
const N = 240;

type Stat = { avg: number; p99: number; max: number };

function stat(a: number[]): Stat {
  const v = [...a].sort((x, y) => x - y);
  if (!v.length) return { avg: 0, p99: 0, max: 0 };
  return { avg: v.reduce((s, x) => s + x, 0) / v.length, p99: v[Math.min(v.length - 1, Math.floor(v.length * 0.99))], max: v[v.length - 1] };
}

export class Bench {
  private gl: WebGL2RenderingContext;
  private ext: { TIME_ELAPSED_EXT: number; GPU_DISJOINT_EXT: number } | null;
  private pending: WebGLQuery[] = [];
  private query: WebGLQuery | null = null;
  private frames = 0;
  private last = 0;
  private t0 = 0;
  private frame: number[] = [];
  private cpu: number[] = [];
  private gpu: number[] = [];
  private finish = new URLSearchParams(location.search).has("finish");

  constructor(private renderer: THREE.WebGLRenderer) {
    this.gl = renderer.getContext() as WebGL2RenderingContext;
    this.ext = this.gl.getExtension("EXT_disjoint_timer_query_webgl2");
    renderer.info.autoReset = false;
  }

  begin() {
    if (this.finish) this.gl.finish();
    this.t0 = performance.now();
    this.renderer.info.reset();
    if (this.ext && this.pending.length < 4) {
      this.query = this.gl.createQuery()!;
      this.gl.beginQuery(this.ext.TIME_ELAPSED_EXT, this.query);
    }
  }

  end() {
    const gl = this.gl;
    if (this.finish) gl.finish();
    if (this.query) {
      gl.endQuery(this.ext!.TIME_ELAPSED_EXT);
      this.pending.push(this.query);
      this.query = null;
    }
    while (this.pending.length && gl.getQueryParameter(this.pending[0], gl.QUERY_RESULT_AVAILABLE)) {
      const q = this.pending.shift()!;
      if (!gl.getParameter(this.ext!.GPU_DISJOINT_EXT) && this.frames > WARM) this.gpu.push(gl.getQueryParameter(q, gl.QUERY_RESULT) / 1e6);
      gl.deleteQuery(q);
    }
    const now = performance.now();
    if (++this.frames > WARM) {
      this.frame.push(now - this.last);
      this.cpu.push(now - this.t0);
    }
    this.last = now;
    if (this.frames === WARM + N) {
      const i = this.renderer.info;
      const c = this.renderer.domElement;
      (window as unknown as { bench: object }).bench = { frame: stat(this.frame), cpu: stat(this.cpu), gpu: stat(this.gpu), draws: i.render.calls, tris: i.render.triangles, canvas: [c.width, c.height] };
    }
  }
}
