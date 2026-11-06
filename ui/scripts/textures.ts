// Compresses the realistic models' textures (public/models: the AO bakes and
// the tex/ library) to BC7, which the GPU keeps compressed: a quarter of the
// memory of a PNG decoded to 32-bit RGBA, at near-PNG quality (docs/APP.md,
// "Performance"). Runs after `bun run models` (part of it); alone:
//
//   bun run textures            # only what changed since the last run
//   bun run textures --force    # everything
//
// Each PNG is encoded to UASTC (basisu, the highest-quality Basis mode), then
// transcoded to BC7 here, at build time, and written as a gzipped KTX (v1)
// file, <name>.bc7: the app uploads it as it is, with no transcoder, worker
// or WebAssembly (a runtime transcoder needs 'unsafe-eval' in the CSP).
// bc7.json lists what was written; the app loads PNG for the rest, and for
// everything on a GPU without BC7.
//
// Needs basisu (Arch: `pacman -S basis-universal`; BASISU= another path).
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { cpus, tmpdir } from "node:os";
import { join } from "node:path";

const DIR = join(import.meta.dir, "../public/models");
const BASISU = process.env.BASISU ?? "basisu";
const force = process.argv.includes("--force");

if (!existsSync(DIR)) {
  console.error(`no ${DIR}: build the models first (bun run models)`);
  process.exit(1);
}
if (!Bun.spawnSync([BASISU, "-version"], { stdout: "ignore", stderr: "ignore" }).success) {
  console.error(`${BASISU} not found: install basis-universal (pacman -S basis-universal), or set BASISU=`);
  process.exit(1);
}

/** Names (without .png) relative to DIR: the AO bakes, then the library. */
const names = [
  ...readdirSync(DIR).filter((f) => f.endsWith("_ao.png")),
  ...readdirSync(join(DIR, "tex")).filter((f) => f.endsWith(".png")).map((f) => `tex/${f}`),
].map((f) => f.slice(0, -4));

/**
 * UASTC flags for one texture. Normal, roughness, grime and AO maps hold
 * data, not colour: linear metrics and mip filtering (normals renormalised).
 * AO bakes are atlases, so their mips clamp at the borders; the library
 * tiles, so its mips wrap. Level 2 is basisu's default effort; no RDO, which
 * only shrinks files at some cost in quality.
 */
function flags(name: string): string[] {
  const base = ["-uastc", "-uastc_level", "2", "-ktx2", "-mipmap"];
  if (name.endsWith("_nrm")) return [...base, "-linear", "-normal_map", "-mip_linear", "-mip_renorm"];
  if (name.endsWith("_ao")) return [...base, "-linear", "-mip_linear", "-mip_clamp"];
  if (name.endsWith("_rgh") || name.endsWith("grime")) return [...base, "-linear", "-mip_linear"];
  return [...base, "-srgb", "-mip_srgb"];
}

const out = (n: string) => join(DIR, `${n}.bc7`);
const fresh = (n: string) => existsSync(out(n)) && statSync(out(n)).mtimeMs >= statSync(join(DIR, `${n}.png`)).mtimeMs;
const todo = names.filter((n) => force || !fresh(n));
console.log(`${names.length} textures, ${todo.length} to encode`);

const run = async (args: string[], cwd: string) => {
  const p = Bun.spawn([BASISU, ...args], { cwd, stdout: "ignore", stderr: "pipe" });
  if ((await p.exited) !== 0) throw new Error(await new Response(p.stderr).text());
};

// basisu threads itself; a few at once keeps every core busy through the small ones.
const jobs = Math.max(1, Math.min(4, Math.floor(cpus().length / 4)));
let failed = 0;
let next = 0;
async function worker() {
  while (next < todo.length) {
    const n = todo[next++];
    const tmp = mkdtempSync(join(tmpdir(), "deepwork-tex-"));
    try {
      await run([...flags(n), join(DIR, `${n}.png`), "-output_file", join(tmp, "t.ktx2")], tmp);
      // Format 6 is BC7; -ktx_only writes a KTX (v1) file with every mip level.
      await run(["-unpack", "-format_only", "6", "-ktx_only", "t.ktx2"], tmp);
      const ktx = readdirSync(tmp).find((f) => f.endsWith(".ktx"));
      if (!ktx) throw new Error("basisu wrote no BC7 file");
      writeFileSync(out(n), Bun.gzipSync(readFileSync(join(tmp, ktx)), { level: 9 }));
      console.log(`  ${n}`);
    } catch (e) {
      failed++;
      console.error(`failed: ${n}\n${e}`);
    } finally {
      rmSync(tmp, { recursive: true, force: true });
    }
  }
}
await Promise.all(Array.from({ length: jobs }, worker));

const done = names.filter(fresh);
writeFileSync(join(DIR, "bc7.json"), JSON.stringify(done));
const size = (f: (n: string) => string) => done.reduce((s, n) => s + statSync(f(n)).size, 0) / 2 ** 20;
console.log(`bc7.json: ${done.length} of ${names.length} (download ${size((n) => join(DIR, `${n}.png`)).toFixed(0)} MB as PNG, ${size(out).toFixed(0)} MB as BC7)`);
if (failed) process.exit(1);
