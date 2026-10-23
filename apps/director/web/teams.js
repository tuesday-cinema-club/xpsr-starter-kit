// Teams: make a shared project and hand its link to the crew. Each team's
// link opens the Director on that project for everyone at once.

import { api } from "./api.js";
import { $, h, toast, loginForm, ago } from "./page-common.js";

const link = (slug) => `${location.origin}/t/${slug}`;

function render(teams) {
  $("#page").innerHTML = `<div class="res-grid">
    <section class="slate"><div class="slate-stripes" aria-hidden="true"></div><div class="slate-body">
      <span class="tag slate-kicker">One link per crew</span><h2>Teams</h2>
      <div class="slate-grid"><div><span class="k">Teams</span><span class="v">${teams.length}</span></div>
        <div><span class="k">People here</span><span class="v">${teams.reduce((n, t) => n + t.members.length, 0)}</span></div>
        <div><span class="k">Signed gates</span><span class="v">${teams.reduce((n, t) => n + t.gates, 0)}</span></div></div></div></section>
    <form class="card" id="new-team">
      <div class="card-head"><span class="card-title"><b>New team</b></span></div>
      <p class="lede">Each team gets its own link. Everyone who opens it, with the access code, works on the same brief, shots, frames and audit, live. Their roles and names stay on their own phones. A private team's link has a random tail and is listed only on phones that have opened it.</p>
      <input type="text" name="name" placeholder="e.g. Ember crew" aria-label="Team name" required minlength="2" maxlength="60">
      <div class="choice" role="radiogroup" aria-label="Who can find it" style="grid-template-columns:1fr 1fr">
        <label class="vis"><input type="radio" name="visibility" value="private" checked> <span><small>Only people with the link</small>Private</span></label>
        <label class="vis"><input type="radio" name="visibility" value="community"> <span><small>Listed here for everyone</small>Community</span></label></div>
      <button class="btn primary" type="submit">Make team</button>
    </form>
    ${teams.map((t) => `<section class="card" aria-label="Team ${h(t.name)}">
      <div class="card-head"><span class="card-title"><b>${h(t.name)}</b>${t.project ? ` · ${h(t.project)}` : ""}</span>
        <span class="badges"><span class="badge">${t.visibility === "community" ? "Community" : "Private"}</span><span class="badge ${t.members.length ? "free" : ""}">${t.members.length} here</span></span></div>
      <div class="row"><input type="text" readonly value="${h(link(t.slug))}" class="grow mono-input" aria-label="Link for ${h(t.name)}">
        <button class="btn small" data-copy="${h(t.slug)}">Copy</button><a class="btn small primary" href="/t/${h(t.slug)}">Open</a></div>
      <p class="item-meta">${h(t.client || "No client yet")} · ${t.shots} shots · ${t.gates} of 3 gates signed · updated ${ago(t.updated)} ago</p>
      ${t.members.length ? `<div class="chips">${t.members.map((m) => `<span class="badge">${h(m.name)}${m.role ? ` · ${h(m.role)}` : ""}</span>`).join("")}</div>` : ""}
    </section>`).join("")}
    <section class="card"><div class="card-head"><span class="card-title"><b>Personal</b></span></div>
      <p class="lede">The plain address keeps a project on one phone only, with no team.</p><a class="btn ghost" href="/">Open my personal project</a></section>
  </div>`;
}

let timer;
async function tick() {
  clearTimeout(timer);
  let mine = [];
  try { mine = JSON.parse(localStorage.getItem("xpsr-my-teams") || "[]"); } catch { /* storage blocked */ }
  try { render((await api.get(`/api/teams?mine=${encodeURIComponent(mine.join(","))}`)).teams); } catch (e) {
    if (e.status === 401) return loginForm($("#page"), tick);
    $("#page").innerHTML = `<p class="notice bad">${h(e.message)}</p>`;
  }
  if (!document.hidden && !document.activeElement?.closest?.("form")) timer = setTimeout(tick, 5000);
}

document.addEventListener("submit", async (e) => {
  if (e.target.id !== "new-team") return;
  e.preventDefault();
  try {
    const f = new FormData(e.target);
    const { team } = await api.post("/api/teams", { name: f.get("name"), visibility: f.get("visibility") });
    location.href = `/t/${team.slug}`;
  } catch (err) { toast(err.message, "bad"); }
});
document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-copy]");
  if (!b) return;
  try { await navigator.clipboard.writeText(link(b.dataset.copy)); toast("Link copied.", "good"); }
  catch { toast("Long-press the link to copy it.", "bad"); }
});
document.addEventListener("focusout", () => setTimeout(tick, 200));
tick();
