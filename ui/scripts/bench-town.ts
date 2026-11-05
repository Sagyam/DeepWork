// Benchmarks the showcase town (town.html) on this machine's GPU, headless:
//
//   bun run dev &                                  # the dev server, on :5173
//   bun scripts/bench-town.ts "view=overview" "view=downtown&opt=4" ...
//
// Each argument is a query for /town.html?bench&...; the page parks the
// traffic, renders 240 settled frames and reports frame, CPU and GPU time
// (GPU from timer queries), draw calls and triangles. HIDE=woods,streets
// hides categories after load (cost per category); EVAL="js" runs code in
// the page after load. CHROMIUM sets the browser (default
// /usr/bin/chromium); the window is 1600 x 900 at a 1.5x scale, like a
// laptop panel.
import { chromium } from "playwright-core";

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM ?? "/usr/bin/chromium",
  args: ["--headless=new", "--ignore-gpu-blocklist", "--enable-gpu", "--use-angle=gl", "--disable-gpu-vsync", "--disable-frame-rate-limit"],
});
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.5 });
const gpu = await (await ctx.newPage()).evaluate(() => {
  const gl = document.createElement("canvas").getContext("webgl2")!;
  const d = gl.getExtension("WEBGL_debug_renderer_info");
  return d ? String(gl.getParameter(d.UNMASKED_RENDERER_WEBGL)) : "unknown GPU";
});
console.log(gpu);
type Stat = { avg: number; p99: number };
for (const qs of process.argv.slice(2)) {
  const p = await ctx.newPage();
  p.on("pageerror", (e) => console.error("pageerror", e.message));
  await p.goto(`${process.env.BASE ?? "http://localhost:5173"}/town.html?bench&${qs}`);
  if (process.env.HIDE || process.env.EVAL) {
    await p.waitForFunction(() => document.title === "ready", null, { timeout: 240000 });
    if (process.env.HIDE)
      await p.evaluate((h) => {
        const t = (window as unknown as { town: { cats: Record<string, { visible: boolean }> } }).town;
        for (const c of h.split(",")) t.cats[c].visible = false;
      }, process.env.HIDE);
    if (process.env.EVAL) await p.evaluate(process.env.EVAL);
    await p.evaluate(() => ((window as unknown as { bench?: object }).bench = undefined));
  }
  await p.waitForFunction(() => (window as unknown as { bench?: object }).bench, null, { timeout: 300000, polling: 1000 });
  const r = (await p.evaluate(() => (window as unknown as { bench: object }).bench)) as { frame: Stat; cpu: Stat; gpu: Stat; draws: number; tris: number; canvas: number[] };
  const f = (x: Stat) => `${x.avg.toFixed(1)} (p99 ${x.p99.toFixed(1)})`.padEnd(17);
  console.log(`${qs.padEnd(28)} gpu ${f(r.gpu)} cpu ${f(r.cpu)} fps ${(1000 / r.frame.avg).toFixed(1).padStart(5)}  draws ${String(r.draws).padStart(5)}  tris ${(r.tris / 1e6).toFixed(2)}M  ${r.canvas.join("x")}`);
  await p.close();
}
await browser.close();
