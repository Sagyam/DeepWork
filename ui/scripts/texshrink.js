// For bench-app.ts EVAL: re-uploads every image texture at 1/2^LEVEL of its size, e.g.
//   EVAL="$(sed s/LEVEL/1/g scripts/texshrink.js)" bun scripts/bench-app.ts "mock=metropolis"
// (dispose() first: three would otherwise write the small image into the old storage).
(() => {
  // Every image texture re-uploaded at 1/2^LEVEL of its size: 4^LEVEL fewer texels (LEVEL 1 ~ 4:1 compression).
  const c = window.city, seen = new Set();
  let n = 0, before = 0, after = 0;
  c.scene.traverse((o) => {
    const m = o.material; if (!m) return;
    for (const mm of Array.isArray(m) ? m : [m]) for (const v of [...Object.values(mm), ...Object.values(mm.uniforms ?? {}).map((u) => u && u.value)]) {
      if (!v || !v.isTexture || v.isRenderTargetTexture || v.isDataTexture || v.isCubeTexture || seen.has(v)) continue;
      const img = v.image; if (!img || !img.width || img.width < 64) continue;
      seen.add(v);
      const k = 2 ** LEVEL, cv = document.createElement("canvas");
      cv.width = Math.max(1, img.width / k); cv.height = Math.max(1, img.height / k);
      cv.getContext("2d").drawImage(img, 0, 0, cv.width, cv.height);
      before += img.width * img.height; after += cv.width * cv.height;
      v.dispose(); v.image = cv; v.needsUpdate = true; n++;
    }
  });
  return `${n} textures, ${(before / 1e6).toFixed(0)}M -> ${(after / 1e6).toFixed(1)}M texels`;
})()
