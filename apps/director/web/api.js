// Talks to server.py. Every POST carries X-XPSR so the server can refuse
// cross-site requests; the session cookie is set by /api/login.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function call(method, path, body, headers = {}) {
  let res;
  try {
    res = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: method === "GET" ? headers : { "X-XPSR": "1", ...headers },
      body,
    });
  } catch {
    throw new ApiError(0, "The director server is not reachable. Brief, shots and audit still work offline.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, data.error || `Request failed (${res.status})`);
  return data;
}

export const api = {
  get: (path) => call("GET", path),
  post: (path, obj) => call("POST", path, JSON.stringify(obj ?? {}), { "Content-Type": "application/json" }),
  // Headers must be Latin-1, so labels and prompts travel percent-encoded.
  upload: (blob, headers = {}) => call("POST", "/api/upload", blob, {
    "Content-Type": blob.type,
    ...Object.fromEntries(Object.entries(headers).map(([k, v]) => [k, encodeURIComponent(String(v ?? ""))])),
  }),
};

export const mediaUrl = (name) => `/api/media/${name}`;

// Phone photos arrive as HEIC, huge JPEGs or rotated; redraw every image as a
// JPEG no wider than 1600 px before upload.
export async function toJpeg(fileOrBlob, maxSide = 1600) {
  const bitmap = await createImageBitmap(fileOrBlob, { imageOrientation: "from-image" }).catch(() => null);
  if (!bitmap) throw new Error("This browser cannot read that image. Try a JPEG or PNG.");
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return new Promise((ok) => canvas.toBlob(ok, "image/jpeg", 0.88));
}

// Grab one frame from a phone video so it can stand in as the layout reference.
export function videoFrame(file, at = 0.5) {
  return new Promise((ok, fail) => {
    const v = document.createElement("video");
    v.muted = true;
    v.playsInline = true;
    v.preload = "auto";
    v.src = URL.createObjectURL(file);
    v.onloadeddata = () => { v.currentTime = Math.min(at, (v.duration || 1) / 2); };
    v.onseeked = () => {
      const c = document.createElement("canvas");
      const scale = Math.min(1, 1600 / Math.max(v.videoWidth, v.videoHeight));
      c.width = Math.round(v.videoWidth * scale);
      c.height = Math.round(v.videoHeight * scale);
      c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
      c.toBlob((b) => (b ? ok(b) : fail(new Error("Could not read a frame from that video."))), "image/jpeg", 0.88);
    };
    v.onerror = () => fail(new Error("This browser cannot play that video."));
  });
}
