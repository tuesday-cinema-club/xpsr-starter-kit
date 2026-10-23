// The catalogue: every file the server holds, which Flow credits paid for
// which clip, and a way to put an existing take back into a shot.

import { api, mediaUrl } from "./api.js";

const KEY = "xpsr-director-v1";
const $ = (s) => document.querySelector(s);
const h = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pad = (n) => String(n).padStart(2, "0");

let data = null;
let filter = "all";
let project = "all";

const FILTERS = [
  ["all", "Everything", () => true],
  ["video", "Clips", (m) => m.kind === "video"],
  ["flow", "Flow frames", (m) => m.kind === "image" && m.source === "flow"],
  ["local", "GPU frames", (m) => m.kind === "image" && m.source === "local"],
  ["upload", "Phone photos", (m) => m.source === "upload"],
];

function state() {
  try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; }
}

function toast(msg, kind = "") {
  const el = $("#toast");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 4000);
}

const day = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
const when = (iso) => new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
const sourceLabel = (m) => m.source === "upload" ? "Phone photo" : m.source === "local" ? "Local GPU" : "Google Flow";

function useControls(m) {
  const s = state();
  if (!s?.shots?.length) return "";
  const slots = m.kind === "video" ? [["motion", "motion"]] : [["first", "first frame"], ["last", "last frame"]];
  const options = s.shots.flatMap((sh, i) => slots.map(([slot, label]) =>
    `<option value="${sh.id}|${slot}" ${sh[slot]?.locked ? "disabled" : ""}>Shot ${pad(i + 1)} ${h(sh.label)} · ${label}${sh[slot]?.locked ? " (locked)" : ""}</option>`)).join("");
  return `<form class="row" data-use="${m.name}">
    <select class="grow" aria-label="Shot to use this in" style="min-height:44px">${options}</select>
    <button class="btn small" type="submit">Use in shot</button></form>`;
}

function item(m) {
  const credits = m.credits ? `<b class="num">${m.credits}</b> Flow credits` : m.source === "flow" ? "0 credits" : "free";
  return `<article class="item" id="m-${h(m.name)}">
    ${m.kind === "video" ? `<video src="${mediaUrl(m.name)}" controls playsinline preload="metadata"></video>` : `<img src="${mediaUrl(m.name)}" alt="${h(m.label || "frame")}" loading="lazy">`}
    <div class="item-body">
      <div class="item-title">${h(m.label || m.prompt || m.name)}</div>
      <div class="badges"><span class="badge ${m.credits ? "cost" : "free"}">${m.kind === "video" ? `${m.duration || ""}${m.duration ? "s clip" : "Clip"}` : m.frame === "last" ? "Last frame" : m.frame === "first" ? "First frame" : "Image"}</span><span class="badge">${sourceLabel(m)}</span></div>
      <div class="item-meta">${h(m.tool_or_model)}<br>${credits} · seed <span class="num">${h(m.seed ?? "")}</span><br>${when(m.created)} · ${(m.bytes / 1e6).toFixed(1)} MB</div>
      ${m.prompt ? `<details><summary>Prompt</summary>${h(m.prompt)}${m.reference ? `<br><br>Reference: <a href="#m-${h(m.reference)}">${h(m.reference)}</a>` : ""}${m.start ? `<br><br>From <a href="#m-${h(m.start)}">first frame</a>${m.end ? ` to <a href="#m-${h(m.end)}">last frame</a>` : ""}` : ""}</details>` : ""}
      <div class="row"><a class="btn small ghost" href="${mediaUrl(m.name)}?download=1">Download</a></div>
      ${useControls(m)}
    </div></article>`;
}

