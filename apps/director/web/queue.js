// The queue: what is running and waiting on the workshop machine, in order.
// Frames and local motion share the GPU lane one at a time; camera moves and
// cuts run in the render lane; Flow jobs run on Google's side in parallel.

import { api, mediaUrl } from "./api.js";
import { $, h, toast, loginForm, ago, comfyUrl } from "./page-common.js";

const KIND = { keyframe: "Frame", motion: "Motion", camera: "Camera move", render: "Cut", chat: "Writing",
  flow_image: "Flow frame", flow_video: "Flow motion" };
const LANES = [
  ["gpu", "Local GPU", "One job at a time: frames, LTX and Wan motion, and the writing model. Frames and motion run as ComfyUI jobs: open ComfyUI's queue panel to watch the steps, and load a job's workflow to see its graph."],
  ["render", "Render", "Camera moves and cuts, on the CPU with ffmpeg."],
  ["flow", "Google Flow", "Runs on Google's side, several at once."],
];

function eta(j) {
  if (!j.avg) return "";
  if (j.status === "running") return ` · usually ${Math.round(j.avg)}s`;
  return ` · about ${Math.max(1, Math.round((j.avg * j.position) / 60))} min to start`;
}

function row(j) {
  return `<div class="svc-row">
    <span><b>${j.position ? `#${j.position} ` : ""}${h(KIND[j.kind] || j.kind)}</b>${j.team ? ` · team <a href="/t/${h(j.team)}">${h(j.team)}</a>` : ""}<br>
      <span class="small">${h(j.label || "")}</span></span>
    <span><span class="job-status ${h(j.status)}">${h(j.status)}</span> ${j.status === "running" ? `${ago(j.started)}${j.note ? ` · ${h(j.note)}` : ""}` : `waiting ${ago(j.created)}`}${eta(j)}
      ${j.status === "queued" && j.kind !== "chat" ? ` <button class="btn small danger" data-cancel="${h(j.id)}">Cancel</button>` : ""}</span></div>`;
}

function render(d) {
  const running = d.live.filter((j) => j.status === "running").length;
  const waiting = d.live.filter((j) => j.status === "queued").length;
  $("#page").innerHTML = `<div class="res-grid">
    <section class="slate"><div class="slate-stripes" aria-hidden="true"></div><div class="slate-body">
      <span class="tag slate-kicker">Everyone's jobs, every team</span><h2>Queue</h2>
      <div class="slate-grid"><div><span class="k">Running</span><span class="v">${running}</span></div>
        <div><span class="k">Waiting</span><span class="v">${waiting}</span></div>
        <div><span class="k">Done today</span><span class="v">${d.recent.filter((j) => j.status === "done" && (j.finished || "").slice(0, 10) === new Date().toISOString().slice(0, 10)).length}</span></div></div></div></section>
    ${LANES.map(([id, name, what]) => {
      const jobs = d.live.filter((j) => j.lane === id);
      return `<section class="card" aria-labelledby="lane-${id}"><div class="card-head"><h3 class="card-title" id="lane-${id}"><b>${name}</b> · ${jobs.length || "idle"}</h3>${id === "gpu" ? `<a class="btn small ghost" href="${comfyUrl()}" target="_blank" rel="noopener">Watch in ComfyUI ↗</a>` : ""}</div>
        <p class="field-hint">${what}</p><div class="svc">${jobs.map(row).join("") || '<p class="muted small">Nothing here.</p>'}</div></section>`;
    }).join("")}
    <section class="card" aria-labelledby="recent-h"><div class="card-head"><h3 class="card-title" id="recent-h"><b>Finished</b></h3></div>
      <div class="svc">${d.recent.map((j) => {
        const secs = j.started && j.finished ? Math.round((new Date(j.finished) - new Date(j.started)) / 1000) : null;
        return `<div class="svc-row"><span><b>${h(KIND[j.kind] || j.kind)}</b>${j.team ? ` · ${h(j.team)}` : ""}<br><span class="small">${h(j.label || j.error || "")}</span></span>
          <span><span class="job-status ${h(j.status)}">${h(j.status)}</span>${secs != null ? ` ${secs}s` : ""} ${(j.media || [])[0] ? `<a href="${mediaUrl(j.media[0])}" target="_blank" rel="noopener">open</a>` : ""}</span></div>`;
      }).join("") || '<p class="muted small">Nothing yet.</p>'}</div></section>
  </div>`;
}

let timer;
async function tick() {
  clearTimeout(timer);
  try { render(await api.get("/api/queue")); } catch (e) {
    if (e.status === 401) return loginForm($("#page"), tick);
    $("#page").innerHTML = `<p class="notice bad">${h(e.message)}</p>`;
  }
  if (!document.hidden) timer = setTimeout(tick, 2000);
}

document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-cancel]");
  if (!b) return;
  try { await api.post(`/api/jobs/${b.dataset.cancel}/cancel`); toast("Cancelled.", "good"); tick(); } catch (err) { toast(err.message, "bad"); }
});
document.addEventListener("visibilitychange", () => { if (!document.hidden) tick(); });
tick();
