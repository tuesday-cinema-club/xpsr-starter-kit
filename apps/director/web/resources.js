// Live machine readings from /api/resources, redrawn every 1.5 seconds while
// the page is visible.

import { api } from "./api.js";

const $ = (s) => document.querySelector(s);
const h = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const gb = (b) => (b / 1e9).toFixed(1);
const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

function dur(sec) {
  const d = Math.floor(sec / 86400), hr = Math.floor(sec / 3600) % 24, m = Math.floor(sec / 60) % 60;
  return d ? `${d}d ${hr}h` : `${hr}h ${m}m`;
}

function heat(v) {
  // Faint slate at idle, amber when busy, red near the top.
  if (v == null) return css("--line");
  if (v < 5) return "#2a2f3d";
  if (v < 35) return "#5b6478";
  if (v < 70) return "#f59e0b";
  return "#ef4444";
}

function spark(id, series, max, colors) {
  const c = document.getElementById(id);
  if (!c) return;
  const dpr = window.devicePixelRatio || 1;
  const w = c.clientWidth, hgt = c.clientHeight;
  c.width = w * dpr;
  c.height = hgt * dpr;
  const g = c.getContext("2d");
  g.scale(dpr, dpr);
  g.strokeStyle = "#2a2f3d";
  g.lineWidth = 1;
  for (const y of [0.25, 0.5, 0.75]) { g.beginPath(); g.moveTo(0, hgt * y); g.lineTo(w, hgt * y); g.stroke(); }
  series.forEach((pts, k) => {
    if (pts.length < 2) return;
    const n = 180;
    const x = (i) => w - ((pts.length - 1 - i) / (n - 1)) * w;
    const y = (v) => hgt - 3 - (Math.max(0, Math.min(max, v ?? 0)) / max) * (hgt - 6);
    g.beginPath();
    pts.forEach((v, i) => (i ? g.lineTo(x(i), y(v)) : g.moveTo(x(i), y(v))));
    g.strokeStyle = colors[k];
    g.lineWidth = 2;
    g.stroke();
    if (k === 0) {
      g.lineTo(x(pts.length - 1), hgt);
      g.lineTo(x(0), hgt);
      g.closePath();
      g.fillStyle = colors[k] + "22";
      g.fill();
    }
  });
}

function stat(k, v) {
  return `<div><span class="k">${h(k)}</span><span class="v">${v}</span></div>`;
}

