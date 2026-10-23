// Reads a ZIP in the browser: stored entries as they are, deflated ones
// through DecompressionStream. Enough for the packs this app writes and for
// a pack someone re-zipped on a laptop.

export async function readZip(file) {
  const buf = new Uint8Array(await file.arrayBuffer());
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  let eocd = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
    if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error("That file is not a ZIP.");
  const count = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const dec = new TextDecoder();
  const entries = new Map();
  for (let n = 0; n < count; n++) {
    if (dv.getUint32(p, true) !== 0x02014b50) throw new Error("The ZIP's directory is damaged.");
    const method = dv.getUint16(p + 10, true);
    const size = dv.getUint32(p + 20, true);
    const nameLen = dv.getUint16(p + 28, true);
    const extraLen = dv.getUint16(p + 30, true);
    const commentLen = dv.getUint16(p + 32, true);
    const local = dv.getUint32(p + 42, true);
    const name = dec.decode(buf.subarray(p + 46, p + 46 + nameLen));
    p += 46 + nameLen + extraLen + commentLen;
    if (name.endsWith("/")) continue;
    const start = local + 30 + dv.getUint16(local + 26, true) + dv.getUint16(local + 28, true);
    const raw = buf.subarray(start, start + size);
    // Strip a leading folder ("my-pack/brief.json" -> "brief.json") later, by suffix.
    entries.set(name, { method, raw });
  }
  return {
    names: [...entries.keys()],
    async bytes(name) {
      const e = entries.get(name);
      if (!e) return null;
      if (e.method === 0) return e.raw;
      if (e.method !== 8) throw new Error(`${name} uses a compression this browser cannot read.`);
      const stream = new Blob([e.raw]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
      return new Uint8Array(await new Response(stream).arrayBuffer());
    },
    async text(name) {
      const b = await this.bytes(name);
      return b ? new TextDecoder().decode(b) : null;
    },
  };
}
