// The workshop admin: every team, private or not, with rename, visibility
// and delete; storage and a clean-up for takes nobody kept; the queue.
// Needs the admin code (XPSR_ADMIN_CODE), separate from the room's code.

import { api } from "./api.js";
import { $, h, toast, ago } from "./page-common.js";

const gb = (b) => (b / 1e9).toFixed(2);

function loginForm(msg = "") {
  $("#page").innerHTML = `<form class="card" id="admin-login" style="max-width:420px;margin:40px auto">
    <div class="card-head"><span class="card-title"><b>Admin code</b></span></div>
    <p class="lede">Not the room's access code: the admin code from the director's machine (XPSR_ADMIN_CODE).</p>
    <label class="field"><span class="field-label">Admin code</span>
      <input type="password" name="code" autocomplete="current-password" autocapitalize="none" class="mono-input" required></label>
    ${msg ? `<p class="notice bad">${h(msg)}</p>` : ""}
    <button class="btn primary" type="submit">Sign in as admin</button></form>`;
}

function render(d) {
  const live = d.queue.live;
  $("#page").innerHTML = `<div class="res-grid">
    <section class="slate"><div class="slate-stripes" aria-hidden="true"></div><div class="slate-body">
      <span class="tag slate-kicker">Signed in as admin</span><h2>Workshop</h2>
      <div class="slate-grid"><div><span class="k">Teams</span><span class="v">${d.teams.length}</span></div>
        <div><span class="k">Files</span><span class="v">${d.media.count} · ${gb(d.media.bytes)} GB</span></div>
        <div><span class="k">Jobs live</span><span class="v">${live.length}</span></div></div></div></section>

    <section class="card" aria-labelledby="teams-h"><div class="card-head"><h3 class="card-title" id="teams-h"><b>Teams</b> · private ones included</h3></div>
      <div class="svc">${d.teams.map((t) => `<div class="machine" data-team="${h(t.slug)}">
        <div class="row"><b class="grow">${h(t.name)}</b><span class="badge">${t.visibility === "community" ? "Community" : "Private"}</span><span class="badge ${t.members.length ? "free" : ""}">${t.members.length} here</span></div>
        <span>${h(t.project || "No project yet")} · ${h(t.client || "")} · ${t.shots} shots · ${t.gates}/3 gates · ${t.files} files · updated ${ago(t.updated)} ago</span><br>
        <span class="mono small">/t/${h(t.slug)}</span>
        <div class="row" style="margin-top:8px">
          <a class="btn small primary" href="/t/${h(t.slug)}">Open</a>
          <a class="btn small ghost" href="/library?team=${h(t.slug)}">Files</a>
          <button class="btn small" data-vis="${t.visibility === "community" ? "private" : "community"}">${t.visibility === "community" ? "Make private" : "Share with community"}</button>
          <button class="btn small" data-rename>Rename</button>
          <button class="btn small danger" data-delete>Delete</button></div></div>`).join("") || '<p class="muted small">No teams yet.</p>'}</div></section>

    <section class="card" aria-labelledby="files-h"><div class="card-head"><h3 class="card-title" id="files-h"><b>Storage</b></h3></div>
      <p class="lede">${d.media.count} files, ${gb(d.media.bytes)} GB: ${d.media.shared} shared with the community, ${d.media.personal} from personal projects. <a href="/library">Open the library</a> and choose Everything to delete single files.</p>
      <form class="row" id="cleanup"><label class="field grow"><span class="field-label">Clean up takes nobody kept, older than (days)</span>
        <input type="number" name="days" value="7" min="0" class="mono-input"></label>
        <button class="btn" type="submit" name="mode" value="dry">Count them</button><button class="btn danger" type="submit" name="mode" value="go">Delete them</button></form>
      <p class="field-hint">Only team files that no team project references and nobody shared. Personal projects live on phones, so their files are never cleaned up here.</p>
      <div id="cleanup-out"></div></section>

    <section class="card"><div class="card-head"><h3 class="card-title"><b>Queue</b> · ${live.length} live</h3><a class="btn small ghost" href="/queue">Full queue</a></div>
      <div class="svc">${live.map((j) => `<div class="svc-row"><span><b>${h(j.kind)}</b> · ${h(j.team || "personal")} · ${h(j.label || "")}</span><span class="job-status ${h(j.status)}">${h(j.status)}</span></div>`).join("") || '<p class="muted small">Idle.</p>'}</div></section>

    <section class="card"><div class="card-head"><h3 class="card-title"><b>Spending today</b></h3></div>
      <p class="item-meta">Flow: ${d.flow.spent_today} of ${d.flow.daily_budget} credits${d.flow.configured ? "" : " (not connected)"}<br>
      Gemini API: $${d.gemini.spent_today.toFixed(3)} of $${d.gemini.daily_usd.toFixed(2)}${d.gemini.configured ? "" : " (no key)"}</p></section>

    <button class="btn ghost" id="logout">Sign out of admin</button>
  </div>`;
}

async function load() {
  try { render(await api.get("/api/admin/overview")); } catch (e) {
    if (e.status === 403 || e.status === 401) return loginForm();
    $("#page").innerHTML = `<p class="notice bad">${h(e.message)}</p>`;
  }
}

document.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (e.target.id === "admin-login") {
    try { await api.post("/api/admin/login", { code: new FormData(e.target).get("code") }); load(); } catch (err) { loginForm(err.message); }
  } else if (e.target.id === "cleanup") {
    const go = e.submitter?.value === "go";
    if (go && !confirm("Delete those files for good?")) return;
    try {
      const r = await api.post("/api/admin/cleanup", { days: new FormData(e.target).get("days"), dry_run: !go });
      $("#cleanup-out").innerHTML = `<p class="notice ${go ? "good" : "warn"}">${go ? `Deleted ${r.removed} files.` : `${r.would_remove} files would go.`}</p>`;
      if (go) load();
    } catch (err) { toast(err.message, "bad"); }
  }
});

document.addEventListener("click", async (e) => {
  if (e.target.id === "logout") { await api.post("/api/admin/logout").catch(() => {}); return loginForm(); }
  const box = e.target.closest("[data-team]");
  if (!box) return;
  const slug = box.dataset.team;
  try {
    if (e.target.dataset.vis) {
      await api.post(`/api/teams/${slug}/settings`, { visibility: e.target.dataset.vis });
      toast("Updated.", "good");
    } else if ("rename" in e.target.dataset) {
      const name = prompt("New team name:");
      if (!name) return;
      await api.post(`/api/teams/${slug}/settings`, { name });
      toast("Renamed. The link stays the same.", "good");
    } else if ("delete" in e.target.dataset) {
      if (!confirm(`Delete team ${slug}? Its shared project is gone for everyone.`)) return;
      const files = confirm("Also delete every frame and clip this team made? (Cancel keeps the files in the library.)");
      const r = await api.post(`/api/admin/teams/${slug}/delete`, { files });
      toast(`Team deleted${files ? `, with ${r.files_removed} files` : ""}.`, "good");
    } else return;
    load();
  } catch (err) { toast(err.message, "bad"); }
});

load();