function render(d) {
  const gpu = d.gpu || {};
  const cpu = d.cpu || {};
  const mem = d.memory || {};
  const hist = d.history || [];
  const vramTotal = gpu.mem_total || 1;
  const procs = gpu.processes || [];
  const ollamaMem = procs.filter((p) => p.name === "Ollama").reduce((n, p) => n + (p.mem || 0), 0);
  const comfyMem = procs.filter((p) => p.name === "ComfyUI").reduce((n, p) => n + (p.mem || 0), 0);
  const otherMem = Math.max(0, (gpu.mem_used || 0) - ollamaMem - comfyMem);
  const f = d.flow;
  const ol = d.services.ollama;
  const cu = d.services.comfyui;

  $("#res").innerHTML = `<div class="res-grid">
    <section class="slate"><div class="slate-stripes" aria-hidden="true"></div><div class="slate-body">
      <span class="tag slate-kicker">The workshop machine</span><h2>Resources</h2>
      <div class="slate-grid">
        <div><span class="k">GPU</span><span class="v">${h(gpu.name || "none")}</span></div>
        <div><span class="k">CPU threads</span><span class="v">${d.threads}</span></div>
        <div><span class="k">Up</span><span class="v">${dur(d.uptime)}</span></div></div></div></section>

    <section class="card" aria-labelledby="gpu-h">
      <div class="card-head"><h3 class="card-title" id="gpu-h"><b>GPU</b> · ${h(gpu.name || "")}</h3><span class="badge">${h(gpu.pcie || "")}</span></div>
      <div class="big-row"><span class="big-num">${gpu.util ?? "–"}<small>%</small></span><span class="muted">busy · ${gpu.temp ?? "–"} °C · ${gpu.power != null ? Math.round(gpu.power) : "–"} of ${gpu.power_limit != null ? Math.round(gpu.power_limit) : "–"} W</span></div>
      <canvas class="spark" id="sp-gpu" role="img" aria-label="GPU busy over the last three minutes, now ${gpu.util ?? 0} percent; graphics memory now ${pct(gpu.mem_used, vramTotal)} percent full"></canvas>
      <div class="legend"><span><i style="background:var(--amber)"></i>GPU busy %</span><span><i style="background:var(--green)"></i>Graphics memory %</span></div>
      <div><span class="field-label">Graphics memory · ${((gpu.mem_used || 0) / 1024).toFixed(1)} of ${(vramTotal / 1024).toFixed(1)} GB</span>
        <div class="bar" role="img" aria-label="Graphics memory: Ollama ${(ollamaMem / 1024).toFixed(1)} GB, ComfyUI ${(comfyMem / 1024).toFixed(1)} GB, other ${(otherMem / 1024).toFixed(1)} GB">
          <span class="a" style="width:${pct(ollamaMem, vramTotal)}%"></span><span class="g" style="width:${pct(comfyMem, vramTotal)}%"></span><span class="x" style="width:${pct(otherMem, vramTotal)}%"></span></div>
        <div class="legend"><span><i style="background:var(--amber)"></i>Ollama ${(ollamaMem / 1024).toFixed(1)} GB</span><span><i style="background:var(--green)"></i>ComfyUI ${(comfyMem / 1024).toFixed(1)} GB</span><span><i style="background:var(--line-strong)"></i>Other ${(otherMem / 1024).toFixed(1)} GB</span></div></div>
      <div class="stat-row">${stat("Clock", `${gpu.clock ?? "–"} / ${gpu.clock_max ?? "–"} MHz`)}${stat("Fan", `${gpu.fan ?? "–"}%`)}${stat("Temp", `${gpu.temp ?? "–"} °C`)}${stat("Power", `${gpu.power != null ? gpu.power.toFixed(0) : "–"} W`)}</div>
    </section>

    <div class="res-grid two">
      <section class="card" aria-labelledby="cpu-h">
        <div class="card-head"><h3 class="card-title" id="cpu-h"><b>CPU</b></h3><span class="badge">${h((cpu.model || "").replace(/\s+\d+-Core Processor/, ""))}</span></div>
        <div class="big-row"><span class="big-num">${cpu.total ?? "–"}<small>%</small></span><span class="muted">${cpu.temp != null ? `${cpu.temp} °C · ` : ""}load ${h((cpu.load || []).join(" "))}</span></div>
        <canvas class="spark" id="sp-cpu" role="img" aria-label="CPU busy over the last three minutes, now ${cpu.total ?? 0} percent"></canvas>
        <div class="cores" role="img" aria-label="${(cpu.cores || []).length} threads; ${(cpu.cores || []).filter((v) => v > 50).length} over half busy">${(cpu.cores || []).map((v, i) => `<span class="core" style="background:${heat(v)}" title="Thread ${i}: ${v}%"></span>`).join("")}</div>
        <div class="legend"><span><i style="background:#2a2f3d"></i>idle</span><span><i style="background:#5b6478"></i>light</span><span><i style="background:#f59e0b"></i>busy</span><span><i style="background:#ef4444"></i>flat out</span></div>
      </section>
      <section class="card" aria-labelledby="mem-h">
        <div class="card-head"><h3 class="card-title" id="mem-h"><b>System memory</b></h3><span class="badge">${gb(mem.total || 0)} GB</span></div>
        <div class="big-row"><span class="big-num">${gb(mem.used || 0)}<small> GB</small></span><span class="muted">in use · ${pct(mem.used, mem.total)}%</span></div>
        <canvas class="spark" id="sp-ram" role="img" aria-label="Memory in use over the last three minutes, now ${pct(mem.used, mem.total)} percent"></canvas>
        <div class="bar" role="img" aria-label="Memory: ${gb(mem.used || 0)} GB used, ${gb(mem.cached || 0)} GB file cache"><span class="a" style="width:${pct(mem.used, mem.total)}%"></span><span class="s" style="width:${pct(mem.cached, mem.total)}%"></span></div>
        <div class="legend"><span><i style="background:var(--amber)"></i>Used ${gb(mem.used || 0)} GB</span><span><i style="background:#6b8cff"></i>File cache ${gb(mem.cached || 0)} GB</span><span>Swap ${gb(mem.swap_used || 0)} of ${gb(mem.swap_total || 0)} GB</span></div>
        <p class="field-hint">Models too big for the 8 GB card run partly from this memory, which is why the big runs are slow here.</p>
      </section>
    </div>

    <div class="res-grid two">
      <section class="card" aria-labelledby="svc-h">
        <div class="card-head"><h3 class="card-title" id="svc-h"><b>Engines</b></h3></div>
        <div class="svc">
          <div class="svc-row"><span><b>Ollama</b> · writing</span><span class="${ol.up ? "" : "muted"}">${ol.up ? `${ol.loaded.length} model${ol.loaded.length === 1 ? "" : "s"} loaded` : "not running"}</span></div>
          ${ol.loaded.map((m) => `<div class="svc-row"><span>${h(m.name)}</span><span>${gb(m.vram || 0)} GB on GPU · ${gb(Math.max(0, (m.size || 0) - (m.vram || 0)))} GB in RAM</span></div>`).join("")}
          <div class="svc-row"><span><b>ComfyUI</b> · frames</span><span class="${cu.up ? "" : "muted"}">${cu.up ? `${cu.running} running · ${cu.pending} waiting` : "not running"}</span></div>
          <div class="svc-row"><span><b>Google Flow</b> · motion</span><span>${f.configured ? `${f.spent_today} of ${f.daily_budget} credits today${f.balance ? ` · balance ${f.balance.credits}` : ""}` : "not connected"}</span></div>
        </div>
        ${d.disks.map((k) => `<div><span class="field-label">${h(k.label)} disk · ${gb(k.used)} of ${gb(k.total)} GB</span><div class="bar"><span class="a" style="width:${pct(k.used, k.total)}%"></span></div></div>`).join("")}
      </section>
      <section class="card" aria-labelledby="jobs-h">
        <div class="card-head"><h3 class="card-title" id="jobs-h"><b>Recent jobs</b></h3></div>
        <div class="svc">${d.jobs.length ? d.jobs.map((j) => {
          const secs = j.started && j.finished ? Math.round((new Date(j.finished) - new Date(j.started)) / 1000) : null;
          return `<div class="svc-row"><span><b>${h({ keyframe: "Frame · local GPU", flow_image: "Frame · Flow", flow_video: "Motion · Flow" }[j.kind] || j.kind)}</b> · ${new Date(j.created).toLocaleTimeString()}</span>
            <span><span class="job-status ${h(j.status)}">${h(j.status)}</span>${secs != null ? ` ${secs}s` : j.note ? ` ${h(j.note)}` : ""}</span></div>`;
        }).join("") : '<p class="muted small">No jobs yet.</p>'}</div>
      </section>
    </div>
  </div>`;

  const amber = css("--amber"), green = css("--green");
  spark("sp-gpu", [hist.map((p) => p.gpu), hist.map((p) => pct(p.vram, vramTotal))], 100, [amber, green]);
  spark("sp-cpu", [hist.map((p) => p.cpu)], 100, [amber]);
  spark("sp-ram", [hist.map((p) => pct(p.ram, mem.total))], 100, [amber]);
}

function loginForm(msg) {
  $("#res").innerHTML = `<form class="card" id="login" style="max-width:420px;margin:40px auto">
    <div class="card-head"><span class="card-title"><b>Access code</b></span></div>
    <label class="field"><span class="field-label">Code from the director's machine</span>
      <input type="password" name="code" autocomplete="current-password" autocapitalize="none" class="mono-input" required></label>
    ${msg ? `<p class="notice bad">${h(msg)}</p>` : ""}
    <button class="btn primary" type="submit">Unlock</button></form>`;
  $("#login").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api.post("/api/login", { code: new FormData(e.target).get("code") });
      tick();
    } catch (err) { loginForm(err.message); }
  });
}

let timer;
async function tick() {
  clearTimeout(timer);
  try {
    render(await api.get("/api/resources"));
    $("#live").className = "light on";
  } catch (e) {
    $("#live").className = "light off";
    if (e.status === 401) return loginForm();
  }
  $("#clock").textContent = new Date().toLocaleTimeString([], { hour12: false });
  if (!document.hidden) timer = setTimeout(tick, 1500);
}

document.addEventListener("visibilitychange", () => { if (!document.hidden) tick(); });
tick();