function ledger() {
  if (!data.days.length) return '<p class="muted small">No Flow credits spent yet.</p>';
  const byName = Object.fromEntries(data.media.map((m) => [m.name, m]));
  return data.days.map((d) => `<div class="ledger-day">
    <span class="field-label">${day(d.day)} · ${d.spent} of ${data.flow.daily_budget} credits</span>
    ${d.entries.map((e) => {
      const m = e.media?.[0] && byName[e.media[0]];
      const thumb = m ? `<video src="${mediaUrl(m.name)}#t=0.5" muted playsinline preload="metadata"></video>` : `<span class="nofile">${e.status === "failed" ? "failed" : e.status || "?"}</span>`;
      return `<a class="ledger-row" href="${m ? `#m-${h(m.name)}` : "#"}">${thumb}
        <span class="item-meta"><b class="${e.refunded ? "refunded" : ""}">${e.credits} credits</b> · ${h(e.model)} · ${new Date(e.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}<br>
        ${h(e.label || e.prompt || "")}${e.refunded ? "<br>Failed; put back in the budget." : ""}</span></a>`;
    }).join("")}</div>`).join("");
}

function render() {
  const t = data.totals;
  const f = data.flow;
  const projects = [...new Set(data.media.map((m) => m.project).filter(Boolean))];
  const test = FILTERS.find((x) => x[0] === filter)[2];
  const shown = data.media.filter((m) => test(m) && (project === "all" || m.project === project));
  $("#lib").innerHTML = `<div class="res-grid">
    <section class="slate"><div class="slate-stripes" aria-hidden="true"></div><div class="slate-body">
      <span class="tag slate-kicker">Everything made on this machine</span><h2>Library</h2>
      <div class="slate-grid">
        <div><span class="k">Clips</span><span class="v">${t.videos}</span></div>
        <div><span class="k">Frames</span><span class="v">${t.frames_local + t.frames_flow + t.photos}</span></div>
        <div><span class="k">Credits used</span><span class="v">${t.credits}</span></div></div></div></section>

    <section class="card" aria-labelledby="ledger-h">
      <div class="card-head"><h3 class="card-title" id="ledger-h"><b>Where the credits went</b></h3><span class="badge ${f.left_today ? "free" : "cost"}">${f.left_today} left today</span></div>
      <p class="lede">Every Flow charge, the clip it bought and the shot it was for. Out of credits? Every clip below is already paid for: put it back into a shot with Use in shot.</p>
      ${ledger()}
    </section>

    <section class="card" aria-labelledby="files-h">
      <div class="card-head"><h3 class="card-title" id="files-h"><b>Files</b> · ${shown.length} shown</h3></div>
      <div class="filters" role="group" aria-label="Show">${FILTERS.map(([k, label]) => `<button data-filter="${k}" aria-pressed="${filter === k}">${label}</button>`).join("")}</div>
      ${projects.length > 1 ? `<label class="field"><span class="field-label">Project</span><select id="project"><option value="all">All projects</option>${projects.map((p) => `<option ${p === project ? "selected" : ""}>${h(p)}</option>`).join("")}</select></label>` : ""}
      <p class="field-hint">${t.frames_local} on the local GPU, ${t.frames_flow} from Flow, ${t.photos} phone photo${t.photos === 1 ? "" : "s"}. Files live in ~/.local/share/xpsr-director/media on the director's machine.</p>
    </section>
    <div class="lib-grid">${shown.map(item).join("") || '<p class="muted">Nothing here yet.</p>'}</div>
  </div>`;
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-filter]");
  if (b) { filter = b.dataset.filter; render(); }
});
document.addEventListener("change", (e) => {
  if (e.target.id === "project") { project = e.target.value; render(); }
});
document.addEventListener("submit", (e) => {
  const form = e.target.closest("[data-use]");
  if (!form) return;
  e.preventDefault();
  const [shot, slot] = form.querySelector("select").value.split("|");
  const meta = data.media.find((m) => m.name === form.dataset.use);
  const s = state();
  if (!s || !meta) return;
  s.imports = [...(s.imports || []), { shot, slot, meta }];
  try {
    localStorage.setItem(KEY, JSON.stringify(s));
    toast("Queued: it shows up as a take in that shot when the Director page opens.", "good");
  } catch { toast("This browser blocked storage.", "bad"); }
});

async function boot() {
  try {
    data = await api.get("/api/library");
    render();
    if (location.hash) document.querySelector(location.hash)?.scrollIntoView();
  } catch (e) {
    $("#lib").innerHTML = e.status === 401
      ? `<p class="notice warn">Enter the access code on the <a href="/">Director page</a> first.</p>`
      : `<p class="notice bad">${h(e.message)}</p>`;
  }
}

boot();
