// Records the README and site demo, one directory of PNG frames per shot,
// from the mock UI on the dev server (bun run dev). 1920x1080, 10 fps on a
// fake clock, quality=high, no pedestrians; captions drawn in the page.
//
//   bun scripts/demo.ts out              # every shot (about 6 minutes)
//   bun scripts/demo.ts out 5-dusk       # just one
//
// Joining and encoding: docs/DEVELOPMENT.md, "README media".
import { chromium, type Page } from "playwright-core";
import { mkdirSync } from "node:fs";
const out = process.argv[2];
const only = process.argv.slice(3);
const W = 1920, H = 1080, FPS = 10;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/usr/bin/chromium", args: ["--headless=new", "--ignore-gpu-blocklist", "--enable-gpu", "--use-angle=gl"] });
const ctx = await browser.newContext({ viewport: { width: W, height: H } });
await ctx.addInitScript(() => { try { localStorage.setItem("deepwork.seen", "1e15"); } catch {} });

async function open(qs: string, cam: string) {
  const p = await ctx.newPage();
  p.on("pageerror", (e) => console.error("pageerror", e.message));
  await p.clock.install();
  await p.goto(`http://localhost:5173/?${qs}&hour=16&people=0&quality=high&weather=clear`);
  await p.waitForFunction(() => (window as any).city?.plan, null, { timeout: 300000, polling: 500 });
  await p.addStyleTag({ content: `#story{display:none!important}
    #cap{position:fixed;left:50%;bottom:64px;transform:translateX(-50%);z-index:99;padding:16px 34px;border-radius:16px;
    background:rgba(16,18,24,.82);color:#fff;font:600 40px/1.2 var(--font-display);letter-spacing:-.01em;white-space:nowrap;
    box-shadow:0 8px 30px rgba(0,0,0,.3)}` });
  await p.evaluate((cam) => {
    const c = (window as any).city;
    const [x, y, z, tx, ty, tz] = cam.split(",").map(Number);
    c.camera.position.set(x, y, z);
    c.controls.target.set(tx, ty, tz);
    c.controls.autoRotate = false;
    c.idle = -1e9;
    c.controls.update();
    const d = document.createElement("div");
    d.id = "cap";
    document.body.append(d);
  }, cam);
  await p.waitForTimeout(8000); // textures, shadows, impostors settle in real time
  await p.clock.pauseAt((await p.evaluate(() => Date.now())) + 500);
  await p.clock.runFor(1500);
  return p;
}

type Shot = { name: string; qs: string; cam: string; cap: string; secs: number; orbit?: number; dolly?: number; at?: Record<number, (p: Page) => Promise<unknown>> };

async function record(s: Shot) {
  const dir = `${out}/${s.name}`;
  mkdirSync(dir, { recursive: true });
  const p = await open(s.qs, s.cam);
  await p.evaluate((t) => { document.getElementById("cap")!.textContent = t; }, s.cap);
  const n = Math.round(s.secs * FPS);
  for (let i = 0; i < n; i++) {
    if (s.at?.[i]) await s.at[i](p);
    if (s.orbit || s.dolly)
      await p.evaluate(([a, k]) => {
        const c = (window as any).city;
        const t = c.controls.target;
        const v = c.camera.position.clone().sub(t);
        v.applyAxisAngle(c.camera.up, a).multiplyScalar(1 - k);
        c.camera.position.copy(t).add(v);
        c.camera.lookAt(t);
      }, [(s.orbit ?? 0) / FPS, (s.dolly ?? 0) / FPS]);
    await p.evaluate(() => { const d = document.getElementById("cap"); const dlg = document.querySelector("dialog[open]"); if (d && dlg && d.parentElement !== dlg) dlg.append(d); });
    await p.clock.runFor(1000 / FPS);
    await p.screenshot({ path: `${dir}/${String(i).padStart(4, "0")}.png` });
  }
  await p.close();
  console.log(s.name, n);
}

const shots: Shot[] = [
  { name: "1-hamlet", qs: "mock=hamlet", cam: "62,36,30,-15,3,-30", cap: "Set a timer. Distracting sites slow to a crawl.", secs: 4.5, orbit: 0.025,
    at: { 14: (p) => p.click("[data-action=start-selected]") } },
  { name: "2-build", qs: "mock=hamlet", cam: "40,30,10,-20,6,-34", cap: "Every finished session raises a building.", secs: 4.5, orbit: -0.03,
    at: { 3: (p) => p.evaluate(() => (window as any).city.demo("build")) } },
  { name: "3-city", qs: "mock=city", cam: "200,85,165,40,12,10", cap: "Sessions add up. The hamlet becomes a city.", secs: 5, orbit: 0.04, dolly: 0.02 },
  { name: "4-metropolis", qs: "mock=metropolis", cam: "230,120,250,-5,30,5", cap: "500 hours in, a metropolis.", secs: 5.5, orbit: 0.05, dolly: 0.025 },
  { name: "5-dusk", qs: "mock=metropolis&hour=18.3", cam: "-210,95,240,-30,30,30", cap: "It lights up when the sun goes down.", secs: 5, orbit: -0.04 },
  { name: "6-surrender", qs: "mock=surrender", cam: "-165,80,120,-24,25,40", cap: "Quit early, and it comes down.", secs: 6,
    at: { 10: (p) => p.evaluate(() => (window as any).city.demo("collapse", 26)) } },
  { name: "7-ruins", qs: "mock=ruins", cam: "-120,60,45,-25,3,-15", cap: "The damage stays until focus repairs it.", secs: 5, orbit: 0.035, dolly: 0.015 },
  { name: "8-sheets", qs: "mock=city", cam: "185,70,150,55,15,15", cap: "Stats and site lists, one click away.", secs: 5.5, orbit: 0.02,
    at: {
      2: (p) => p.click("[data-open=progress]"),
      28: async (p) => { await p.keyboard.press("Escape"); await p.click("[data-open=settings]"); await p.clock.runFor(300); await p.click("#settings [data-section=lists]"); },
    } },
];
for (const s of shots) if (!only.length || only.includes(s.name)) await record(s);
await browser.close();
