// Shared bits for the queue and teams pages: escaping, toasts, and the
// access-code form when the session has not been unlocked yet.

import { api } from "./api.js";

export const $ = (s) => document.querySelector(s);
export const h = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

export function toast(msg, kind = "") {
  const el = $("#toast");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 4000);
}

export function loginForm(target, onDone, msg = "") {
  target.innerHTML = `<form class="card" id="login" style="max-width:420px;margin:40px auto">
    <div class="card-head"><span class="card-title"><b>Access code</b></span></div>
    <label class="field"><span class="field-label">Code from the director's machine</span>
      <input type="password" name="code" autocomplete="current-password" autocapitalize="none" class="mono-input" required></label>
    ${msg ? `<p class="notice bad">${h(msg)}</p>` : ""}
    <button class="btn primary" type="submit">Unlock</button></form>`;
  $("#login").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api.post("/api/login", { code: new FormData(e.target).get("code") });
      onDone();
    } catch (err) { loginForm(target, onDone, err.message); }
  });
}

export function ago(iso) {
  if (!iso) return "";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso)) / 1000));
  return s < 90 ? `${s}s` : s < 5400 ? `${Math.round(s / 60)} min` : `${(s / 3600).toFixed(1)} h`;
}

// ComfyUI's own page, on the same machine name. Over Tailscale this is the
// tailnet-only ComfyUI on port 8188 (plain http, devices on the tailnet only).
export const comfyUrl = () => `http://${location.hostname}:8188`;
