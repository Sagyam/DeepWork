// Packs the realistic models (public/models, from `bun run models`) for
// download on first run (docs/APP.md, "Model packs"). Releases
// do not carry them in the binary: the app fetches them from a GitHub release
// of their own, checks every file against the manifest compiled into it, and
// keeps them in ~/.local/share/deepwork/assets/<id>/.
//
//   bun run pack            # write src-tauri/models.json, stage the files
//   bun run pack --upload   # and publish them as the release models-<id>
//
// The pack is what the app needs on a GPU with BC7 (every GPU Mesa drives
// with OpenGL 4.2 or later): the glb files, the BC7 textures and bc7.json.
// No PNGs; a GPU without BC7 keeps the low-poly kit.
//
// <id> is a hash of the file list with each file's sum, so an unchanged pack
// keeps its id and its release, and an app update downloads nothing. Commit
// src-tauri/models.json after publishing: it is what the app trusts.
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";

const UI = join(import.meta.dir, "..");
const DIR = join(UI, "public/models");
const MANIFEST = join(UI, "src-tauri/models.json");
const REPO = "Sagyam/DeepWork";
const upload = process.argv.includes("--upload");

if (!existsSync(join(DIR, "bc7.json"))) {
  console.error(`no ${DIR}/bc7.json: build the models first (bun run models)`);
  process.exit(1);
}

const bc7 = JSON.parse(readFileSync(join(DIR, "bc7.json"), "utf8")) as string[];
const glbs = readdirSync(DIR).filter((f) => f.endsWith(".glb")).sort();
for (const g of glbs) {
  if (!bc7.includes(g.replace(/\.glb$/, "_ao"))) {
    console.error(`${g} has no BC7 AO bake: run bun run textures`);
    process.exit(1);
  }
}
const paths = [...glbs, "bc7.json", ...bc7.map((n) => `${n}.bc7`).sort()];

const sha = (b: Buffer | string) => createHash("sha256").update(b).digest("hex");
const files = paths.map((path) => {
  const bytes = readFileSync(join(DIR, path));
  return { path, size: bytes.length, sha256: sha(bytes) };
});
const id = sha(files.map((f) => `${f.path} ${f.size} ${f.sha256}\n`).join("")).slice(0, 16);
const tag = `models-${id}`;
const total = files.reduce((n, f) => n + f.size, 0);

/** Release assets are flat: tex/brick_col.bc7 is published as tex.brick_col.bc7. */
const asset = (path: string) => path.replaceAll("/", ".");

const manifest = {
  id,
  url: `https://github.com/${REPO}/releases/download/${tag}/`,
  files: files.map((f) => ({ ...f, asset: asset(f.path) })),
};
writeFileSync(MANIFEST, `${JSON.stringify(manifest, null, 1)}\n`);
console.log(`${files.length} files, ${(total / 1e6).toFixed(1)} MB, pack ${id}; wrote ${MANIFEST}`);

const stage = join(UI, "../target/models-pack", id);
rmSync(stage, { recursive: true, force: true });
mkdirSync(stage, { recursive: true });
for (const f of files) copyFileSync(join(DIR, f.path), join(stage, asset(f.path)));
console.log(`staged in ${stage}`);

if (upload) {
  const gh = (args: string[]) => Bun.spawnSync(["gh", ...args], { stdout: "inherit", stderr: "inherit" });
  if (Bun.spawnSync(["gh", "release", "view", tag, "-R", REPO], { stdout: "ignore", stderr: "ignore" }).success) {
    console.log(`${tag} is already published`);
  } else {
    const notes =
      "The realistic city's models and textures, downloaded by the DeepWork app on first run " +
      `(${files.length} files, ${(total / 1e6).toFixed(0)} MB). Not an app release: see the latest v* release to install DeepWork.`;
    // A prerelease, never "latest": get.sh installs the latest release.
    const ok = gh(["release", "create", tag, "-R", REPO, "--prerelease", "--latest=false", "--title", `Models ${id}`, "--notes", notes,
      ...readdirSync(stage).map((f) => join(stage, f))]).success;
    if (!ok) process.exit(1);
  }
  // Check what was published against the manifest.
  const r = Bun.spawnSync(["gh", "release", "view", tag, "-R", REPO, "--json", "assets"]);
  const live = new Map((JSON.parse(r.stdout.toString()).assets as { name: string; size: number }[]).map((a) => [a.name, a.size]));
  const bad = manifest.files.filter((f) => live.get(f.asset) !== f.size);
  if (bad.length) {
    console.error(`${bad.length} assets missing or the wrong size on ${tag}: ${bad.map((f) => f.asset).join(", ")}`);
    process.exit(1);
  }
  console.log(`${tag}: all ${files.length} assets published; commit src-tauri/models.json`);
}
