// Benchmarks the app's city (index.html against the mock daemon) on this
// machine's GPU, headless, as bench-town.ts does the showcase town:
//
//   bun run dev &                                  # the dev server, on :5173
//   bun scripts/bench-app.ts "mock=metropolis" "mock=city&hour=22" ...
//
// Each argument is a query for /?bench&...; `cam=x,y,z,tx,ty,tz` fixes the
// camera (otherwise the city's own opening view, turning slowly). The page
// renders 240 settled frames and reports frame, CPU and GPU time (GPU from
// timer queries), draw calls and triangles. SHOTS=dir also saves a
// screenshot per query. CHROMIUM sets the browser (default
// /usr/bin/chromium); the window is 1600 x 900 at a 1.5x scale.
import { chromium } from "playwright-core";

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM ?? "/usr/bin/chromium",
  args: ["--headless=new", "--ignore-gpu-blocklist", "--enable-gpu", "--use-angle=gl", "--disable-gpu-vsync", "--disable-frame-rate-limit"],
});
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.5 });
type Stat = { avg: number; p99: number };
for (const qs of process.argv.slice(2)) {
  const p = await ctx.newPage();
  p.on("pageerror", (e) => console.error("pageerror", e.message));
  p.on("console", (m) => m.type() === "error" && console.error("console", m.text()));
  await p.goto(`${process.env.BASE ?? "http://localhost:5173"}/?bench&${qs}`);
  await p.waitForFunction(() => (window as unknown as { bench?: object }).bench, null, { timeout: 300000, polling: 500 });
  const r = (await p.evaluate(() => (window as unknown as { bench: object }).bench)) as { frame: Stat; cpu: Stat; gpu: Stat; draws: number; tris: number; canvas: number[] };
  const f = (x: Stat) => `${x.avg.toFixed(1)} (p99 ${x.p99.toFixed(1)})`.padEnd(17);
  console.log(`${qs.padEnd(40)} gpu ${f(r.gpu)} cpu ${f(r.cpu)} fps ${(1000 / r.frame.avg).toFixed(1).padStart(5)} (1% low ${(1000 / r.frame.p99).toFixed(1)})  draws ${String(r.draws).padStart(5)}  tris ${(r.tris / 1e6).toFixed(2)}M  ${r.canvas.join("x")}`);
  if (process.env.EVAL) {
    // A/B in the same page: run EVAL (e.g. scripts/bench-texbase.js), restart the bench, measure again.
    await p.evaluate(process.env.EVAL);
    await p.evaluate(() => {
      const b = (window as unknown as { city: { bench: Record<string, unknown> } }).city.bench;
      Object.assign(b, { frames: 0, frame: [], cpu: [], gpu: [] });
      (window as unknown as { bench?: object }).bench = undefined;
    });
    await p.waitForFunction(() => (window as unknown as { bench?: object }).bench, null, { timeout: 300000, polling: 500 });
    const r2 = (await p.evaluate(() => (window as unknown as { bench: object }).bench)) as typeof r;
    console.log(`${"  + EVAL".padEnd(40)} gpu ${f(r2.gpu)} cpu ${f(r2.cpu)} fps ${(1000 / r2.frame.avg).toFixed(1).padStart(5)} (1% low ${(1000 / r2.frame.p99).toFixed(1)})`);
  }
  if (process.env.LUMA) {
    // Mean brightness (0-255) of the lower middle of the view, clear of the HUD: for matching the look across changes.
    const png = (await p.screenshot({ clip: { x: 360, y: 560, width: 1200, height: 330 } })).toString("base64");
    const luma = await p.evaluate(async (b64) => {
      const img = await createImageBitmap(await (await fetch(`data:image/png;base64,${b64}`)).blob());
      const c = new OffscreenCanvas(img.width, img.height);
      const x = c.getContext("2d")!;
      x.drawImage(img, 0, 0);
      const d = x.getImageData(0, 0, img.width, img.height).data;
      let sum = 0;
      for (let i = 0; i < d.length; i += 4) sum += 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
      return sum / (d.length / 4);
    }, png);
    console.log(`  luma ${luma.toFixed(1)}`);
  }
  if (process.env.SHOTS) await p.screenshot({ path: `${process.env.SHOTS}/${qs.replace(/[^a-z0-9=,.-]+/gi, "_")}.png` });
  await p.close();
}
await browser.close();
