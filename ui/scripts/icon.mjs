// Writes the app icons (a small night skyline) as PNGs: node scripts/icon.mjs
import { writeFileSync } from "node:fs";
import { deflateSync } from "node:zlib";

const CRC = new Int32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c;
});
const crc32 = (buf) => {
  let c = -1;
  for (const b of buf) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
};
const chunk = (type, data) => {
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0);
  out.write(type, 4, "ascii");
  data.copy(out, 8);
  out.writeUInt32BE(crc32(out.subarray(4, 8 + data.length)), 8 + data.length);
  return out;
};

function png(size) {
  const px = (x, y) => {
    // Unit coordinates, y up from the bottom.
    const u = (x + 0.5) / size, v = 1 - (y + 0.5) / size;
    const r = 0.18, dx = Math.max(r - u, u - (1 - r), 0), dy = Math.max(r - v, v - (1 - r), 0);
    if (dx * dx + dy * dy > r * r) return [0, 0, 0, 0];
    const buildings = [[0.14, 0.34, 0.42], [0.36, 0.6, 0.72], [0.62, 0.86, 0.54]];
    for (const [x0, x1, h] of buildings) {
      if (u >= x0 && u < x1 && v >= 0.14 && v < 0.14 + h) {
        const wx = ((u - x0) / 0.06) % 1, wy = ((v - 0.14) / 0.07) % 1;
        const lit = wx > 0.35 && wx < 0.8 && wy > 0.3 && wy < 0.75 && v < 0.14 + h - 0.05;
        return lit ? [255, 205, 110, 255] : [38, 44, 74, 255];
      }
    }
    if (v < 0.14) return [24, 26, 44, 255];
    const t = v;
    return [Math.round(20 + 40 * t), Math.round(24 + 30 * t), Math.round(60 + 70 * t), 255];
  };
  const raw = Buffer.alloc(size * (size * 4 + 1));
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0;
    for (let x = 0; x < size; x++) raw.set(px(x, y), y * (size * 4 + 1) + 1 + x * 4);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr.set([8, 6, 0, 0, 0], 8);
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const dir = new URL("../src-tauri/icons/", import.meta.url);
for (const [name, size] of [["32x32.png", 32], ["128x128.png", 128], ["icon.png", 512]]) {
  writeFileSync(new URL(name, dir), png(size));
}
