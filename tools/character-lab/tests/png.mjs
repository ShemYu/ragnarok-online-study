// Minimal PNG reader for tests: 8-bit RGB/RGBA, non-interlaced (what Godot's save_png writes).
import {readFileSync} from 'node:fs';
import {inflateSync} from 'node:zlib';

export function readPng(url) {
  const bytes = readFileSync(url);
  if (bytes.readUInt32BE(0) !== 0x89504e47) throw new Error(`Not a PNG: ${url}`);
  let offset = 8, width = 0, height = 0, channels = 0;
  const chunks = [];
  while (offset < bytes.length) {
    const length = bytes.readUInt32BE(offset), type = bytes.toString('ascii', offset + 4, offset + 8);
    const body = bytes.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') {
      width = body.readUInt32BE(0); height = body.readUInt32BE(4);
      const depth = body[8], color = body[9], interlace = body[12];
      if (depth !== 8 || interlace !== 0 || ![2, 6].includes(color)) throw new Error(`Unsupported PNG format in ${url}`);
      channels = color === 6 ? 4 : 3;
    } else if (type === 'IDAT') chunks.push(body);
    else if (type === 'IEND') break;
    offset += 12 + length;
  }
  const raw = inflateSync(Buffer.concat(chunks)), stride = width * channels;
  const data = new Uint8ClampedArray(width * height * 4);
  let previous = new Uint8Array(stride);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)], row = Uint8Array.from(raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1)));
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? row[x - channels] : 0, b = previous[x], c = x >= channels ? previous[x - channels] : 0;
      if (filter === 1) row[x] += a;
      else if (filter === 2) row[x] += b;
      else if (filter === 3) row[x] += (a + b) >> 1;
      else if (filter === 4) {
        const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        row[x] += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      }
    }
    for (let x = 0; x < width; x++) {
      data.set(row.subarray(x * channels, x * channels + channels), (y * width + x) * 4);
      if (channels === 3) data[(y * width + x) * 4 + 3] = 255;
    }
    previous = row;
  }
  return {width, height, data};
}
