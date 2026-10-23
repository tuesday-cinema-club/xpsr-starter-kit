// XPSR Director: four gates on one phone screen. State lives in localStorage
// and is saved on every keystroke; the server is only needed for the GPU,
// Google Flow and media.

import { ROLES, PRESETS, FRAMINGS, MOVES, LENSES, DEFAULT_SHOTS, CHECKS } from "./data.js";
import { api, ApiError, mediaUrl, toJpeg, videoFrame, CLIENT_ID } from "./api.js";
import { textFiles } from "./pack.js";
import { makeZip } from "./zip.js";
import { readZip } from "./unzip.js";

// A team URL (/t/<slug>) shares one project between phones through the
// server; the root URL keeps a personal project on this phone only.
const TEAM = (location.pathname.match(/^\/t\/([a-z0-9-]{1,40})\/?$/) || [])[1] || null;
const KEY = TEAM ? `xpsr-director-team-${TEAM}` : "xpsr-director-v1";
if (TEAM) {  // private teams are unlisted: remember the ones this phone has opened
  try {
    const mine = new Set(JSON.parse(localStorage.getItem("xpsr-my-teams") || "[]"));
    mine.add(TEAM);
    localStorage.setItem("xpsr-my-teams", JSON.stringify([...mine]));
  } catch { /* storage blocked */ }
}
// Kept per person even inside a team: your role, your name, your drafts.
const LOCAL_KEYS = ["role", "director", "suggest", "llm_model"];

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const h = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const buzz = (p = 12) => { try { navigator.vibrate?.(p); } catch { /* not supported */ } };
const pad = (n) => String(n).padStart(2, "0");
const nowIso = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");
const uid = () => Math.random().toString(36).slice(2, 10);

// ------------------------------------------------------------------ state

function newShot(i, tpl = DEFAULT_SHOTS[i] || DEFAULT_SHOTS[1], preset = "ember", source = "local") {
  const p = PRESETS[preset] || PRESETS.custom;
  return {
    id: uid(), label: tpl.label || `Shot ${i + 1}`, framing: tpl.framing || "Medium", lens_mm: tpl.lens_mm || 35,
    duration_sec: tpl.duration_sec || 10, camera_move: tpl.camera_move || "Static",
    location_id: p.locations[0]?.[0] || "location_1", characters: [], action_description: "", visual_prompt: "",
    voiceover_line: "", source_ids: [], locked: false, ref: null,
    first: { prompt: "", useRef: true, source, takes: [], pick: null, locked: false, error: null },
    last: { prompt: "", source, takes: [], pick: null, locked: false, skip: false, error: null },
    motion: { prompt: "", model: "veo-3.1-lite", takes: [], pick: null, locked: false, still: false, error: null },
  };
}

function fresh(preset = "ember") {
  const p = PRESETS[preset];
  return {
    v: 1, role: "director", director: "",
    brief: {
      preset, client: p.client, project_title: p.project_title, target_audience: "", core_feeling: "",
      call_to_action: "", key_message: "", runtime_sec: 30, tone: [...p.tone], exclusions: [], references: "",
      facts: p.facts.map((f) => [...f]), idea: "",
    },
    gates: { g1: null, g2: null, g3: null },
    shots: DEFAULT_SHOTS.map((t, i) => newShot(i, t, preset)),
    jobs: {},
    provenance: [],
    vo_note: "",
    audit: { auditor: "", cut: "cut.mp4", date: "", notes: "", signature: "", signed_at: null, checks: {}, intent_llm: "" },
    llm_model: "",
    flow_frames: "nano-banana-2-lite",
    cuts: [],
    render: { burn: true, vo: true },
    vo_media: null,
    frame_source: "local",
    suggest: null,
  };
}

// Fill in anything a saved, synced or imported project is missing, so an
// older or hand-edited state never breaks the page.
function normalize(s) {
  const base = fresh(s.brief?.preset || "ember");
  const out = { ...base, ...s };
  out.brief = { ...base.brief, ...(s.brief || {}) };
  for (const k of ["client", "project_title", "target_audience", "core_feeling", "call_to_action", "key_message", "references", "idea"]) {
    if (typeof out.brief[k] !== "string") out.brief[k] = out.brief[k] == null ? "" : String(out.brief[k]);
  }
  for (const k of ["tone", "exclusions", "facts"]) if (!Array.isArray(out.brief[k])) out.brief[k] = [];
  out.audit = { ...base.audit, ...(s.audit || {}), checks: { ...(s.audit?.checks || {}) } };
  for (const k of ["auditor", "cut", "notes", "signature", "intent_llm"]) if (typeof out.audit[k] !== "string") out.audit[k] = "";
  out.gates = { g1: null, g2: null, g3: null, ...(s.gates || {}) };
  out.shots = (Array.isArray(s.shots) ? s.shots : base.shots).map((sh, i) => {
    const d = newShot(i, { label: sh?.label || `Shot ${i + 1}` }, out.brief.preset);
    const m = { ...d, ...sh };
    for (const slot of ["first", "last", "motion"]) m[slot] = { ...d[slot], ...(sh?.[slot] || {}), takes: [...(sh?.[slot]?.takes || [])] };
    for (const k of ["action_description", "visual_prompt", "voiceover_line", "label"]) if (typeof m[k] !== "string") m[k] = "";
    for (const k of ["characters", "source_ids"]) if (!Array.isArray(m[k])) m[k] = [];
    return m;
  });
  for (const k of ["provenance", "cuts"]) if (!Array.isArray(out[k])) out[k] = [];
  if (!out.jobs || typeof out.jobs !== "object") out.jobs = {};
  if (!out.render) out.render = { burn: true, vo: true };
  if (typeof out.director !== "string") out.director = "";
  return out;
}

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY));
    if (saved?.v === 1) return normalize(saved);
  } catch { /* storage blocked or corrupt: start fresh */ }
  return fresh();
}

let S = load();
const cache = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch { /* private mode */ } };
const save = () => { cache(); if (TEAM) schedulePush(); };

function getPath(path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), S);
}
function setPath(path, value) {
  const keys = path.split(".");
  const last = keys.pop();
  const obj = keys.reduce((o, k) => o[k], S);
  obj[last] = value;
}
const shotById = (id) => S.shots.find((s) => s.id === id);
const upload = (blob, headers = {}) => api.upload(blob, TEAM ? { ...headers, "X-Team": TEAM } : headers);
const shotNo = (shot) => pad(S.shots.indexOf(shot) + 1);

const server = { reachable: false, authed: false, status: null, skipped: false };
const vo = { recorder: null, chunks: [], url: null, blob: null, started: 0, timer: null };

// ------------------------------------------------------------------ derived

function gateOpen(n) {
  if (n === 1) return true;
  if (n === 2) return !!S.gates.g1;
  if (n === 3) return !!S.gates.g1 && !!S.gates.g2;
  return !!S.gates.g1 && !!S.gates.g2 && !!S.gates.g3;
}

function blockers(n) {
  const b = S.brief;
  const out = [];
  if (n === 1) {
    if (b.project_title.trim().length < 3) out.push("Name the project.");
    if (b.client.trim().length < 2) out.push("Name the client.");
    if (b.target_audience.trim().length < 3) out.push("Answer: who is it for?");
    if (b.core_feeling.trim().length < 3) out.push("Answer: what should they feel?");
    if (b.call_to_action.trim().length < 3) out.push("Answer: what should they do next?");
    if (b.key_message.trim().length < 3) out.push("Write the key message.");
    if (b.exclusions.length < 3) out.push(`Add ${3 - b.exclusions.length} more exclusion${b.exclusions.length === 2 ? "" : "s"} (${b.exclusions.length} of 3).`);
  } else if (n === 2) {
    if (!S.shots.length) out.push("Add at least one shot.");
    S.shots.forEach((s, i) => {
      if (s.action_description.trim().length < 5) out.push(`Shot ${i + 1}: describe the action.`);
      if (s.visual_prompt.trim().length < 5) out.push(`Shot ${i + 1}: write the visual prompt.`);
      if (s.voiceover_line.trim() && !s.source_ids.length) out.push(`Shot ${i + 1}: the voiceover line needs a source id, or no claim.`);
      if (!s.locked) out.push(`Shot ${i + 1}: lock its specs.`);
    });
  } else if (n === 3) {
    S.shots.forEach((s, i) => {
      if (!s.first.locked) out.push(`Shot ${i + 1}: lock a first frame.`);
      else if (!s.motion.locked && !s.motion.still) out.push(`Shot ${i + 1}: lock a motion take, or hold the still.`);
    });
  }
  if (n <= 3 && S.director.trim().length < 2) out.push("Type the director's name to sign.");
  return out;
}

function auditMetrics() {
  const machine = {};
  const lines = S.shots.filter((s) => s.voiceover_line.trim());
  const cited = lines.filter((s) => s.source_ids.length);
  machine.intent = `Exclusions to check: ${S.brief.exclusions.join("; ") || "none written"}.`;
  machine.evidence = lines.length
    ? `${cited.length} of ${lines.length} spoken lines cite research_log.csv (${[...new Set(cited.flatMap((s) => s.source_ids))].join(", ") || "none"}).`
    : "No spoken lines.";
  const withRef = S.shots.filter((s) => s.last.locked).length;
  machine.continuity = `${withRef} of ${S.shots.length} shots have a last frame drawn from their own first frame.`;
  const motion = S.shots.filter((s) => s.motion.locked).length;
  const still = S.shots.filter((s) => s.motion.still).length;
  const qc = (S.cuts || [])[0]?.qc;
  machine.techqc = `${motion} motion take${motion === 1 ? "" : "s"} and ${still} held still${still === 1 ? "" : "s"}. ` + (qc
    ? `Latest cut, qc_check.py: ${qc.passed ? "pass" : "fail"} (${qc.checks.filter((c) => c.result !== "pass").map((c) => `${c.check} ${c.measured}`).join("; ") || "every check passed"}).`
    : "Render the cut to run the kit's qc_check.py on it.");
  const picked = pickedAssets();
  const logged = picked.filter((a) => S.provenance.some((r) => r.asset_id === a.asset_id && r.status === "APPROVED"));
  machine.provenance = `${logged.length} of ${picked.length} picked assets have an APPROVED row; ${S.provenance.length} rows including rejected takes.`;
  machine.signature = S.audit.signature ? `Signed by ${S.audit.signature}.` : "Not signed.";
  const results = CHECKS.map((c) => S.audit.checks[c.id]?.result);
  const passed = results.filter((r) => r === "Pass").length;
  const gatesOk = S.audit.checks.intent?.result === "Pass" && S.audit.checks.signature?.result === "Pass";
  return { machine, passed, failed: results.filter((r) => r === "Fail").length, risk: Math.round(100 * (7 - passed) / 7),
    gatesOk, release: passed === 7 && !!S.audit.signature };
}

function pickedAssets() {
  const out = [];
  S.shots.forEach((s) => {
    const nn = shotNo(s);
    if (s.ref) out.push({ asset_id: `shot_${nn}_previs_photo`, media: s.ref, dir: "previs" });
    for (const slot of ["first", "last", "motion"]) {
      const t = s[slot];
      if (t.locked && t.pick) out.push({ asset_id: assetId(s, slot, t.pick), media: t.pick, dir: slot === "motion" ? "motion" : "frames" });
    }
  });
  return out;
}

function assetId(shot, slot, media) {
  const k = shot[slot].takes.indexOf(media) + 1;
  return `shot_${shotNo(shot)}_${slot === "motion" ? "motion" : slot + "_frame"}_take${k}`;
}

// ------------------------------------------------------------------ provenance

function upsertRow(row) {
  const i = S.provenance.findIndex((r) => r.asset_id === row.asset_id);
  if (i >= 0) S.provenance[i] = { ...S.provenance[i], ...row };
  else S.provenance.push({ timestamp: nowIso(), checkpoint_hash: "N/A", human_approver: "", status: "PENDING_REVIEW", ...row });
}

function logTake(shot, slot, meta) {
  const stage = { first: "keyframe", last: "keyframe_last", motion: "motion" }[slot];
  const extra = [meta.reference ? `reference: ${meta.reference}` : "", meta.start ? `first frame: ${meta.start}` : "",
    meta.end ? `last frame: ${meta.end}` : "", meta.credits ? `${meta.credits} Flow credits${meta.reused ? ", spent earlier" : ""}` : ""].filter(Boolean).join(" | ");
  upsertRow({ asset_id: assetId(shot, slot, meta.name), timestamp: meta.created || nowIso(), stage,
    tool_or_model: meta.tool_or_model, seed: meta.seed ?? "", prompt_or_input: meta.prompt + (extra ? ` | ${extra}` : ""),
    media: meta.name });
}

function decideTakes(shot, slot, approve) {
  const t = shot[slot];
  t.takes.forEach((m) => {
    const id = assetId(shot, slot, m);
    if (!S.provenance.some((r) => r.asset_id === id)) return;
    upsertRow({ asset_id: id, status: approve ? (m === t.pick ? "APPROVED" : "REJECTED") : "PENDING_REVIEW",
      human_approver: approve ? S.director || "Director" : "" });
  });
}

// ------------------------------------------------------------------ team sync
// Each phone sends path/value changes; every 2.5 s it asks for anything newer
// and merges it in, keeping edits made while the request was out. The last
// write to a field wins, which suits people working on different cards.

const team = { version: -1, synced: null, members: [], name: "", visibility: "private", timer: null, pushing: false, again: false, missing: false };
const clone = (x) => JSON.parse(JSON.stringify(x));
const sharedOf = (s) => Object.fromEntries(Object.entries(s).filter(([k]) => !LOCAL_KEYS.includes(k)));
const localOf = (s) => Object.fromEntries(Object.entries(s).filter(([k]) => LOCAL_KEYS.includes(k)));

function diffOps(a, b, path = "", out = []) {
  if (a === b) return out;
  const obj = (x) => x !== null && typeof x === "object";
  if (obj(a) && obj(b) && Array.isArray(a) === Array.isArray(b) && (!Array.isArray(a) || a.length === b.length)) {
    for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) {
      const p = path ? `${path}.${k}` : k;
      if (!(k in b)) out.push({ p, del: true });
      else diffOps(a[k], b[k], p, out);
    }
  } else if (JSON.stringify(a) !== JSON.stringify(b)) {
    out.push({ p: path, v: b === undefined ? null : clone(b) });
  }
  return out;
}

function applyOps(target, ops) {
  for (const op of ops) {
    const keys = op.p.split(".");
    const last = keys.pop();
    let node = target;
    for (const k of keys) {
      if (node[k] === null || typeof node[k] !== "object") node[k] = {};
      node = node[k];
    }
    if (op.del) delete node[last];
    else node[last] = clone(op.v);
  }
}

function schedulePush() {
  clearTimeout(team.timer);
  team.timer = setTimeout(push, 350);
}

async function push() {
  team.timer = null;
  if (!TEAM || !team.synced || !server.authed) return;
  if (team.pushing) { team.again = true; return; }
  const cur = sharedOf(S);
  const ops = diffOps(team.synced, cur);
  if (!ops.length) return;
  team.pushing = true;
  try {
    await api.post(`/api/teams/${TEAM}/ops`, { ops });
    team.synced = clone(cur);
  } catch { /* stays unsynced; the next save or pull retries */ } finally {
    team.pushing = false;
    if (team.again) { team.again = false; schedulePush(); }
  }
}

const deferred = new Set();
async function pull() {
  if (!TEAM || !server.authed) return;
  if (team.timer) { clearTimeout(team.timer); await push(); }
  const q = new URLSearchParams({ since: team.version, who: CLIENT_ID, name: S.director || "", role: S.role });
  let r;
  try { r = await api.get(`/api/teams/${TEAM}?${q}`); } catch (e) {
    if (e.status === 404 && !team.missing) { team.missing = true; banner(); }
    return;
  }
  team.members = r.members;
  team.name = r.name;
  team.visibility = r.visibility;
  if ("state" in r) {
    if (r.state === null) {
      // A brand-new team: this phone's project seeds it.
      await api.post(`/api/teams/${TEAM}/ops`, { ops: [{ p: "", v: sharedOf(S) }] }).catch(() => {});
      team.version = -1;
      return;
    }
    const pending = team.synced ? diffOps(team.synced, sharedOf(S)) : [];
    const remote = team.synced ? diffOps(team.synced, r.state) : null;
    team.synced = clone(r.state);
    team.version = r.version;
    if (remote === null) S = { ...clone(r.state), ...localOf(S) };
    else applyOps(S, remote);
    if (pending.length) { applyOps(S, pending); schedulePush(); }
    S = normalize(S);
    cache();
    if (applyImports()) schedulePush();
    if (remote === null || remote.length) remoteChanged(remote || []);
    if (Object.keys(S.jobs || {}).length) poll();
  }
  renderTeamChip();
}

// Re-render what changed, then put the cursor back where it was. If a
// teammate changed the very field being typed in, that one waits until the
// typing stops, so nobody's sentence is overwritten mid-word.
function remoteChanged(remote = []) {
  const active = document.activeElement;
  const bind = active?.dataset?.bind;
  const focusGate = active?.closest?.(".gate");
  if (bind && remote.some((op) => op.p === bind || bind.startsWith(`${op.p}.`))) {
    deferred.add(Number(focusGate?.id.slice(5)));
  }
  // Half-typed drafts in add-a-row boxes (exclusions, facts, provenance) are not
  // in the state, so carry them across the re-render by hand.
  const drafts = $$("form[data-form] [name]").map((el) => [`[data-form="${el.form.dataset.form}"] [name="${el.name}"]`, el.value]);
  const key = bind ? `[data-bind="${CSS.escape(bind)}"]`
    : active?.form?.dataset?.form && active.name ? `[data-form="${active.form.dataset.form}"] [name="${active.name}"]` : null;
  const sel = key && "selectionStart" in active ? [active.selectionStart, active.selectionEnd] : null;
  const typed = key ? active.value : null;
  const y = window.scrollY;
  [renderGate1, renderGate2, renderGate3, renderGate4].forEach((r) => r());
  refresh();
  for (const [k, v] of drafts) { const el = document.querySelector(k); if (el && v) el.value = v; }
  if (key) {
    const again = document.querySelector(key);
    if (again) {
      if (typed !== null && again.value !== typed) again.value = typed;  // keep what is being typed
      again.focus({ preventScroll: true });
      if (sel) { try { again.setSelectionRange(sel[0], sel[1]); } catch { /* not a text field */ } }
    }
  }
  window.scrollTo(0, y);
}

document.addEventListener("focusout", () => setTimeout(() => {
  if (!deferred.size || document.activeElement?.closest?.(".gate")) return;
  deferred.forEach((n) => renderGate(n));
  deferred.clear();
}, 120));

function renderTeamChip() {
  const el = $("#team-chip");
  if (!el) return;
  const others = team.members.filter((m) => m.id !== CLIENT_ID).length;
  el.textContent = `${team.name || TEAM} · ${team.members.length || 1} here`;
  el.setAttribute("aria-label", `Team ${team.name || TEAM}, ${others} other ${others === 1 ? "person" : "people"} here. Open team details`);
}

function openTeam() {
  const url = `${location.origin}/t/${TEAM}`;
  openSheet(`<div class="sheet-head"><div><span class="tag slate-kicker">Team</span><h2 id="sheet-title">${h(team.name || TEAM)}</h2></div><button class="btn small" data-act="close">Close</button></div>
    <div class="sheet-body">
      <p class="lede">Everyone with this link and the access code works on the same project. Your role and your name stay on your phone; everything else is shared.</p>
      <div class="field"><span class="field-label">Who can find it</span>
        <div class="choice" role="group" aria-label="Team visibility" style="grid-template-columns:1fr 1fr">
          <button data-act="visibility" data-v="private" aria-pressed="${team.visibility !== "community"}"><small>Only people with the link</small>Private</button>
          <button data-act="visibility" data-v="community" aria-pressed="${team.visibility === "community"}"><small>Listed on the teams page</small>Community</button></div>
        <span class="field-hint">Files stay with the team either way; share single frames and clips from the library. The workshop admin can see everything.</span></div>
      <div class="row"><input type="text" readonly value="${h(url)}" class="grow mono-input" aria-label="Team link"><button class="btn small" data-act="copy-link">Copy link</button></div>
      <label class="field"><span class="field-label">Your name <em>shown to the team and used when you sign</em></span><input type="text" data-bind="director" value="${h(S.director)}" placeholder="Your name"></label>
      <div class="svc">${team.members.map((m) => `<div class="machine"><b>${h(m.name || "Someone")}</b>${m.id === CLIENT_ID ? " (you)" : ""} · ${h(ROLES.find((r) => r.id === m.role)?.label || m.role || "")}</div>`).join("") || '<p class="muted small">Just you so far.</p>'}</div>
      <div class="row"><a class="btn ghost" href="/teams">All teams</a><a class="btn ghost" href="/queue">Queue</a></div>
    </div>`);
}

// ------------------------------------------------------------------ toasts

let toastTimer;
function toast(msg, kind = "") {
  const el = $("#toast");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, kind === "bad" ? 7000 : 3500);
}

// ------------------------------------------------------------------ shell

function shell() {
  document.body.innerHTML = `
  <a class="sr-only" href="#gate-1">Skip to the brief</a>
  <header class="top">
    <div class="top-bar">
      <a class="brand" href="#gate-1" aria-label="XPSR Director, back to the top">
        <span class="brand-mark" aria-hidden="true"></span>
        <span><span class="brand-name">XPSR</span><br><span class="brand-sub">Director</span></span>
      </a>
      <span class="tc" id="tc" aria-hidden="true">00:00:00:00</span>
      <div class="lights">
        <a class="light" id="light-gpu" href="/resources" title="Local GPU">GPU</a>
        <button class="light" id="light-flow" data-act="accounts" title="Google Flow">FLOW</button>
      </div>
      <button class="btn small primary" data-act="pack">Pack</button>
    </div>
    <nav class="roles" aria-label="Crew role">
      ${TEAM ? `<button class="role team-chip" id="team-chip" data-act="team">${h(TEAM)}</button>` : `<a class="role team-chip" href="/teams">Personal · teams</a>`}
      ${ROLES.map((r) => `<button class="role" data-act="role" data-id="${r.id}" aria-pressed="${S.role === r.id}">${h(r.label)}${r.phone ? '<span class="phone" aria-label="phone OK">📱</span>' : ""}</button>`).join("")}
    </nav>
  </header>
  <main id="main">
    <div id="banner"></div>
    <section class="gate" id="gate-1" aria-labelledby="g1-title"></section>
    <section class="gate" id="gate-2" aria-labelledby="g2-title"></section>
    <section class="gate" id="gate-3" aria-labelledby="g3-title"></section>
    <section class="gate" id="gate-4" aria-labelledby="g4-title"></section>
  </main>
  <footer class="foot">Runs on this machine: Ollama and ComfyUI for writing and frames, Google Flow only for motion.
    <a href="/library${TEAM ? `?team=${TEAM}` : ""}">Library</a> · <a href="/admin">Admin</a> · <a href="/queue">Queue</a> · <a href="/teams">Teams</a> · <a href="/resources">Machine resources</a> · <button class="btn small ghost" data-act="reset">Start over</button></footer>
  <nav class="rail" aria-label="Gates"><div class="rail-inner" id="rail"></div></nav>
  <div class="sheet-back" id="sheet" hidden></div>
  <div class="toast" id="toast" role="status" aria-live="polite" hidden></div>`;
  document.body.dataset.role = S.role;
}

function banner() {
  const el = $("#banner");
  if (TEAM && team.missing) {
    el.innerHTML = `<p class="notice bad" style="margin-bottom:14px">There is no team called ${h(TEAM)} on this server. <a href="/teams">Make it on the teams page</a>, then open its link.</p>`;
    return;
  }
  if (!server.reachable) {
    el.innerHTML = `<p class="notice warn" style="margin-bottom:14px">Offline: the director server is not reachable. Brief, shots and audit save on this phone; frames and motion wait for the connection.</p>`;
  } else if (!server.authed) {
    el.innerHTML = `<form class="card" data-form="login" style="margin-bottom:14px">
      <div class="card-head"><span class="card-title"><b>Access code</b> · unlocks the GPU and Flow</span></div>
      <label class="field"><span class="field-label">Code from the director's machine</span>
        <input type="password" name="code" autocomplete="current-password" autocapitalize="none" spellcheck="false" class="mono-input" required></label>
      <button class="btn primary" type="submit">Unlock</button>
      <p class="field-hint">Without it you can still write the brief, block shots and audit on this phone.</p></form>`;
  } else el.innerHTML = "";
}

// ------------------------------------------------------------------ pieces

function badges(roles) {
  const objs = ROLES.filter((r) => roles.includes(r.id));
  return `<div class="badges">${objs.map((r) => `<span class="badge${r.id === S.role ? " me" : ""}">${h(r.label)}</span>`).join("")}${objs.some((r) => r.phone) ? '<span class="badge phone">📱 Phone OK</span>' : ""}</div>`;
}

function card(roles, title, body, extraClass = "") {
  return `<div class="card ${extraClass}" data-roles="${roles.join(" ")}">
    <div class="card-head"><span class="card-title">${title}</span>${badges(roles)}</div>${body}</div>`;
}

function slate(n, kicker, title, cells) {
  const open = gateOpen(n);
  const signed = n < 4 ? !!S.gates[`g${n}`] : auditMetrics().release;
  return `<div class="slate ${!open ? "locked" : signed ? "passed" : ""}">
    <div class="slate-stripes" aria-hidden="true"></div>
    <div class="slate-body">
      <div class="slate-row"><div><span class="tag slate-kicker">Gate 0${n} · ${h(kicker)}</span><h2 id="g${n}-title">${h(title)}</h2></div></div>
      <div class="slate-grid">${cells.map(([k, v]) => `<div><span class="k">${h(k)}</span><span class="v">${h(v)}</span></div>`).join("")}</div>
    </div></div>`;
}

function lockout(n, prev) {
  return `<div class="lockout"><span class="tag">Locked · Gate 0${prev} not signed</span>
    <h3>Gate 0${n} waits for Gate 0${prev}</h3>
    <p>Each gate opens only after the director signs the one before it. Nothing downstream is made from an unapproved brief, shot or frame.</p>
    <a class="btn primary" href="#gate-${prev}">Go to Gate 0${prev}</a></div>`;
}

function field(label, path, { area = false, hint = "", placeholder = "", type = "text", mono = false, disabled = false, rows = 3 } = {}) {
  const v = getPath(path);
  const attrs = `data-bind="${path}" ${type === "number" ? 'data-num="1"' : ""} placeholder="${h(placeholder)}" ${disabled ? "disabled" : ""} class="${mono ? "mono-input" : ""}"`;
  return `<label class="field"><span class="field-label">${label}</span>
    ${area ? `<textarea rows="${rows}" ${attrs}>${h(v)}</textarea>` : `<input type="${type}" inputmode="${type === "number" ? "decimal" : "text"}" value="${h(v)}" ${attrs}>`}
    ${hint ? `<span class="field-hint">${hint}</span>` : ""}</label>`;
}

function seal(n, label) {
  return `<div class="card" data-roles="director">
    <div class="card-head"><span class="card-title"><b>${h(label)}</b></span>${badges(["director"])}</div>
    ${field("Director's name", "director", { placeholder: "The human who signs" })}
    <div id="seal-${n}"></div></div>`;
}

function sealDynamic(n) {
  const signed = S.gates[`g${n}`];
  const bl = blockers(n);
  const blocked = !signed && bl.length > 0;
  const cls = signed ? "signed" : blocked ? "blocked" : "";
  const state = signed ? "Signed · gate passed" : blocked ? "Blocked" : "Awaiting signature";
  return `<div class="seal ${cls}">
    <div class="seal-head"><span class="tag">Gate 0${n} sign-off</span><span class="seal-state">${state}</span></div>
    ${blocked ? `<ul class="blockers">${bl.map((b) => `<li>${h(b)}</li>`).join("")}</ul>` : ""}
    <div class="slider">
      <div class="slider-fill" style="width:${signed ? 100 : 0}%"></div>
      <div class="slider-text">${signed ? "Slide back to reopen" : blocked ? "Clear the list above" : "Slide to approve and lock"}</div>
      <input type="range" min="0" max="100" value="${signed ? 100 : 0}" data-seal="${n}" ${blocked ? "disabled" : ""}
        aria-label="${signed ? `Reopen gate 0${n}` : `Approve gate 0${n}: slide to the end`}">
    </div>
    ${signed ? `<div class="seal-sig"><span>Approved by ${h(signed.director)}</span><span class="num">${new Date(signed.at).toLocaleString()}</span></div>` : ""}
  </div>`;
}

// ------------------------------------------------------------------ gate 1

function renderGate1() {
  const b = S.brief;
  const p = PRESETS[b.preset];
  const sug = S.suggest;
  $("#gate-1").innerHTML = `<div class="stack">
    ${slate(1, "Intent and anti-drift", "The brief", [["Client", b.client || "—"], ["Runtime", `${b.runtime_sec}s`], ["Decision", S.gates.g1 ? "Approved" : "Open"]])}
    ${card(["director"], "<b>01A</b> · Client", `
      <div class="choice" role="group" aria-label="Client">
        ${Object.entries(PRESETS).map(([k, v]) => `<button data-act="preset" data-id="${k}" aria-pressed="${b.preset === k}"><small>${h(v.kicker)}</small>${h(v.label)}</button>`).join("")}
      </div>
      <p class="lede">${h(p.ask)}</p>
      <div class="grid-2">${field("Project title", "brief.project_title")}${field("Client", "brief.client")}</div>
      ${b.facts.length ? `<div class="facts" aria-label="Facts you may claim">${b.facts.map(([id, t]) => `<div class="fact"><b>${h(id)}</b><span>${h(t)}</span></div>`).join("")}</div>` : ""}
      <div class="capture"><div class="capture-copy"><b>Pick up where you left off</b><span>Import a pack this app exported (.zip): the brief, shots, takes, sign-offs, audit and cut come back${TEAM ? " for the whole team" : ""}.</span></div>
        <label class="btn file-btn ${server.authed ? "" : "disabled"}">Import a pack<input type="file" accept=".zip,application/zip" data-file="pack" ${server.authed ? "" : "disabled"}></label></div>
      ${b.preset === "custom" ? `<form class="row" data-form="fact"><input class="grow" name="fact" placeholder="A fact you can prove, one sentence" aria-label="New fact"><button class="btn small" type="submit">Add fact</button></form>` : ""}`)}
    ${card(["director", "writer"], "<b>01B</b> · The director's three answers", `
      ${field("1. Who is it for?", "brief.target_audience", { area: true, rows: 2, placeholder: "A specific person, not a demographic" })}
      ${field("2. What should they feel?", "brief.core_feeling", { area: true, rows: 2, placeholder: "One feeling you could act" })}
      ${field("3. What should they do next?", "brief.call_to_action", { placeholder: "One concrete action" })}
      ${field("Key message <em>only claims with a fact id</em>", "brief.key_message", { area: true, rows: 2 })}`)}
    ${card(["director", "auditor"], `<b>01C</b> · Exclusions · ${b.exclusions.length} of 3`, `
      <p class="lede">Things this spot will never do. The auditor checks the cut against every one.</p>
      <form class="row" data-form="exclusion">
        <input class="grow" name="ex" placeholder="No…" aria-label="New exclusion" autocomplete="off">
        <button class="btn primary" type="submit">Add</button></form>
      <div class="chips">${b.exclusions.map((e, i) => `<span class="chip"><span class="never">NEVER</span>${h(e)}<button data-act="del-ex" data-i="${i}" aria-label="Remove ${h(e)}">×</button></span>`).join("") || '<span class="muted small">None yet.</span>'}</div>`)}
    ${card(["writer"], "<b>01D</b> · Tone and references", `
      <label class="field"><span class="field-label">Tone words <em>comma separated</em></span>
        <input type="text" data-bind="brief.tone" data-list="1" value="${h(b.tone.join(", "))}"></label>
      ${field("References <em>one per line, described in words</em>", "brief.references", { area: true, rows: 3 })}`)}
    ${card(["writer"], "<b>01E</b> · Agent draft · local GPU", `
      <p class="lede">Rough idea in, a draft of the brief out, from the local writing model. It only proposes: nothing lands in the brief until you press Use.</p>
      ${field("Rough idea", "brief.idea", { area: true, rows: 2, placeholder: "e.g. the regulars follow the roaster down the street to the new shop" })}
      <button class="btn" data-act="draft-brief" ${server.authed ? "" : "disabled"}>Draft with ${h(llmModel())}</button>
      ${sug ? `<div class="stack">${Object.entries(sug.fields).map(([k, v]) => `<div class="machine"><b>${h(k.replace(/_/g, " "))}</b><br>${h(Array.isArray(v) ? v.join(" · ") : v)}<br><button class="btn small" data-act="use-sug" data-k="${k}">Use</button></div>`).join("")}
        <p class="field-hint">${h(sug.model)} · ${sug.seconds}s on the local GPU</p></div>` : ""}`)}
    ${seal(1, "Gate 01 · director signs the brief")}
  </div>`;
}

// ------------------------------------------------------------------ gate 2

function shotCard(s, i) {
  const p = PRESETS[S.brief.preset];
  const dis = s.locked ? "disabled" : "";
  const sel = (path, opts, cur, num) => `<select data-bind="${path}" ${num ? 'data-num="1"' : ""} ${dis}>${opts.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return `<option value="${h(v)}" ${String(v) === String(cur) ? "selected" : ""}>${h(l)}</option>`; }).join("")}</select>`;
  const base = `shots.${i}`;
  return `<article class="shot ${s.locked ? "locked" : ""}" aria-label="Shot ${i + 1}">
    <div class="shot-head"><span class="shot-num">SHOT ${pad(i + 1)}</span>
      <h3><input type="text" data-bind="${base}.label" value="${h(s.label)}" aria-label="Shot ${i + 1} name" ${dis} style="min-height:40px;font-weight:800;text-transform:uppercase"></h3>
      <button class="btn small ${s.locked ? "go" : "primary"}" data-act="lock-shot" data-id="${s.id}" aria-pressed="${s.locked}">${s.locked ? "✓ Locked" : "Lock specs"}</button></div>
    <div class="shot-body">
      <div class="grid-3">
        <label class="field"><span class="field-label">Framing</span>${sel(`${base}.framing`, FRAMINGS, s.framing)}</label>
        <label class="field"><span class="field-label">Lens</span>${sel(`${base}.lens_mm`, LENSES.map((l) => [l, `${l} mm`]), s.lens_mm, true)}</label>
        <label class="field"><span class="field-label">Seconds</span><input type="number" min="0.5" max="30" step="0.5" inputmode="decimal" data-bind="${base}.duration_sec" data-num="1" value="${s.duration_sec}" ${dis} class="mono-input"></label>
        <label class="field"><span class="field-label">Camera move</span>${sel(`${base}.camera_move`, MOVES, s.camera_move)}</label>
        <label class="field span-all-sm" style="grid-column:span 2"><span class="field-label">Location</span>${sel(`${base}.location_id`, p.locations, s.location_id)}</label>
      </div>
      ${p.characters.length ? `<div class="field"><span class="field-label">On screen</span><div class="chips">${p.characters.map(([id, name]) => `<button class="btn small ${s.characters.includes(id) ? "go" : "ghost"}" data-act="toggle-char" data-id="${s.id}" data-c="${id}" aria-pressed="${s.characters.includes(id)}" ${dis}>${h(name)}</button>`).join("")}</div></div>` : ""}
      ${field("Action", `${base}.action_description`, { area: true, rows: 2, disabled: s.locked, placeholder: "What happens, in plain words" })}
      ${field("Visual prompt <em>one frame, concrete, no text in frame</em>", `${base}.visual_prompt`, { area: true, rows: 3, disabled: s.locked })}
      ${field("Voiceover line", `${base}.voiceover_line`, { area: true, rows: 2, disabled: s.locked, placeholder: "Leave empty for none" })}
      ${S.brief.facts.length ? `<div class="field"><span class="field-label">Sources for this line</span><div class="chips">${S.brief.facts.map(([id]) => `<button class="btn small ${s.source_ids.includes(id) ? "go" : "ghost"}" data-act="toggle-src" data-id="${s.id}" data-src="${id}" aria-pressed="${s.source_ids.includes(id)}" ${dis}>${h(id)}</button>`).join("")}</div></div>` : ""}
      <div class="capture">
        <div class="capture-copy"><b>📱 Block it with your phone</b><span>Film the move or snap the framing. The photo, or a frame from the video, becomes the layout reference for the first frame.</span></div>
        <label class="btn file-btn ${server.authed ? "" : "disabled"}">📷 Record or snap<input type="file" accept="image/*,video/*" capture="environment" data-file="ref" data-id="${s.id}" ${server.authed ? "" : "disabled"}></label>
      </div>
      ${s.ref ? `<div class="ref-media"><img src="${mediaUrl(s.ref)}" alt="Phone blocking reference for shot ${i + 1}" loading="lazy"><div class="row"><span class="muted small grow">Layout reference</span><button class="btn small danger" data-act="clear-ref" data-id="${s.id}">Remove</button></div></div>` : ""}
      ${!s.locked ? `<div class="shot-tools"><button class="btn small danger" data-act="del-shot" data-id="${s.id}">Delete shot</button></div>` : ""}
    </div></article>`;
}

function renderGate2() {
  const el = $("#gate-2");
  const total = S.shots.reduce((n, s) => n + Number(s.duration_sec || 0), 0);
  if (!gateOpen(2)) {
    el.innerHTML = `<div class="stack">${slate(2, "Previs and blocking", "Shot deck", [["Shots", S.shots.length], ["Runtime", `${total}s`], ["Decision", "Locked"]])}${lockout(2, 1)}</div>`;
    return;
  }
  el.innerHTML = `<div class="stack">
    ${slate(2, "Previs and blocking", "Shot deck", [["Shots", S.shots.length], ["Runtime", `${total} of ${S.brief.runtime_sec}s`], ["Decision", S.gates.g2 ? "Approved" : "Open"]])}
    ${card(["writer", "previs"], "<b>02A</b> · Agent draft · local GPU", `
      <p class="lede">Drafts every unlocked shot from the signed brief: framing, lens, move, action, a visual prompt and a voiceover line that cites only your facts.</p>
      <button class="btn" data-act="draft-shots" ${server.authed ? "" : "disabled"}>Draft unlocked shots with ${h(llmModel())}</button>`)}
    <div class="stack" data-roles="previs director" id="shots">${S.shots.map(shotCard).join("")}</div>
    ${S.shots.length < 12 ? `<button class="btn block ghost" data-act="add-shot">+ Add shot</button>` : ""}
    ${total !== Number(S.brief.runtime_sec) ? `<p class="notice warn">Shots add up to ${total}s; the brief says ${S.brief.runtime_sec}s.</p>` : ""}
    ${seal(2, "Gate 02 · director signs the framing")}
  </div>`;
}

// ------------------------------------------------------------------ gate 3

function flowModels() {
  return server.status?.flow?.models || [];
}
function flowLeft() {
  return server.status?.flow?.left_today ?? 0;
}
function llmModel() {
  const models = server.status?.local?.models || [];
  if (S.llm_model && models.includes(S.llm_model)) return S.llm_model;
  return server.status?.local?.default_model || "llama3.2:3b";
}

// ------------------------------------------------------------------ Flow by hand
// The app prepares everything, the person makes the frame or clip in their
// own Flow tab, and the file comes back here to be catalogued.

const FLOW_URL = () => server.status?.flow?.flow_url || "https://labs.google/fx/tools/flow";

function handPrompt(shot, slot) {
  const t = shot[slot];
  if (slot === "motion") return (t.prompt || `${shot.camera_move}. ${shot.action_description}`).trim();
  const p = (t.prompt || (slot === "first" ? shot.visual_prompt : "")).trim();
  if (slot === "last") return `Use the attached image as the first frame of this shot. Make the last frame of the same shot: the same place, people, wardrobe, light and lens, a moment later. Only this changes: ${p}`;
  if (t.useRef && shot.ref) return `The attached image is a rough phone photo that blocks out this shot. Make a finished photograph that keeps its camera angle, layout and the positions of people and objects, but none of its phone-camera look. Scene: ${p}`;
  return p;
}

function handSteps(shot, slot) {
  const ref = slot === "last" ? shot.first.pick : (shot.first.useRef && shot.ref ? shot.ref : null);
  return `<details class="hand"><summary>Make it in Flow by hand · 4 steps</summary><ol class="hand-steps">
    <li><button class="btn small" data-act="copy-hand" data-id="${shot.id}" data-slot="${slot}">Copy the prompt</button></li>
    ${ref ? `<li><a class="btn small ghost" href="${mediaUrl(ref)}?download=1">Save the ${slot === "last" ? "first frame" : "blocking photo"}</a> and attach it in Flow as the reference image.</li>` : ""}
    <li><a class="btn small ghost" href="${FLOW_URL()}" target="_blank" rel="noopener noreferrer">Open Flow ↗</a> Pick an image model (Nano Banana), paste, generate, and download the take you like.</li>
    <li><label class="btn primary file-btn">Bring the image back<input type="file" accept="image/*" data-file="hand" data-id="${shot.id}" data-slot="${slot}"></label></li>
  </ol></details>`;
}

function handClipSteps(shot, sel, dur, cost, fits) {
  const label = sel ? `${sel.label}, ${dur} seconds` : "Veo 3.1 Lite, 8 seconds";
  return `<ol class="hand-steps">
    <li><a class="btn small ghost" href="${mediaUrl(shot.first.pick)}?download=1">Save the first frame</a>${shot.last.locked ? ` <a class="btn small ghost" href="${mediaUrl(shot.last.pick)}?download=1">Save the last frame</a>` : ""}</li>
    <li><button class="btn small" data-act="copy-hand" data-id="${shot.id}" data-slot="motion">Copy the action</button></li>
    <li><a class="btn small ghost" href="${FLOW_URL()}" target="_blank" rel="noopener noreferrer">Open Flow ↗</a> Use frames to video${shot.last.locked ? " with both frames" : " with the first frame"}, choose <b>${h(label)}</b>, paste, generate, download.</li>
    <li><label class="btn primary file-btn">Bring the clip back · logs ${cost} credits<input type="file" accept="video/mp4,video/*" data-file="hand-clip" data-id="${shot.id}"></label></li>
  </ol>
  <p class="field-hint">Flow takes the credits when you press generate. The app records ${cost} against today's budget when the clip comes back${fits ? "" : `: <span style="color:var(--red-text)">that is more than the ${flowLeft()} left today</span>`}. Picked a different model in Flow? Change it above first, so the ledger matches.</p>`;
}

async function bringBack(shot, slot, file, label) {
  label?.classList.add("busy");
  try {
    let blob = file;
    const headers = { "X-Source": "flow-hand", "X-Label": jobLabel(shot, slot === "motion" ? "motion (made in Flow)" : `${slot} frame (made in Flow)`).label,
      "X-Project": jobLabel(shot, "").project, "X-Prompt": handPrompt(shot, slot), "X-Frame": slot };
    if (slot === "motion") {
      if (file.type && file.type !== "video/mp4") throw new Error("Bring back the MP4 that Flow downloads (this file is " + file.type + ").");
      blob = file.type ? file : new Blob([file], { type: "video/mp4" });
      const model = flowModels().find((x) => x.id === shot.motion.model) || flowModels()[0];
      const dur = clipDuration(shot, model);
      Object.assign(headers, { "X-Model": model?.id || "veo-3.1-lite", "X-Credits": model ? model.costs[dur] : 0, "X-Duration": dur });
    } else {
      blob = await toJpeg(file, 2048);
      headers["X-Model"] = S.flow_frames;
    }
    const { media } = await upload(blob, headers);
    const t = shot[slot];
    t.takes.push(media.name);
    t.pick = media.name;
    if (slot === "motion") t.still = false;
    logTake(shot, slot, media);
    save();
    buzz([10, 30, 10]);
    toast(slot === "motion" ? `Clip catalogued; ${media.credits || 0} credits logged for today.` : "Frame catalogued as a Flow take.", "good");
    await loadStatus();
    renderGate(3);
  } catch (e) {
    toast(e.message, "bad");
  } finally {
    label?.classList.remove("busy");
  }
}

// The shortest clip that covers the shot, or the longest the model makes.
function clipDuration(shot, model) {
  if (!model) return 8;
  if (model.durations.includes(Number(shot.motion.duration))) return Number(shot.motion.duration);
  return model.durations.find((d) => d >= Number(shot.duration_sec)) || model.durations[model.durations.length - 1];
}

function takesGrid(shot, slot) {
  const t = shot[slot];
  const pending = Object.entries(S.jobs).filter(([, j]) => j.shot === shot.id && j.slot === slot);
  const isVideo = slot === "motion";
  if (!t.takes.length && !pending.length && !t.error) return "";
  return `<div class="takes" role="group" aria-label="Takes">
    ${t.takes.map((m, k) => `<button class="take" data-act="pick" data-id="${shot.id}" data-slot="${slot}" data-m="${m}" aria-pressed="${t.pick === m}" ${t.locked ? "disabled" : ""} aria-label="Take ${k + 1}${t.pick === m ? ", picked" : ""}">
      ${isVideo ? `<video src="${mediaUrl(m)}#t=0.5" muted playsinline preload="metadata"></video>` : `<img src="${mediaUrl(m)}" alt="" loading="lazy">`}
      <span class="take-label">TAKE ${k + 1}${t.pick === m ? " · PICK" : ""}</span></button>`).join("")}
    ${pending.map(([, j]) => `<div class="take pending" aria-live="polite">${h(j.note || "Queued")}</div>`).join("")}
  </div>${t.error ? `<p class="notice bad">${h(t.error)}</p>` : ""}`;
}

function sourceButtons(shot, slot) {
  const t = shot[slot];
  const g = server.status?.gemini;
  const opts = [["local", "Local GPU", "free · automatic"], ["gemini", "Gemini API", g ? `~$${(g.models.find((m) => m.id === g.model)?.usd || 0.034).toFixed(3)} · your key` : "your key"],
    ["hand", "Flow by hand", "free · you click"], ["flow", "Flow via useapi", "0 credits · paid bridge"], ["upload", "Photo", "human"]];
  return `<div class="choice" role="group" aria-label="Where the frame comes from" style="grid-template-columns:repeat(2,1fr)">
    ${opts.map(([v, l, c]) => `<button data-act="source" data-id="${shot.id}" data-slot="${slot}" data-v="${v}" aria-pressed="${t.source === v}" ${t.locked ? "disabled" : ""}><small>${c}</small>${l}</button>`).join("")}</div>`;
}

function frameControls(shot, slot) {
  const t = shot[slot];
  const i = S.shots.indexOf(shot);
  const isLast = slot === "last";
  if (t.locked) {
    return `<div class="picked"><img src="${mediaUrl(t.pick)}" alt="Locked ${slot} frame for shot ${i + 1}">
      <button class="btn small ghost" data-act="unlock" data-id="${shot.id}" data-slot="${slot}">Unlock ${slot} frame</button></div>`;
  }
  if (!isLast && !t.prompt && shot.visual_prompt) t.prompt = shot.visual_prompt;
  const flowOk = server.status?.flow?.configured;
  let go;
  if (t.source === "hand") {
    return `${sourceButtons(shot, slot)}
      ${field(isLast ? "What has changed by the last frame" : "Frame prompt", `shots.${i}.${slot}.prompt`, { area: true, rows: 3,
        placeholder: isLast ? "e.g. the cup is now full and steaming, the roaster has stepped back" : shot.visual_prompt })}
      ${handSteps(shot, slot)}
      ${t.pick ? `<div class="row"><button class="btn go" data-act="lock" data-id="${shot.id}" data-slot="${slot}">Lock take ${t.takes.indexOf(t.pick) + 1}</button>${isLast ? `<button class="btn ghost" data-act="skip-last" data-id="${shot.id}">No last frame</button>` : ""}</div>` : isLast ? `<div class="row"><button class="btn ghost" data-act="skip-last" data-id="${shot.id}">No last frame</button></div>` : ""}
      ${takesGrid(shot, slot)}`;
  }
  if (t.source === "upload") {
    go = `<label class="btn primary file-btn">📷 Take or choose photo<input type="file" accept="image/*" capture="environment" data-file="frame" data-id="${shot.id}" data-slot="${slot}"></label>`;
  } else if (t.source === "flow" && !flowOk) {
    go = `<button class="btn" data-act="accounts">Connect Google Flow first</button>`;
  } else if (t.source === "gemini" && !server.status?.gemini?.configured) {
    go = `<button class="btn" data-act="accounts">Add a Gemini API key first</button>`;
  } else {
    const label = { local: "Render on local GPU", flow: "Render on Flow · 0 credits",
      gemini: `Render with Gemini · about $${(server.status?.gemini?.models.find((m) => m.id === server.status.gemini.model)?.usd || 0.034).toFixed(3)}` }[t.source];
    go = `<button class="btn primary" data-act="frame" data-id="${shot.id}" data-slot="${slot}" ${server.authed ? "" : "disabled"}>${label}</button>`;
  }
  return `${sourceButtons(shot, slot)}
    ${t.source !== "upload" ? field(isLast ? "What has changed by the last frame" : "Frame prompt", `shots.${i}.${slot}.prompt`, { area: true, rows: 3,
      placeholder: isLast ? "e.g. the cup is now full and steaming, the roaster has stepped back" : shot.visual_prompt }) : ""}
    ${!isLast && shot.ref && t.source !== "upload" ? `<label class="row"><input type="checkbox" data-bind="shots.${i}.first.useRef" data-bool="1" ${t.useRef ? "checked" : ""} style="width:24px;height:24px"> <span class="small">Follow the phone blocking photo's layout</span></label>` : ""}
    ${isLast && t.source !== "upload" ? `<p class="field-hint">Drawn from the locked first frame, so the place, people and light carry over.</p>` : ""}
    <div class="row">${go}${t.pick ? `<button class="btn go" data-act="lock" data-id="${shot.id}" data-slot="${slot}">Lock take ${t.takes.indexOf(t.pick) + 1}</button>` : ""}
      ${isLast ? `<button class="btn ghost" data-act="skip-last" data-id="${shot.id}">No last frame</button>` : ""}</div>
    ${takesGrid(shot, slot)}`;
}

function meter(cost) {
  const f = server.status?.flow;
  if (!f) return "";
  const budget = f.daily_budget || 1;
  const spent = Math.min(f.spent_today, budget);
  const fits = cost <= f.left_today;
  const w = (n) => `${Math.max(0, Math.min(100, (100 * n) / budget))}%`;
  return `<div class="meter" aria-label="Flow credits today">
    <div class="meter-bar"><span class="spent" style="width:${w(spent)}"></span><span class="${fits ? "this" : "over"}" style="width:${w(fits ? cost : f.left_today)}"></span></div>
    <div class="meter-legend"><span><b class="num">${f.spent_today}</b> of <b class="num">${f.daily_budget}</b> credits used today</span>
      <span>${cost ? (fits ? `this clip <b class="num">${cost}</b>, then <b class="num">${f.left_today - cost}</b> left` : `<span style="color:var(--red-text)">this clip needs ${cost}; ${f.left_today} left</span>`) : `<b class="num">${f.left_today}</b> left`}</span>
      ${f.balance ? `<span>account balance <b class="num">${f.balance.credits}</b></span>` : ""}</div></div>`;
}

const ENGINES = [
  ["camera", "Camera move", "instant · CPU · free", "Moves over the still; dissolves to the last frame"],
  ["ltx", "LTX-Video", "1 to 2 min · GPU · free", "Uses the first and last frames"],
  ["wan-draft", "Wan 2.2 draft", "a few min · GPU · free", "First frame only, small preview"],
  ["wan-full", "Wan 2.2 full", "about 24 min · GPU · free", "First frame only, the examples' quality"],
  ["hand", "Flow by hand", "you click · Flow credits", "Made in your own Flow tab"],
  ["useapi", "Flow via useapi", "paid bridge · Flow credits", "Rendered from here through useapi.net"],
];

function motionEngine(shot) {
  const have = server.status?.local?.motion || {};
  const e = shot.motion.engine;
  if (e && (have[e] !== false || ["hand", "useapi"].includes(e))) return e;
  return have.ltx ? "ltx" : "camera";
}

function motionControls(shot) {
  const m = shot.motion;
  const i = S.shots.indexOf(shot);
  const ready = shot.first.locked && (shot.last.locked || shot.last.skip);
  if (m.still) {
    return `<p class="notice good">Holding the first frame as a still for ${shot.duration_sec}s. No credits.</p>
      <button class="btn small ghost" data-act="still" data-id="${shot.id}">Animate it after all</button>`;
  }
  if (m.locked) {
    return `<div class="picked"><video src="${mediaUrl(m.pick)}" controls playsinline preload="metadata" aria-label="Locked motion take for shot ${i + 1}"></video>
      <button class="btn small ghost" data-act="unlock" data-id="${shot.id}" data-slot="motion">Unlock motion</button></div>`;
  }
  const engine = motionEngine(shot);
  const have = server.status?.local?.motion || {};
  const flowEngine = engine === "hand" || engine === "useapi";
  const models = flowModels();
  const sel = models.find((x) => x.id === m.model) || models[0];
  const dur = clipDuration(shot, sel);
  const cost = sel ? sel.costs[dur] : 0;
  const flowOk = server.status?.flow?.configured;
  const fits = cost <= flowLeft();
  const pick = m.pick ? `<button class="btn go" data-act="lock" data-id="${shot.id}" data-slot="motion">Lock take ${m.takes.indexOf(m.pick) + 1}</button>` : "";
  const still = `<button class="btn ghost" data-act="still" data-id="${shot.id}" ${shot.first.locked ? "" : "disabled"}>Hold the still</button>`;
  let body;
  if (engine === "camera") {
    body = `<label class="field"><span class="field-label">Camera move</span>
        <select data-bind="shots.${i}.motion.move" data-rerender="3">${MOVES.map((mv) => `<option ${mv === (m.move || shot.camera_move) ? "selected" : ""}>${mv}</option>`).join("")}</select></label>
      <p class="field-hint">${shot.last.locked ? "Moves over the first frame and dissolves into the last frame through the middle third." : "Moves over the first frame."} No model: it only moves the camera, so nothing in the frame changes shape.</p>
      <div class="row"><button class="btn primary" data-act="local-motion" data-id="${shot.id}" ${ready && server.authed ? "" : "disabled"}>Make the camera move · instant</button>${pick}${still}</div>`;
  } else if (!flowEngine) {
    body = `${field("Action <em>only what moves between the two frames</em>", `shots.${i}.motion.prompt`, { area: true, rows: 3, placeholder: `${shot.camera_move}. ${shot.action_description}` })}
      <div class="row"><button class="btn small" data-act="draft-action" data-id="${shot.id}" ${server.authed && ready ? "" : "disabled"}>Write it with ${h(llmModel())}</button></div>
      ${engine.startsWith("wan") && shot.last.locked ? `<p class="field-hint">Wan 2.2 5B animates from the first frame only; the last frame is not used. LTX-Video uses both.</p>` : ""}
      <div class="row"><button class="btn primary" data-act="local-motion" data-id="${shot.id}" ${ready && server.authed ? "" : "disabled"}>Render on the local GPU · free</button>${pick}${still}</div>
      <p class="field-hint">Joins the GPU queue; see <a href="/queue">the queue</a> for its place in line, or <a href="http://${location.hostname}:8188" target="_blank" rel="noopener">watch it in ComfyUI ↗</a>.</p>`;
  } else {
    body = `${field("Action <em>only what moves between the two frames</em>", `shots.${i}.motion.prompt`, { area: true, rows: 3, placeholder: `${shot.camera_move}. ${shot.action_description}` })}
      <div class="row"><button class="btn small" data-act="draft-action" data-id="${shot.id}" ${server.authed && ready ? "" : "disabled"}>Write it with ${h(llmModel())}</button></div>
      ${models.length ? `<label class="field"><span class="field-label">Flow video model</span>
        <select data-bind="shots.${i}.motion.model" data-rerender="3">${models.map((x) => `<option value="${x.id}" ${x.id === sel?.id ? "selected" : ""} ${x.allowed ? "" : "disabled"}>${h(x.label)} · ${x.durations.length > 1 ? `from ${x.costs[x.durations[0]]} credits · ${x.durations[0]} to ${x.durations[x.durations.length - 1]}s` : `${x.costs[x.durations[0]]} credits · ${x.durations[0]}s`}${x.allowed ? "" : " (paid plan)"}</option>`).join("")}</select></label>` : ""}
      ${sel && sel.durations.length > 1 ? `<label class="field"><span class="field-label">Clip length</span>
        <select data-bind="shots.${i}.motion.duration" data-num="1" data-rerender="3">${sel.durations.map((d) => `<option value="${d}" ${d === dur ? "selected" : ""}>${d} seconds · ${sel.costs[d]} credits</option>`).join("")}</select></label>` : ""}
      ${meter(cost)}
      ${engine === "useapi"
        ? `<div class="row">${flowOk ? `<button class="btn primary" data-act="motion" data-id="${shot.id}" ${ready && fits && server.authed ? "" : "disabled"}>Render through useapi · ${cost} credits</button>` : `<button class="btn" data-act="accounts">Connect useapi.net</button>`}${pick}${still}</div>`
        : `<details class="hand"><summary>Make it in Flow by hand · 4 steps</summary>${handClipSteps(shot, sel, dur, cost, fits)}</details><div class="row">${pick}${still}</div>`}
      ${dur > shot.duration_sec ? `<p class="field-hint">Flow renders ${dur}s; the cut trims it to the shot's ${shot.duration_sec}s.</p>` : ""}`;
  }
  return `<div class="frame-pair">
      <figure>${shot.first.pick && shot.first.locked ? `<img src="${mediaUrl(shot.first.pick)}" alt="First frame">` : `<div class="empty-frame">first frame</div>`}<figcaption>First</figcaption></figure>
      <span class="arrow" aria-hidden="true">→</span>
      <figure>${shot.last.locked ? `<img src="${mediaUrl(shot.last.pick)}" alt="Last frame">` : `<div class="empty-frame">${shot.last.skip ? "model decides" : "last frame"}</div>`}<figcaption>Last</figcaption></figure></div>
    <div class="field"><span class="field-label">Motion engine</span>
      <div class="choice engines" role="group" aria-label="Motion engine">${ENGINES.map(([id, label, cost, what]) => {
        const off = !["hand", "useapi"].includes(id) && have[id] === false;
        return `<button data-act="engine" data-id="${shot.id}" data-v="${id}" aria-pressed="${engine === id}" ${off ? "disabled" : ""} title="${h(what)}"><small>${h(off ? "not installed" : cost)}</small>${h(label)}</button>`;
      }).join("")}</div></div>
    ${body}
    ${takesGrid(shot, "motion")}`;
}

function workCard(shot, i) {
  const f = shot.first, l = shot.last, m = shot.motion;
  const lastReady = f.locked;
  const motionReady = f.locked && (l.locked || l.skip);
  return `<article class="shot ${m.locked || m.still ? "locked" : ""}" data-roles="frames editsound" aria-label="Shot ${i + 1} frames and motion">
    <div class="shot-head"><span class="shot-num">SHOT ${pad(i + 1)}</span><h3>${h(shot.label)}</h3>
      <span class="badge">${h(shot.framing)} · ${shot.lens_mm}mm · ${h(shot.camera_move)}</span></div>
    <div class="two-pass">
      <div class="pass ${f.locked ? "done" : ""}">
        <div class="pass-head"><span class="pass-step"><span class="n">1</span>Pass 1 · First frame</span><span class="badge free">0 credits</span></div>
        ${frameControls(shot, "first")}
      </div>
      <div class="pass ${l.locked || l.skip ? "done" : ""} ${lastReady ? "" : "wait"}">
        <div class="pass-head"><span class="pass-step"><span class="n">1b</span>Last frame <span class="muted">optional</span></span><span class="badge free">0 credits</span></div>
        <span class="lock-note">Lock the first frame to unlock the last frame.</span>
        ${!lastReady ? "" : l.skip ? `<p class="small muted">No last frame: Flow decides where the shot ends.</p><button class="btn small ghost" data-act="skip-last" data-id="${shot.id}">Add a last frame</button>` : frameControls(shot, "last")}
      </div>
      <div class="pass ${m.locked || m.still ? "done" : ""} ${motionReady ? "" : "wait"}">
        <div class="pass-head"><span class="pass-step"><span class="n">2</span>Pass 2 · Action</span><span class="badge cost">Flow credits</span></div>
        <span class="lock-note">Two-pass rule: motion unlocks after the frames are locked.</span>
        ${motionReady ? motionControls(shot) : ""}
      </div>
    </div></article>`;
}

function provTable() {
  if (!S.provenance.length) return '<p class="muted small">Rows appear here as frames and clips are made.</p>';
  return `<div class="table-wrap"><table><thead><tr><th>asset_id</th><th>stage</th><th>tool_or_model</th><th>seed</th><th>status</th><th>prompt_or_input</th><th><span class="sr-only">Remove</span></th></tr></thead><tbody>
    ${S.provenance.map((r, i) => `<tr><td>${h(r.asset_id)}</td><td>${h(r.stage)}</td><td>${h(r.tool_or_model)}</td><td class="num">${h(r.seed)}</td><td><span class="status ${h(r.status)}">${h(r.status)}</span></td><td class="prompt">${h(String(r.prompt_or_input).slice(0, 140))}${String(r.prompt_or_input).length > 140 ? "…" : ""}</td>
      <td>${r.manual ? `<button class="btn small danger" data-act="del-row" data-i="${i}" aria-label="Remove row ${h(r.asset_id)}">×</button>` : ""}</td></tr>`).join("")}
  </tbody></table></div>`;
}

function renderGate3() {
  const el = $("#gate-3");
  const done = S.shots.filter((s) => s.motion.locked || s.motion.still).length;
  const f = server.status?.flow;
  const cells = [["Shots done", `${done} of ${S.shots.length}`], ["Flow today", f ? `${f.spent_today}/${f.daily_budget} cr` : "—"], ["Decision", S.gates.g3 ? "Approved" : gateOpen(3) ? "Open" : "Locked"]];
  if (!gateOpen(3)) {
    el.innerHTML = `<div class="stack">${slate(3, "Frames, then motion", "Production", cells)}${lockout(3, S.gates.g1 ? 2 : 1)}</div>`;
    return;
  }
  const lite = flowModels().find((m) => m.id === "veo-3.1-lite");
  const fast = flowModels().find((m) => m.id === "veo-3.1-fast");
  el.innerHTML = `<div class="stack">
    ${slate(3, "Frames, then motion", "Production", cells)}
    ${card(["frames", "director"], "<b>03A</b> · How the free allowance is spent", `
      <p class="lede">Frames are free and unlimited on the local GPU. Only Pass 2, the motion, spends Flow credits, and only after both frames are locked. Everything made so far, with the credits each clip cost, is in the <a href="/library${TEAM ? `?team=${TEAM}` : ""}">library</a>; out of credits, reuse a clip from there.</p>
      ${f ? `${meter(0)}<p class="field-hint">${f.plan === "free" ? "Free Google account: " : ""}${f.daily_budget} credits a day buys ${lite ? Math.floor(f.daily_budget / lite.costs[8]) : "?"} Veo 3.1 Lite or ${fast ? Math.floor(f.daily_budget / fast.costs[8]) : "?"} Veo 3.1 Fast clips. The server refuses any clip that would go over.${f.configured ? "" : " Flow is not connected yet."}</p>` : '<p class="muted small">Unlock with the access code to see the budget.</p>'}
      <div class="field"><span class="field-label">Frames come from <em>every unlocked first and last frame</em></span>
        <div class="choice" role="group" aria-label="Default frame source" style="grid-template-columns:1fr 1fr">
          <button data-act="frame-source" data-v="local" aria-pressed="${S.frame_source === "local"}"><small>Unlimited · this GPU</small>Local FLUX.2 klein</button>
          <button data-act="frame-source" data-v="hand" aria-pressed="${S.frame_source === "hand"}"><small>Free · you click in Flow</small>Flow by hand</button>
          <button data-act="frame-source" data-v="gemini" aria-pressed="${S.frame_source === "gemini"}"><small>About 3 cents · your API key</small>Gemini API</button>
          <button data-act="frame-source" data-v="flow" aria-pressed="${S.frame_source === "flow"}"><small>0 credits · paid useapi.net bridge</small>Flow via useapi</button></div>
        <span class="field-hint">Flow by hand: the app hands you the prompt and reference, you make the frame in your own Flow tab with Nano Banana, and bring the download back. Last frames use the locked first frame as their reference either way. Each shot can still pick its own source.</span></div>
      <label class="field"><span class="field-label">Flow image model <em>when a frame source is Flow image</em></span>
        <select data-bind="flow_frames">${(f?.image_models || ["nano-banana-2-lite"]).map((m) => `<option ${S.flow_frames === m ? "selected" : ""}>${m}</option>`).join("")}</select></label>`)}
    ${S.shots.map(workCard).join("")}
    ${card(["editsound", "director"], "<b>03B</b> · Voiceover scratch", `
      <p class="lede">Record a guide read on this phone. It stays a scratch: the audit asks for a human take.</p>
      <div class="row">${vo.recorder ? `<button class="btn primary" data-act="vo-stop">■ Stop <span class="num" id="vo-time">0s</span></button>` : `<button class="btn danger" data-act="vo-rec">● Record scratch</button>`}</div>
      ${vo.url || S.vo_media ? `<audio src="${vo.url || mediaUrl(S.vo_media)}" controls style="width:100%"></audio>${S.vo_media ? `<p class="field-hint">Saved on the server for the team and the cut.</p>` : ""}` : ""}
      ${field("Read", "vo_note", { area: true, rows: 2, placeholder: "The lines as read, or a note for the edit" })}`)}
    ${card(["auditor", "frames", "editsound"], `<b>03C</b> · provenance.csv · ${S.provenance.length} rows`, `
      ${provTable()}
      <form class="stack" data-form="row">
        <div class="grid-2"><input name="asset_id" placeholder="asset_id, e.g. cut.mp4" aria-label="asset_id" required>
          <input name="tool" placeholder="Tool, e.g. Kdenlive 25.08" aria-label="tool_or_model" required></div>
        <div class="grid-2"><select name="stage" aria-label="stage">${["edit", "previs", "vo", "music", "grade", "captions", "other"].map((s) => `<option>${s}</option>`).join("")}</select>
          <input name="note" placeholder="Input or note" aria-label="prompt_or_input"></div>
        <button class="btn small" type="submit">Add row</button></form>`)}
    ${seal(3, "Gate 03 · director signs picture lock")}
  </div>`;
}

// ------------------------------------------------------------------ gate 4

function renderGate4() {
  const el = $("#gate-4");
  const mtr = auditMetrics();
  const cells = [["Score", `${mtr.passed} of 7`], ["Slop risk", `${mtr.risk}%`], ["Release", mtr.release ? "Ready" : "Blocked"]];
  if (!gateOpen(4)) {
    el.innerHTML = `<div class="stack">${slate(4, "Seven checks", "Anti-slop audit", cells)}${lockout(4, !S.gates.g1 ? 1 : !S.gates.g2 ? 2 : 3)}</div>`;
    return;
  }
  el.innerHTML = `<div class="stack">
    ${slate(4, "Seven checks", "Anti-slop audit", cells)}
    <div class="score" id="score" aria-live="polite"></div>
    ${cutCard()}
    ${card(["auditor"], "<b>04A</b> · Auditor", `<div class="grid-2">${field("Auditor's name", "audit.auditor")}${field("Cut reviewed", "audit.cut", { mono: true })}</div>`)}
    ${CHECKS.map((c) => {
      const r = S.audit.checks[c.id] || {};
      const sigBlock = c.id === "signature";
      return `<div class="check ${r.result === "Pass" ? "pass" : r.result === "Fail" ? "fail" : ""}" data-roles="${sigBlock ? "director" : "auditor"}">
        <div class="check-head"><span class="shot-num">${pad(c.n)}</span><h3>${h(c.name)}</h3>${c.gate ? '<span class="badge cost">Non-negotiable</span>' : ""}
          <div class="verdict" role="group" aria-label="${h(c.name)} result">${["Pass", "Fail"].map((v) => `<button data-act="verdict" data-c="${c.id}" data-v="${v}" aria-pressed="${r.result === v}" ${sigBlock && v === "Pass" && !S.audit.signature ? "disabled" : ""}>${v}</button>`).join("")}</div></div>
        <p class="small muted">${h(c.ask)}</p>
        <div class="machine" data-machine="${c.id}"></div>
        ${c.id === "intent" ? `<button class="btn small" data-act="check-intent" ${server.authed ? "" : "disabled"}>Read the shots against the exclusions with ${h(llmModel())}</button>${S.audit.intent_llm ? `<div class="machine">${h(S.audit.intent_llm)}</div>` : ""}` : ""}
        ${sigBlock ? field("Director signature <em>a named human who reviewed, changed and approved it</em>", "audit.signature", { placeholder: "Full name" }) : ""}
        ${field("Evidence", `audit.checks.${c.id}.evidence`, { area: true, rows: 2, placeholder: "One line: what you looked at" })}
      </div>`;
    }).join("")}
    ${card(["auditor", "director"], "<b>04B</b> · What broke and how it was caught", field("Notes", "audit.notes", { area: true, rows: 4, placeholder: "Writer crew: …\nPrevis crew: …\nFrames crew: …\nEdit and Sound crew: …" }))}
    <div id="release"></div>
  </div>`;
}

function cutSegments() {
  return S.shots.map((s) => ({
    media: s.motion.locked && s.motion.pick ? s.motion.pick : s.first.locked ? s.first.pick : null,
    duration: Number(s.duration_sec) || 5,
    caption: s.voiceover_line,
  }));
}

function cutCard() {
  const segs = cutSegments();
  const missing = segs.map((x, k) => (x.media ? null : k + 1)).filter(Boolean);
  const job = Object.entries(S.jobs || {}).find(([, j]) => j.slot === "cut");
  const latest = (S.cuts || [])[0];
  const qc = latest?.qc;
  const total = segs.reduce((n, x) => n + x.duration, 0);
  return card(["editsound", "director", "auditor"], "<b>04A</b> · Render the cut", `
    <p class="lede">Every shot in order: its locked motion take trimmed to the shot's length, or its first frame held as a still. Captions from the voiceover lines, and your voiceover scratch under it, loudness-matched. Rendered on this machine; ${S.shots.length} shots, ${total} seconds.</p>
    <label class="row"><input type="checkbox" data-bind="render.burn" ${S.render?.burn !== false ? "checked" : ""} style="width:24px;height:24px"><span class="small">Burn in captions</span></label>
    <label class="row"><input type="checkbox" data-bind="render.vo" ${S.render?.vo !== false ? "checked" : ""} ${S.vo_media ? "" : "disabled"} style="width:24px;height:24px"><span class="small">${S.vo_media ? "Use the voiceover scratch" : "No voiceover scratch yet (record one in Gate 03)"}</span></label>
    ${missing.length ? `<p class="notice warn">Lock a first frame for shot ${missing.join(", ")} first.</p>` : ""}
    <button class="btn primary" data-act="render-cut" ${missing.length || job || !server.authed ? "disabled" : ""}>${latest ? "Render a new version" : "Render the cut"}</button>
    ${job ? `<p class="notice warn" aria-live="polite">${h(job[1].note || "Waiting in the render queue")} · <a href="/queue">queue</a></p>` : ""}
    ${S.cut_error ? `<p class="notice bad">${h(S.cut_error)}</p>` : ""}
    ${latest ? `<div class="picked"><video src="${mediaUrl(latest.media)}" controls playsinline preload="metadata" aria-label="The rendered cut"></video>
      <p class="small muted">Version ${(S.cuts || []).length} · ${new Date(latest.created).toLocaleString()} · ${h(latest.prompt || "")}</p>
      ${qc ? `<div class="machine"><b>Kit QC (qc_check.py): ${qc.passed ? "pass" : "fail"}</b><br>${qc.checks.map((c) => `${c.result === "pass" ? "✓" : "✕"} ${h(c.check)}: ${h(c.measured)} (${h(c.expected)})`).join("<br>")}</div>` : '<p class="field-hint">No QC: a custom pitch has no project bible to check against.</p>'}
      <a class="btn small ghost" href="${mediaUrl(latest.media)}?download=1">Download cut.mp4</a></div>` : ""}`);
}

function refreshAudit() {
  if (!gateOpen(4)) return;
  if (!S.audit.signature.trim() && S.audit.checks.signature?.result === "Pass") {
    S.audit.checks.signature.result = null;
    save();
    renderGate4();
  }
  const mtr = auditMetrics();
  const score = $("#score");
  if (score) {
    score.innerHTML = `<div><span class="tag muted">Passed</span><span class="big" style="color:${mtr.passed === 7 ? "var(--green-text)" : "var(--text)"}">${mtr.passed}/7</span></div>
      <div><span class="tag muted">Slop risk</span><span class="big" style="color:${mtr.risk === 0 ? "var(--green-text)" : mtr.risk > 40 ? "var(--red-text)" : "var(--amber)"}">${mtr.risk}%</span><span class="small muted">checks not yet passed</span></div>
      <div><span class="tag muted">Human signature</span><span class="tag" style="color:${S.audit.checks.signature?.result === "Pass" ? "var(--green-text)" : "var(--red-text)"}">${S.audit.checks.signature?.result === "Pass" ? "✓ Signed" : "✕ Not signed: release locked"}</span></div>`;
  }
  const sigPass = $('[data-act="verdict"][data-c="signature"][data-v="Pass"]');
  if (sigPass) sigPass.disabled = !S.audit.signature.trim();
  for (const c of CHECKS) {
    const m = $(`[data-machine="${c.id}"]`);
    if (m) m.innerHTML = `<b>Machine:</b> ${h(mtr.machine[c.id])}`;
  }
  const rel = $("#release");
  if (rel) {
    const missing = CHECKS.filter((c) => S.audit.checks[c.id]?.result !== "Pass").map((c) => c.name);
    rel.innerHTML = `<div class="seal ${mtr.release ? "signed" : "blocked"}">
      <div class="seal-head"><span class="tag">Release</span><span class="seal-state">${mtr.release ? "Ready to release" : "Release locked"}</span></div>
      ${mtr.release ? `<p class="small">All seven checks pass and ${h(S.audit.signature)} signed. The pack is marked for release.</p>`
        : `<ul class="blockers">${!mtr.gatesOk ? "<li>Intent and Human signature must both pass.</li>" : ""}${missing.length ? `<li>Not passed yet: ${h(missing.join(", "))}. Release needs 7 of 7.</li>` : ""}</ul>`}
      <button class="btn ${mtr.release ? "go" : ""} block" data-act="pack">${mtr.release ? "Open the release pack" : "Open the draft pack"}</button></div>`;
  }
}

// ------------------------------------------------------------------ rail and refresh

function gateProgress(n) {
  const b = S.brief;
  if (n === 1) {
    const parts = [b.project_title, b.client, b.target_audience, b.core_feeling, b.call_to_action, b.key_message].filter((x) => x.trim().length >= 3).length + Math.min(3, b.exclusions.length);
    return S.gates.g1 ? 1 : parts / 9;
  }
  if (n === 2) return S.gates.g2 ? 1 : S.shots.filter((s) => s.locked).length / Math.max(1, S.shots.length);
  if (n === 3) return S.gates.g3 ? 1 : S.shots.reduce((a, s) => a + (s.first.locked ? 0.5 : 0) + (s.motion.locked || s.motion.still ? 0.5 : 0), 0) / Math.max(1, S.shots.length);
  return auditMetrics().passed / 7;
}

let currentGate = 1;
function renderRail() {
  const names = ["Brief", "Previs", "Prod", "Audit"];
  $("#rail").innerHTML = names.map((nm, i) => {
    const n = i + 1;
    const pass = n < 4 ? !!S.gates[`g${n}`] : auditMetrics().release;
    const st = !gateOpen(n) ? "is-locked" : pass ? "is-pass" : "";
    return `<a href="#gate-${n}" class="${st}" ${currentGate === n ? 'aria-current="step"' : ""} aria-label="Gate ${n}, ${nm}, ${st === "is-locked" ? "locked" : pass ? "passed" : "open"}">
      <span class="rail-top"><span>G0${n}</span><span class="rail-dot ${st}"></span></span>
      <span class="rail-name">${nm}</span>
      <span class="rail-prog"><span style="width:${Math.round(100 * gateProgress(n))}%"></span></span></a>`;
  }).join("");
}

function refreshLights() {
  const gpu = $("#light-gpu");
  const flow = $("#light-flow");
  const loc = server.status?.local;
  gpu.className = `light ${!server.reachable ? "off" : !loc ? "" : loc.ollama && loc.comfyui ? "on" : loc.ollama || loc.comfyui ? "warn" : "off"}`;
  gpu.title = loc ? `Ollama ${loc.ollama ? "up" : "down"}, ComfyUI ${loc.comfyui ? "up" : "down"}` : "Local GPU";
  flow.className = `light ${server.status?.flow?.configured ? "on" : server.authed ? "warn" : ""}`;
}

function refreshRoles() {
  document.body.dataset.role = S.role;
  $$(".role").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.id === S.role)));
  $$("[data-roles]").forEach((el) => {
    const mine = el.dataset.roles.split(" ").includes(S.role);
    if (el.classList.contains("card") || el.classList.contains("shot") || el.classList.contains("check")) el.classList.toggle("mine", mine);
  });
  $$(".badge").forEach((b) => {
    const r = ROLES.find((x) => x.label === b.textContent);
    if (r) b.classList.toggle("me", r.id === S.role);
  });
}

const lastOpen = {};
function refresh() {
  for (const n of [1, 2, 3]) {
    const el = $(`#seal-${n}`);
    if (el && !el.contains(document.activeElement)) el.innerHTML = sealDynamic(n);
  }
  // Re-render a gate whose lock state changed.
  for (const n of [2, 3, 4]) {
    const open = gateOpen(n);
    const changed = lastOpen[n] !== undefined && lastOpen[n] !== open;
    lastOpen[n] = open;
    if (changed) {
      [renderGate1, renderGate2, renderGate3, renderGate4][n - 1]();
      if (n < 4) { const el = $(`#seal-${n}`); if (el) el.innerHTML = sealDynamic(n); }
    }
  }
  refreshAudit();
  renderRail();
  refreshLights();
  refreshRoles();
}

function renderGate(n) {
  [renderGate1, renderGate2, renderGate3, renderGate4][n - 1]();
  refresh();
}
function renderAll() {
  banner();
  [1, 2, 3, 4].forEach((n) => [renderGate1, renderGate2, renderGate3, renderGate4][n - 1]());
  [2, 3, 4].forEach((n) => { lastOpen[n] = gateOpen(n); });
  refresh();
}

// ------------------------------------------------------------------ gate sign-off

function sign(n, on) {
  const key = `g${n}`;
  if (on) {
    if (blockers(n).length) return;
    S.gates[key] = { decision: "Approve", director: S.director.trim(), at: nowIso() };
    if (n === 1) upsertRow({ asset_id: "brief.json", stage: "brief", tool_or_model: S.suggest?.used ? `Director, with an ollama/${S.suggest.model} draft` : "Director (human)", seed: "", prompt_or_input: "Director's three answers and exclusions", status: "APPROVED", human_approver: S.director.trim() });
    if (n === 2) upsertRow({ asset_id: "shots.json", stage: "shot_list", tool_or_model: S.shotsDrafted ? `Previs crew, with an ollama/${S.shotsDrafted} draft` : "Previs crew (human)", seed: "", prompt_or_input: "brief.json", status: "APPROVED", human_approver: S.director.trim() });
    buzz([20, 40, 20]);
    toast(`Gate 0${n} signed by ${S.director.trim()}.`, "good");
  } else {
    S.gates[key] = null;
    buzz(15);
    toast(`Gate 0${n} reopened.`);
  }
  save();
  renderGate(n);
}

// Editing a signed gate reopens it: the signature covered the old version.
function touchGate(el) {
  const sec = el.closest(".gate");
  if (!sec) return;
  const n = Number(sec.id.slice(5));
  if (n < 4 && S.gates[`g${n}`] && !el.closest(`#seal-${n}`) && el.dataset.bind !== "director" && !el.dataset.bind?.match(/\.(first|last|motion)\.|^vo_note|^flow_frames|^brief\.idea/)) {
    S.gates[`g${n}`] = null;
    toast(`Gate 0${n} reopened: it changed after sign-off.`);
    setTimeout(() => refresh(), 0);
  }
}

// Picture lock covers the frames and takes as they were when it was signed.
function reopen3() {
  if (S.gates.g3) { S.gates.g3 = null; toast("Gate 03 reopened: the picture changed after sign-off."); }
}

// ------------------------------------------------------------------ jobs

function jobLabel(shot, what) {
  return { project: S.brief.project_title || S.brief.client || "Untitled", label: `${S.brief.project_title || "Untitled"} · shot ${shotNo(shot)} ${shot.label} · ${what}` };
}

async function startFrame(shot, slot) {
  const t = shot[slot];
  const prompt = (t.prompt || (slot === "first" ? shot.visual_prompt : "")).trim();
  if (prompt.length < 5) return toast(slot === "last" ? "Say what has changed by the last frame." : "Write a frame prompt first.", "bad");
  const reference = slot === "last" ? shot.first.pick : (t.useRef && shot.ref ? shot.ref : null);
  const body = { prompt, reference, frame: slot, shot: shot.id, team: TEAM, ...jobLabel(shot, `${slot} frame`) };
  t.error = null;
  try {
    const { job } = t.source === "flow" ? await api.post("/api/flow/image", { ...body, model: S.flow_frames })
      : t.source === "gemini" ? await api.post("/api/gemini/image", body)
      : await api.post("/api/local/keyframe", body);
    S.jobs[job.id] = { shot: shot.id, slot, note: "Queued" };
    save();
    buzz();
    renderGate(3);
    poll();
  } catch (e) {
    toast(e.message, "bad");
  }
}

async function startMotion(shot) {
  const m = shot.motion;
  const prompt = (m.prompt || `${shot.camera_move}. ${shot.action_description}`).trim();
  const model = flowModels().find((x) => x.id === m.model) || flowModels()[0];
  if (!model) return toast("Flow is not connected.", "bad");
  const duration = clipDuration(shot, model);
  const cost = model.costs[duration];
  if (!confirm(`Render ${model.label}, ${duration}s, for ${cost} Flow credits? ${flowLeft() - cost} will be left today.`)) return;
  m.error = null;
  try {
    const { job } = await api.post("/api/flow/video", { prompt, model: model.id, duration, start: shot.first.pick,
      end: shot.last.locked ? shot.last.pick : null, shot: shot.id, team: TEAM, ...jobLabel(shot, "motion") });
    S.jobs[job.id] = { shot: shot.id, slot: "motion", note: "Queued" };
    if (!m.prompt) m.prompt = prompt;
    save();
    buzz([15, 30, 15]);
    await loadStatus();
    renderGate(3);
    poll();
  } catch (e) {
    toast(e.message, "bad");
  }
}

async function renderCut(btn) {
  btn?.classList.add("busy");
  try {
    const { job } = await api.post("/api/render", {
      segments: cutSegments(), burn: S.render?.burn !== false, vo: S.render?.vo !== false ? S.vo_media : null,
      bible: PRESETS[S.brief.preset]?.bible || "", team: TEAM,
      project: S.brief.project_title || "Untitled", label: `${S.brief.project_title || "Untitled"} · cut v${(S.cuts || []).length + 1}`,
    });
    S.jobs[job.id] = { shot: null, slot: "cut", note: "Waiting in the render queue" };
    S.cut_error = null;
    save();
    renderGate(4);
    poll();
  } catch (e) {
    toast(e.message, "bad");
  } finally {
    btn?.classList.remove("busy");
  }
}

async function startLocalMotion(shot) {
  const m = shot.motion;
  const engine = motionEngine(shot);
  const body = { engine, start: shot.first.pick, end: shot.last.locked ? shot.last.pick : null, duration: shot.duration_sec,
    move: m.move || shot.camera_move, prompt: (m.prompt || `${shot.camera_move}. ${shot.action_description}`).trim(),
    shot: shot.id, team: TEAM, ...jobLabel(shot, `motion (${engine})`) };
  m.error = null;
  try {
    const { job } = await api.post("/api/local/motion", body);
    S.jobs[job.id] = { shot: shot.id, slot: "motion", note: "Queued" };
    if (!m.prompt && engine !== "camera") m.prompt = body.prompt;
    save();
    buzz([15, 30, 15]);
    renderGate(3);
    poll();
  } catch (e) {
    toast(e.message, "bad");
  }
}

let polling = false;
async function poll() {
  if (polling) return;
  polling = true;
  while (Object.keys(S.jobs).length && server.authed) {
    for (const [id, j] of Object.entries(S.jobs)) {
      let res;
      try {
        res = await api.get(`/api/jobs/${id}`);
      } catch (e) {
        if (e.status === 404) { delete S.jobs[id]; save(); }
        continue;
      }
      const job = res.job;
      if (j.slot === "cut") {
        if (job.status === "done") {
          delete S.jobs[id];
          const meta = res.media[0];
          if (meta && !(S.cuts || []).some((c) => c.media === meta.name)) {
            S.cuts = [{ media: meta.name, qc: meta.qc || null, srt: meta.srt || "", created: meta.created, prompt: meta.prompt }, ...(S.cuts || [])];
            upsertRow({ asset_id: "cut.mp4", stage: "edit", tool_or_model: meta.tool_or_model, seed: "",
              prompt_or_input: `${meta.prompt}; shots: ${pickedAssets().filter((x) => x.dir !== "previs").map((x) => x.asset_id).join(", ")}`,
              status: "PENDING_REVIEW", media: meta.name });
          }
          S.cut_error = null;
          buzz([10, 30, 10]);
          toast("The cut is rendered.", "good");
        } else if (job.status === "failed" || job.status === "cancelled") {
          delete S.jobs[id];
          S.cut_error = job.error;
          toast(job.error || "The render failed.", "bad");
        } else {
          j.note = job.note;
        }
        save();
        if (!$("#gate-4").contains(document.activeElement)) renderGate(4);
        continue;
      }
      const shot = shotById(j.shot);
      if (!shot) { delete S.jobs[id]; continue; }
      if (job.status === "done") {
        delete S.jobs[id];
        for (const meta of res.media.filter(Boolean)) {
          if (shot[j.slot].takes.includes(meta.name)) continue;  // a teammate's phone got there first
          shot[j.slot].takes.push(meta.name);
          if (!shot[j.slot].pick) shot[j.slot].pick = meta.name;
          logTake(shot, j.slot, meta);
        }
        buzz([10, 30, 10]);
        toast(`Shot ${shotNo(shot)}: new ${j.slot === "motion" ? "motion take" : `${j.slot} frame`} ready.`, "good");
        save();
        if (j.slot === "motion") loadStatus();
        renderGate(3);
      } else if (job.status === "failed" || job.status === "cancelled") {
        delete S.jobs[id];
        shot[j.slot].error = job.error;
        toast(`Shot ${shotNo(shot)}: ${job.error}`, "bad");
        save();
        if (j.slot === "motion") await loadStatus();
        renderGate(3);
      } else if (job.note !== j.note) {
        j.note = job.note;
        const el = $(`#gate-3`);
        if (el && !el.contains(document.activeElement)) renderGate(3);
      }
    }
    await new Promise((r) => setTimeout(r, 2000));
  }
  polling = false;
}

// ------------------------------------------------------------------ local model helpers

function factsText() {
  return S.brief.facts.map(([id, t]) => `${id}: ${t}`).join("\n") || "(no facts yet)";
}

async function chat(system, prompt, schema, btn) {
  btn?.classList.add("busy");
  try {
    return await api.post("/api/local/chat", { model: llmModel(), system, prompt, schema });
  } finally {
    btn?.classList.remove("busy");
  }
}

async function draftBrief(btn) {
  const b = S.brief;
  const schema = { type: "object", required: ["target_audience", "core_feeling", "call_to_action", "key_message", "exclusions"],
    properties: { target_audience: { type: "string" }, core_feeling: { type: "string" }, call_to_action: { type: "string" },
      key_message: { type: "string" }, exclusions: { type: "array", items: { type: "string" } }, references: { type: "array", items: { type: "string" } } } };
  try {
    const out = await chat(
      "You help the Writer crew of a short-film workshop draft a 30-second spot's brief. You propose; a human director decides. Use only the facts given. Plain, concrete words: no hype, no superlatives, no invented numbers. Exclusions start with 'No' and name something specific this spot will never do.",
      `Client: ${b.client}\nThe ask: ${PRESETS[b.preset].ask}\nTone: ${b.tone.join(", ")}\nFacts you may use:\n${factsText()}\n\nRough idea from the crew: ${b.idea || "(none: propose one)"}\n\nDraft: target_audience (one specific person), core_feeling (one feeling), call_to_action (one action), key_message (one sentence, facts only), exactly three exclusions, two references described in words.`,
      schema, btn);
    const j = out.json;
    S.suggest = { model: out.model, seconds: out.seconds, used: S.suggest?.used || false,
      fields: { target_audience: j.target_audience, core_feeling: j.core_feeling, call_to_action: j.call_to_action, key_message: j.key_message, exclusions: (j.exclusions || []).slice(0, 3), references: j.references || [] } };
    save();
    renderGate(1);
  } catch (e) { toast(e.message, "bad"); }
}

async function draftShots(btn) {
  const b = S.brief;
  const p = PRESETS[b.preset];
  const open = S.shots.filter((s) => !s.locked);
  if (!open.length) return toast("Every shot is locked. Unlock one to redraft it.");
  const each = Math.round((Number(b.runtime_sec) - S.shots.filter((s) => s.locked).reduce((n, s) => n + Number(s.duration_sec), 0)) / open.length) || 5;
  const shotSchema = { type: "object", required: ["framing", "lens_mm", "camera_move", "location_id", "action_description", "visual_prompt", "voiceover_line", "source_ids"],
    properties: { framing: { type: "string", enum: FRAMINGS }, lens_mm: { type: "integer" }, camera_move: { type: "string", enum: MOVES },
      location_id: { type: "string", enum: p.locations.map((l) => l[0]) }, characters: { type: "array", items: { type: "string", enum: p.characters.map((c) => c[0]).concat(["none"]) } },
      action_description: { type: "string" }, visual_prompt: { type: "string" }, voiceover_line: { type: "string" }, source_ids: { type: "array", items: { type: "string" } } } };
  try {
    const out = await chat(
      "You are the shot_breakdown agent in a film workshop. Write shots a director will review. Visual prompts describe one frame concretely: subject, setting, light, lens feel. Never ask for text, logos or signs in frame. voiceover_line holds only the words a narrator speaks, in your own phrasing: never fact ids. It may only state the given facts, and source_ids lists the ids of the facts it states. No hype words.",
      `Brief:\nFor: ${b.target_audience}\nFeel: ${b.core_feeling}\nDo next: ${b.call_to_action}\nKey message: ${b.key_message}\nNever: ${b.exclusions.join("; ")}\nTone: ${b.tone.join(", ")}\nFacts:\n${factsText()}\nLocations: ${p.locations.map((l) => `${l[0]} (${l[1]})`).join(", ")}\nCharacters: ${p.characters.map((c) => `${c[0]} (${c[1]})`).join(", ") || "none"}\n\nWrite ${open.length} shots in order, each about ${each} seconds: ${open.map((s) => `"${s.label}" (${s.framing}, ${s.camera_move})`).join(", ")}.`,
      { type: "object", required: ["shots"], properties: { shots: { type: "array", items: shotSchema } } }, btn);
    const drafts = out.json.shots || [];
    open.forEach((s, k) => {
      const d = drafts[k];
      if (!d) return;
      // Small models like to paste "SRC-004: ..." into the spoken line: move
      // the ids to source_ids and keep only the words.
      const named = String(d.voiceover_line || "").match(/SRC-\d+/g) || [];
      d.voiceover_line = String(d.voiceover_line || "").replace(/\(?SRC-\d+\)?\s*[:,-]?\s*/g, "").trim();
      if (named.length) d.source_ids = named;
      Object.assign(s, {
        framing: FRAMINGS.includes(d.framing) ? d.framing : s.framing,
        lens_mm: LENSES.reduce((a, l) => (Math.abs(l - d.lens_mm) < Math.abs(a - d.lens_mm) ? l : a), s.lens_mm),
        camera_move: MOVES.includes(d.camera_move) ? d.camera_move : s.camera_move,
        location_id: p.locations.some((l) => l[0] === d.location_id) ? d.location_id : s.location_id,
        characters: (d.characters || []).filter((c) => p.characters.some((x) => x[0] === c)),
        action_description: d.action_description || "", visual_prompt: d.visual_prompt || "", voiceover_line: d.voiceover_line || "",
        source_ids: (d.source_ids || []).filter((id) => S.brief.facts.some((f) => f[0] === id)), duration_sec: each,
      });
    });
    S.shotsDrafted = out.model;
    save();
    renderGate(2);
    toast(`${out.model} drafted ${Math.min(drafts.length, open.length)} shots in ${out.seconds}s. Read every one before you lock it.`, "good");
  } catch (e) { toast(e.message, "bad"); }
}

async function draftAction(shot, btn) {
  try {
    const out = await chat(
      "You write the action prompt for an image-to-video model that animates from a first frame to a last frame. Describe only motion: the camera move, what moves in frame, and pacing, in one or two plain sentences. Introduce no new people, objects or text.",
      `Camera move: ${shot.camera_move}\nLens: ${shot.lens_mm}mm, ${shot.framing}\nAction: ${shot.action_description}\nFirst frame: ${shot.first.prompt || shot.visual_prompt}\nLast frame: ${shot.last.skip ? "(none: the model decides)" : shot.last.prompt}\nLength: ${shot.duration_sec} seconds`,
      { type: "object", required: ["action"], properties: { action: { type: "string" } } }, btn);
    shot.motion.prompt = out.json.action;
    save();
    renderGate(3);
  } catch (e) { toast(e.message, "bad"); }
}

async function checkIntent(btn) {
  try {
    const out = await chat(
      "You help a human auditor. Read each shot and list any place where it might break one of the exclusions or make a claim not in the facts. Quote the words. If nothing breaks, say so. You do not decide pass or fail.",
      `Exclusions:\n${S.brief.exclusions.map((e) => `- ${e}`).join("\n")}\nFacts:\n${factsText()}\n\nShots:\n${S.shots.map((s, i) => `Shot ${i + 1}: action "${s.action_description}" | visual "${s.visual_prompt}" | voiceover "${s.voiceover_line}" | motion "${s.motion.prompt}"`).join("\n")}`,
      { type: "object", required: ["findings"], properties: { findings: { type: "array", items: { type: "string" } } } }, btn);
    const f = out.json.findings || [];
    S.audit.intent_llm = `${out.model} (${out.seconds}s): ${f.length ? f.join(" · ") : "found nothing to flag."} The auditor decides.`;
    save();
    renderGate(4);
  } catch (e) { toast(e.message, "bad"); }
}

// ------------------------------------------------------------------ voiceover

async function voRecord() {
  if (!navigator.mediaDevices?.getUserMedia) return toast("This browser cannot record here. Recording needs HTTPS.", "bad");
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec = new MediaRecorder(stream);
    vo.chunks = [];
    rec.ondataavailable = (e) => e.data.size && vo.chunks.push(e.data);
    rec.onstop = async () => {
      const type = (rec.mimeType || "audio/webm").split(";")[0];
      vo.blob = new Blob(vo.chunks, { type });
      if (vo.url) URL.revokeObjectURL(vo.url);
      vo.url = URL.createObjectURL(vo.blob);
      stream.getTracks().forEach((t) => t.stop());
      renderGate(3);
      // Keep it on the server so the team and the render can use it.
      try {
        const { media } = await upload(vo.blob, { "X-Label": `${S.brief.project_title || "Untitled"} · voiceover scratch`, "X-Project": S.brief.project_title || "", "X-Prompt": S.vo_note || "" });
        S.vo_media = media.name;
        upsertRow({ asset_id: `vo_scratch.${media.name.split(".").pop()}`, stage: "vo", tool_or_model: "Phone microphone (human scratch read)", seed: "",
          prompt_or_input: S.vo_note || "Scratch read", status: "PENDING_REVIEW", media: media.name });
        toast("Voiceover scratch saved for the cut.", "good");
      } catch (e) {
        toast(`Kept on this phone only: ${e.message}`, "bad");
      }
      save();
      renderGate(3);
    };
    rec.start();
    vo.recorder = rec;
    vo.started = Date.now();
    vo.timer = setInterval(() => { const t = $("#vo-time"); if (t) t.textContent = `${Math.round((Date.now() - vo.started) / 1000)}s`; }, 500);
    buzz(20);
    renderGate(3);
  } catch (e) { toast(`Microphone: ${e.message}`, "bad"); }
}

function voStop() {
  clearInterval(vo.timer);
  vo.recorder?.stop();
  vo.recorder = null;
  buzz([15, 30]);
}

// ------------------------------------------------------------------ import a pack

function parseCsv(text) {
  const rows = [];
  let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') q = false; else cell += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cell); rows.push(row); row = []; cell = ""; }
    else cell += c;
  }
  if (cell || row.length) { row.push(cell); rows.push(row); }
  const [head, ...body] = rows.filter((r) => r.some((x) => x !== ""));
  return body.map((r) => Object.fromEntries(head.map((k, i) => [k, r[i] ?? ""])));
}

const TYPES = { png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", mp4: "video/mp4", webm: "audio/webm", m4a: "audio/mp4", ogg: "audio/ogg" };

async function restoreFile(zip, path, model = "", prompt = "") {
  const data = await zip.bytes(path);
  const ext = path.split(".").pop().toLowerCase();
  if (!data || !TYPES[ext]) return null;
  const { media } = await upload(new Blob([data], { type: TYPES[ext] }),
    { "X-Source": "restore", "X-Label": `${S.brief.project_title || "Imported"} · ${path}`, "X-Model": model, "X-Prompt": prompt });
  return media.name;
}

// An older pack, or one edited by hand: rebuild what the kit files describe.
async function rebuild(zip, find) {
  const st = fresh();
  const brief = JSON.parse(await zip.text(find("brief.json")) || "{}");
  const preset = Object.entries(PRESETS).find(([, p]) => p.client && p.client === brief.client)?.[0] || "custom";
  const p = PRESETS[preset];
  Object.assign(st.brief, { preset, client: brief.client || "", project_title: brief.project_title || "", target_audience: brief.target_audience || "",
    core_feeling: brief.core_feeling || "", call_to_action: brief.call_to_action || "", key_message: brief.key_message || "",
    runtime_sec: brief.runtime_sec || 30, tone: brief.tone || [], exclusions: brief.exclusions || [], references: (brief.references || []).join("\n") });
  const research = find("research_log.csv") && parseCsv(await zip.text(find("research_log.csv")));
  st.brief.facts = research ? research.map((r) => [r.source_id, r.claim]) : p.facts.map((f) => [...f]);
  const shots = JSON.parse(await zip.text(find("shots.json")) || '{"shots":[]}').shots || [];
  st.shots = shots.map((sh, i) => Object.assign(newShot(i, { label: `Shot ${i + 1}` }, preset), {
    framing: sh.framing, lens_mm: sh.lens_mm, duration_sec: sh.duration_sec, camera_move: sh.camera_move, location_id: sh.location_id,
    characters: sh.characters || [], action_description: sh.action_description || "", visual_prompt: sh.visual_prompt || "",
    voiceover_line: sh.voiceover_line || "", source_ids: sh.source_ids || [], locked: true }));
  if (find("provenance.csv")) st.provenance = parseCsv(await zip.text(find("provenance.csv")));
  const prov = Object.fromEntries(st.provenance.map((r) => [r.asset_id, r]));
  for (const path of zip.names) {
    const m = path.match(/(?:^|\/)shot_(\d+)_(first_frame|last_frame|motion|previs_photo)(?:_take\d+)?\.(png|jpe?g|mp4)$/);
    if (!m) continue;
    const shot = st.shots[Number(m[1]) - 1];
    if (!shot) continue;
    const stem = path.split("/").pop().replace(/\.[^.]+$/, "");
    const name = await restoreFile(zip, path, prov[stem]?.tool_or_model, prov[stem]?.prompt_or_input);
    if (!name) continue;
    if (m[2] === "previs_photo") { shot.ref = name; continue; }
    const slot = { first_frame: "first", last_frame: "last", motion: "motion" }[m[2]];
    shot[slot].takes.push(name);
    shot[slot].pick = name;
    shot[slot].locked = true;
    if (prov[stem]) prov[stem].media = name;
  }
  st.shots.forEach((s) => { if (!s.last.locked) s.last.skip = true; if (!s.motion.locked && s.first.locked) s.motion.still = true; });
  if (find("cut.mp4")) {
    const name = await restoreFile(zip, find("cut.mp4"), "ffmpeg (XPSR Director assemble)");
    if (name) st.cuts = [{ media: name, qc: JSON.parse(await zip.text(find("qc.json")) || "null"), srt: await zip.text(find("captions.srt")) || "", created: nowIso(), prompt: "Imported from a pack" }];
  }
  return st;
}

async function importPack(file, label) {
  label?.classList.add("busy");
  try {
    const zip = await readZip(file);
    const find = (n) => zip.names.find((x) => x === n || x.endsWith(`/${n}`));
    let next;
    const projFile = find("xpsr-director.json");
    if (projFile) {
      const proj = JSON.parse(await zip.text(projFile));
      if (proj.format !== "xpsr-director-project") throw new Error("xpsr-director.json is not a Director project.");
      let text = JSON.stringify(proj.state);
      // Media the server still has stays; anything missing comes back from the ZIP.
      for (const [path, name] of Object.entries(proj.media || {})) {
        const have = await fetch(mediaUrl(name), { method: "HEAD", credentials: "same-origin" }).then((r) => r.ok).catch(() => false);
        if (have) continue;
        const fresh_ = await restoreFile(zip, find(path) || path);
        if (fresh_) text = text.split(name).join(fresh_);
      }
      next = JSON.parse(text);
      // Takes that were not in the pack and are gone from the server are dropped.
      const names = new Set();
      text.replace(/[0-9a-f]{16}\.(png|jpg|mp4|webm|m4a|ogg)/g, (n) => { names.add(n); return n; });
      const alive = new Set();
      for (const n of names) {
        if (await fetch(mediaUrl(n), { method: "HEAD", credentials: "same-origin" }).then((r) => r.ok).catch(() => false)) alive.add(n);
      }
      for (const s of next.shots || []) {
        for (const slot of ["first", "last", "motion"]) {
          const t = s[slot];
          t.takes = (t.takes || []).filter((n) => alive.has(n));
          if (t.pick && !alive.has(t.pick)) { t.pick = null; t.locked = false; }
        }
        if (s.ref && !alive.has(s.ref)) s.ref = null;
      }
      next.cuts = (next.cuts || []).filter((c) => alive.has(c.media));
      if (next.vo_media && !alive.has(next.vo_media)) next.vo_media = null;
    } else if (find("brief.json")) {
      next = await rebuild(zip, find);
    } else {
      throw new Error("This ZIP has no xpsr-director.json or brief.json.");
    }
    next.jobs = {};
    if (TEAM) {
      await api.post(`/api/teams/${TEAM}/ops`, { ops: [{ p: "", v: next, force: true }] });
      team.synced = null;
      team.version = -1;
      S = normalize({ ...next, ...localOf(S) });
      cache();
      await pull();
    } else {
      S = normalize({ ...next, ...localOf(S) });
      save();
    }
    renderAll();
    toast(`Picked up "${S.brief.project_title || "the project"}" from the pack${projFile ? "" : " (rebuilt from the kit files: sign the gates again)"}.`, "good");
  } catch (e) {
    toast(`Could not import: ${e.message}`, "bad");
  } finally {
    label?.classList.remove("busy");
  }
}

// ------------------------------------------------------------------ sheets

function openSheet(html) {
  const el = $("#sheet");
  el.innerHTML = `<div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title">${html}</div>`;
  el.hidden = false;
  document.body.style.overflow = "hidden";
  setTimeout(() => $("#sheet [data-act=close]")?.focus(), 50);
}
function closeSheet() {
  $("#sheet").hidden = true;
  $("#sheet").innerHTML = "";
  document.body.style.overflow = "";
}

let packTab = "brief.md";
function openPack() {
  const mtr = auditMetrics();
  const files = textFiles(S, mtr);
  const cur = files.find((f) => f.name === packTab) || files[0];
  const media = pickedAssets();
  openSheet(`<div class="sheet-head"><div><span class="tag slate-kicker">For the starter kit</span><h2 id="sheet-title">${mtr.release ? "Release pack" : "Draft pack"}</h2></div>
      <button class="btn small" data-act="close">Close</button></div>
    <div class="sheet-body">
      <p class="notice ${mtr.release ? "good" : "warn"}">${mtr.release ? `All seven checks pass; signed by ${h(S.audit.signature)}.` : "Draft: the audit is not at 7 of 7 with a human signature, so audit.md says so. Export it to keep working in the kit."}</p>
      <div class="tabs" role="tablist">${files.map((f) => `<button role="tab" aria-selected="${f.name === cur.name}" data-act="tab" data-name="${f.name}">${f.name}</button>`).join("")}</div>
      <pre class="preview" tabindex="0" aria-label="${h(cur.name)} preview">${h(cur.data)}</pre>
      ${(S.cuts || [])[0] ? `<video src="${mediaUrl(S.cuts[0].media)}" controls playsinline preload="metadata" style="width:100%;background:#000" aria-label="The cut in this pack"></video>`
        : `<p class="notice warn">No cut rendered yet. <button class="linkish" data-act="close-to-cut">Render the cut</button> in Gate 04 to put cut.mp4 in the pack.</p>`}
      <label class="row"><input type="checkbox" id="with-media" checked ${server.authed ? "" : "disabled"} style="width:24px;height:24px"><span class="small">Include ${(S.cuts || [])[0] ? "cut.mp4, captions.srt, qc.json, " : ""}${media.length} picked frame${media.length === 1 ? "" : "s"} and clip${media.length === 1 ? "" : "s"}${S.vo_media || vo.blob ? " and the voiceover scratch" : ""}</span></label>
      <p class="field-hint">Unzip into your project folder (for example <span class="mono">my-project/</span>) and carry on with the kit's pipelines.</p>
    </div>
    <div class="sheet-foot"><button class="btn" data-act="copy-pack">Copy as text</button><button class="btn ${mtr.release ? "go" : "primary"}" data-act="zip">Download .zip</button></div>`);
}

async function downloadZip(btn) {
  const mtr = auditMetrics();
  const files = textFiles(S, mtr);
  btn.classList.add("busy");
  try {
    const mediaMap = {};
    if ($("#with-media")?.checked) {
      for (const a of pickedAssets()) {
        const res = await fetch(mediaUrl(a.media), { credentials: "same-origin" });
        if (!res.ok) continue;
        const path = `${a.dir}/${a.asset_id}.${a.media.split(".").pop()}`;
        files.push({ name: path, data: new Uint8Array(await res.arrayBuffer()) });
        mediaMap[path] = a.media;
      }
      const grab = async (name) => { const r = await fetch(mediaUrl(name), { credentials: "same-origin" }); return r.ok ? new Uint8Array(await r.arrayBuffer()) : null; };
      if (S.vo_media) { const d = await grab(S.vo_media); if (d) files.push({ name: `audio/vo_scratch.${S.vo_media.split(".").pop()}`, data: d }); }
      else if (vo.blob) files.push({ name: "audio/vo_scratch.webm", data: new Uint8Array(await vo.blob.arrayBuffer()) });
      if (S.vo_media) mediaMap[`audio/vo_scratch.${S.vo_media.split(".").pop()}`] = S.vo_media;
      const cut = (S.cuts || [])[0];
      if (cut) {
        const d = await grab(cut.media);
        if (d) { files.push({ name: "cut.mp4", data: d }); mediaMap["cut.mp4"] = cut.media; }
        if (cut.srt) files.push({ name: "captions.srt", data: cut.srt.replace(/\n/g, "\r\n") });
        if (cut.qc) files.push({ name: "qc.json", data: JSON.stringify({ ...cut.qc, video: "cut.mp4" }, null, 2) + "\n" });
      }
    }
    // Everything needed to pick the project up again with Import a pack.
    const project = { ...sharedOf(S), jobs: {} };
    files.push({ name: "xpsr-director.json", data: JSON.stringify({ format: "xpsr-director-project", version: 1,
      exported: nowIso(), team: TEAM, media: mediaMap, state: project }, null, 1) + "\n" });
    const slug = (S.brief.project_title || "project").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
    const url = URL.createObjectURL(makeZip(files));
    const a = document.createElement("a");
    a.href = url;
    a.download = `xpsr-${slug}-${mtr.release ? "release" : "draft"}-${new Date().toISOString().slice(0, 10)}.zip`;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    buzz([20, 40, 20]);
    toast(`Packed ${files.length} files.`, "good");
  } catch (e) {
    toast(`Could not pack: ${e.message}`, "bad");
  } finally {
    btn.classList.remove("busy");
  }
}

async function openAccounts() {
  const f = server.status?.flow;
  const models = server.status?.local?.models || [];
  if (!server.authed) {
    openSheet(`<div class="sheet-head"><h2 id="sheet-title">Accounts</h2><button class="btn small" data-act="close">Close</button></div>
      <div class="sheet-body"><p class="notice warn">Enter the access code at the top of the page first.</p></div>`);
    return;
  }
  openSheet(`<div class="sheet-head"><div><span class="tag slate-kicker">Engines</span><h2 id="sheet-title">Accounts and models</h2></div><button class="btn small" data-act="close">Close</button></div>
    <div class="sheet-body">
      <div class="card"><div class="card-head"><span class="card-title"><b>Local writing model</b> · Ollama</span></div>
        <select data-bind="llm_model" aria-label="Local writing model">${models.map((m) => `<option ${m === llmModel() ? "selected" : ""}>${h(m)}</option>`).join("")}</select>
        <p class="field-hint">llama3.2:3b answers in seconds on this card; glm-4.7-flash writes better and takes about a minute.</p></div>
      ${(() => { const g = server.status?.gemini || {}; return `<div class="card"><div class="card-head"><span class="card-title"><b>Gemini API</b> · Nano Banana with your key</span><span class="badge ${g.configured ? "free" : "cost"}">${g.configured ? "Key saved" : "No key"}</span></div>
        <p class="lede">Google's official API, for frames. It has no free tier for image models: each image is billed to the key's Google Cloud project (a Google AI Pro subscription is not documented to cover it). The cap below stops the server before it spends more in a day.</p>
        <form class="stack" data-form="gemini">
          <label class="field"><span class="field-label">API key <em>from aistudio.google.com, kept on the director's machine</em></span><input type="password" name="key" autocomplete="off" placeholder="${g.configured ? "Saved. Paste a new one to replace it." : "Paste the key"}" class="mono-input"></label>
          <div class="grid-2"><label class="field"><span class="field-label">Model</span><select name="model">${(g.models || []).map((m) => `<option value="${m.id}" ${m.id === g.model ? "selected" : ""}>${m.id} · $${m.usd.toFixed(3)}</option>`).join("")}</select></label>
            <label class="field"><span class="field-label">Cap per day, $</span><input type="number" name="daily_usd" step="0.25" min="0" value="${g.daily_usd ?? 1}" class="mono-input"></label></div>
          <p class="field-hint">Spent today: $${(g.spent_today || 0).toFixed(3)} of $${(g.daily_usd ?? 1).toFixed(2)}.</p>
          <div class="row"><button class="btn primary" type="submit">Save</button>${g.configured ? '<button class="btn danger" type="button" data-act="forget-gemini">Forget key</button>' : ""}</div>
        </form></div>`; })()}
      <div class="card"><div class="card-head"><span class="card-title"><b>Google Flow</b> · through useapi.net, optional</span><span class="badge ${f?.configured ? "free" : "cost"}">${f?.configured ? "Token saved" : "Not connected"}</span></div>
        <p class="lede">useapi.net runs Google Flow on your own Google account. Sign the Google account in on their setup page, then paste the useapi.net API token here. The token is saved on the director's machine, never in this browser or the repo.</p>
        <a class="btn" href="${h(f?.setup_url || "https://useapi.net/docs/start-here/setup-google-flow")}" target="_blank" rel="noopener noreferrer">Connect a Google account at useapi.net ↗</a>
        <form class="stack" data-form="flow">
          <label class="field"><span class="field-label">useapi.net API token</span><input type="password" name="token" autocomplete="off" placeholder="${f?.configured ? "Saved. Paste a new one to replace it." : "Paste the token"}" class="mono-input"></label>
          <div class="grid-2">
            <label class="field"><span class="field-label">Plan</span><select name="plan">${["free", "plus", "pro", "ultra"].map((p) => `<option ${f?.plan === p ? "selected" : ""}>${p}</option>`).join("")}</select></label>
            <label class="field"><span class="field-label">Credits per day</span><input type="number" name="daily_credits" value="${f?.daily_budget ?? 50}" min="0" class="mono-input"></label></div>
          <label class="field"><span class="field-label">Google account email <em>optional, if several are connected</em></span><input type="email" name="email" value="${h(f?.email || "")}" autocomplete="off"></label>
          <div class="row"><button class="btn primary" type="submit">Save</button>${f?.configured ? '<button class="btn danger" type="button" data-act="forget-token">Forget token</button>' : ""}</div>
        </form>
        ${f?.configured ? `<button class="btn" data-act="check-accounts">Check connected accounts and live credits</button><div id="accounts-out"></div>` : ""}
      </div>
      <div class="card"><div class="card-head"><span class="card-title"><b>What is free</b></span></div>
        <ul class="small" style="margin:0;padding-left:18px;display:grid;gap:6px">
          <li><b>No subscription needed:</b> pick Flow by hand as a frame source, or open Make it in Flow by hand under a shot's action. You generate in your own Flow tab and bring the file back; the app catalogues it and logs a clip's credits. useapi.net below is only for rendering from inside the app.</li>
          <li>A free Google account gets about 50 Flow credits a day: 5 Veo 3.1 Lite or 2 Veo 3.1 Fast clips, 8 seconds each. Omni and upscaling need a paid plan. useapi.net calls these figures averages, not guarantees.</li>
          <li>Flow images (Nano Banana) cost no credits, but each image or clip needs one captcha solve. useapi.net gives the first account 300; after that you plug in a paid solving service.</li>
          <li>useapi.net itself is a paid subscription. The Flow credits are free; the bridge is not.</li>
          <li>Frames on this machine's GPU are free and unlimited, which is why Pass 1 defaults to it.</li>
          <li>Automating Flow through a third party may break Google's terms; Google can limit or suspend the account. Use an account you can afford to lose.</li>
        </ul></div>
    </div>`);
}

// ------------------------------------------------------------------ events

document.addEventListener("input", (e) => {
  const el = e.target;
  if (el.dataset.seal) {
    const fill = el.parentElement.querySelector(".slider-fill");
    if (fill) fill.style.width = `${el.value}%`;
    return;
  }
  const path = el.dataset.bind;
  if (!path) return;
  let v = el.type === "checkbox" ? el.checked : el.value;
  if (el.dataset.num) v = v === "" ? "" : Number(v);
  if (el.dataset.list) v = String(v).split(",").map((x) => x.trim()).filter(Boolean);
  touchGate(el);
  setPath(path, v);
  save();
  if (el.dataset.rerender) renderGate(Number(el.dataset.rerender));
  else if (path === "llm_model") renderAll();
  else refresh();
});

document.addEventListener("change", async (e) => {
  const el = e.target;
  if (el.dataset.seal) {
    const n = Number(el.dataset.seal);
    const signed = !!S.gates[`g${n}`];
    const v = Number(el.value);
    if (!signed && v >= 92) sign(n, true);
    else if (signed && v <= 15) sign(n, false);
    else { el.value = signed ? 100 : 0; el.parentElement.querySelector(".slider-fill").style.width = `${el.value}%`; }
    return;
  }
  if (el.dataset.file === "pack") {
    const file = el.files?.[0];
    el.value = "";
    if (!file) return;
    if (!confirm(`Replace ${TEAM ? "the team's" : "this"} project with the one in ${file.name}?`)) return;
    await importPack(file, el.closest("label"));
    return;
  }
  if (el.dataset.file === "hand" || el.dataset.file === "hand-clip") {
    const file = el.files?.[0];
    if (file) await bringBack(shotById(el.dataset.id), el.dataset.file === "hand-clip" ? "motion" : el.dataset.slot, file, el.closest("label"));
    return;
  }
  if (el.dataset.file) {
    const file = el.files?.[0];
    if (!file) return;
    const shot = shotById(el.dataset.id);
    const label = el.closest("label");
    label?.classList.add("busy");
    try {
      const jpeg = file.type.startsWith("video") ? await videoFrame(file) : await toJpeg(file);
      const what = el.dataset.file === "ref" ? "blocking photo" : `${el.dataset.slot} frame (photo)`;
      const { media } = await upload(jpeg, { "X-Label": jobLabel(shot, what).label, "X-Project": jobLabel(shot, what).project, "X-Frame": el.dataset.slot || "" });
      if (el.dataset.file === "ref") {
        touchGate(el);
        shot.ref = media.name;
        upsertRow({ asset_id: `shot_${shotNo(shot)}_previs_photo`, stage: "previs", tool_or_model: "Phone camera (human)", seed: "", prompt_or_input: `Blocking for: ${shot.camera_move}, ${shot.framing}`, status: "APPROVED", human_approver: S.director || "Previs crew", media: media.name });
        save();
        renderGate(2);
      } else {
        const slot = el.dataset.slot;
        shot[slot].takes.push(media.name);
        shot[slot].pick = media.name;
        logTake(shot, slot, { ...media, tool_or_model: "Phone camera (human)", prompt: "Photographed on set" });
        save();
        renderGate(3);
      }
      buzz(20);
    } catch (err) {
      toast(err.message, "bad");
    } finally {
      label?.classList.remove("busy");
    }
  }
});

document.addEventListener("submit", async (e) => {
  const form = e.target;
  const kind = form.dataset.form;
  if (!kind) return;
  e.preventDefault();
  const data = Object.fromEntries(new FormData(form));
  if (kind === "exclusion") {
    const v = String(data.ex || "").trim();
    if (!v) return;
    touchGate(form);
    S.brief.exclusions.push(v);
    buzz();
    save();
    renderGate(1);
    $('[data-form="exclusion"] input')?.focus();
  } else if (kind === "fact") {
    const v = String(data.fact || "").trim();
    if (!v) return;
    touchGate(form);
    S.brief.facts.push([`SRC-${pad(S.brief.facts.length + 1).padStart(3, "0")}`, v]);
    save();
    renderGate(1);
  } else if (kind === "row") {
    S.provenance.push({ asset_id: data.asset_id, timestamp: nowIso(), stage: data.stage, tool_or_model: data.tool, checkpoint_hash: "N/A", seed: "",
      prompt_or_input: data.note || "", human_approver: S.director || "", status: "APPROVED", manual: true });
    save();
    renderGate(3);
  } else if (kind === "login") {
    try {
      await api.post("/api/login", { code: data.code });
      server.authed = true;
      await loadStatus();
      renderAll();
      poll();
      if (TEAM) pull();
      toast("Unlocked. The GPU is yours.", "good");
    } catch (err) { toast(err.message, "bad"); }
  } else if (kind === "gemini") {
    const body = { model: data.model, daily_usd: data.daily_usd };
    if (data.key) body.key = data.key;
    try {
      await api.post("/api/gemini/key", body);
      await loadStatus();
      toast("Saved on the director's machine.", "good");
      openAccounts();
      renderGate(3);
    } catch (err) { toast(err.message, "bad"); }
  } else if (kind === "flow") {
    const body = { plan: data.plan, daily_credits: data.daily_credits, email: data.email || "" };
    if (data.token) body.token = data.token;
    try {
      if (!data.token && !server.status?.flow?.configured) throw new ApiError(400, "Paste the useapi.net token.");
      await api.post("/api/flow/token", body);
      await loadStatus();
      toast("Saved on the director's machine.", "good");
      openAccounts();
      renderGate(3);
    } catch (err) { toast(err.message, "bad"); }
  }
});

document.addEventListener("click", async (e) => {
  const el = e.target.closest("[data-act]");
  if (!el || el.disabled) return;
  const act = el.dataset.act;
  const shot = el.dataset.id ? shotById(el.dataset.id) : null;
  switch (act) {
    case "role":
      S.role = el.dataset.id; buzz(); save(); refreshRoles(); break;
    case "preset": {
      if (el.dataset.id === S.brief.preset) break;
      const dirty = S.brief.target_audience || S.brief.exclusions.length;
      if (dirty && !confirm("Switch client? The three answers and exclusions stay; facts, locations and tone change.")) break;
      const p = PRESETS[el.dataset.id];
      touchGate(el);
      Object.assign(S.brief, { preset: el.dataset.id, client: p.client, project_title: p.project_title, tone: [...p.tone], facts: p.facts.map((f) => [...f]) });
      S.shots.forEach((s) => { if (!p.locations.some((l) => l[0] === s.location_id)) s.location_id = p.locations[0][0]; s.characters = []; s.source_ids = []; });
      buzz(); save(); renderAll(); break;
    }
    case "del-ex":
      touchGate(el); S.brief.exclusions.splice(Number(el.dataset.i), 1); buzz(); save(); renderGate(1); break;
    case "use-sug": {
      const k = el.dataset.k;
      const v = S.suggest.fields[k];
      touchGate(el);
      if (k === "exclusions") S.brief.exclusions = [...new Set([...S.brief.exclusions, ...v])];
      else if (k === "references") S.brief.references = [S.brief.references, ...v].filter(Boolean).join("\n");
      else S.brief[k] = v;
      delete S.suggest.fields[k];
      S.suggest.used = true;
      save(); renderGate(1); break;
    }
    case "draft-brief": draftBrief(el); break;
    case "draft-shots": draftShots(el); break;
    case "add-shot":
      touchGate(el); S.shots.push(newShot(S.shots.length, { label: `Shot ${S.shots.length + 1}`, duration_sec: 5 }, S.brief.preset, S.frame_source)); save(); renderGate(2); break;
    case "del-shot":
      if (!confirm("Delete this shot and its frames?")) break;
      touchGate(el); S.shots = S.shots.filter((s) => s !== shot); save(); renderAll(); break;
    case "lock-shot":
      touchGate(el); shot.locked = !shot.locked; buzz(shot.locked ? [15, 30] : 10); save(); renderGate(2); break;
    case "toggle-char":
      touchGate(el); shot.characters = shot.characters.includes(el.dataset.c) ? shot.characters.filter((c) => c !== el.dataset.c) : [...shot.characters, el.dataset.c]; save(); renderGate(2); break;
    case "toggle-src":
      touchGate(el); shot.source_ids = shot.source_ids.includes(el.dataset.src) ? shot.source_ids.filter((c) => c !== el.dataset.src) : [...shot.source_ids, el.dataset.src]; save(); renderGate(2); break;
    case "clear-ref":
      touchGate(el); shot.ref = null; save(); renderGate(2); break;
    case "frame-source":
      S.frame_source = el.dataset.v;
      for (const s of S.shots) for (const slot of ["first", "last"]) if (!s[slot].locked) s[slot].source = el.dataset.v;
      buzz(); save(); renderGate(3); break;
    case "source":
      shot[el.dataset.slot].source = el.dataset.v; save(); renderGate(3); break;
    case "frame": startFrame(shot, el.dataset.slot); break;
    case "copy-hand": {
      const text = handPrompt(shot, el.dataset.slot);
      try { await navigator.clipboard.writeText(text); toast("Copied. Paste it into Flow.", "good"); }
      catch { window.prompt("Copy this into Flow:", text); }
      break;
    }
    case "pick": {
      const t = shot[el.dataset.slot];
      t.pick = el.dataset.m; buzz(8); save(); renderGate(3); break;
    }
    case "lock": {
      const slot = el.dataset.slot;
      const t = shot[slot];
      if (!t.pick) break;
      t.locked = true;
      decideTakes(shot, slot, true);
      reopen3();
      buzz([15, 30, 15]); save(); renderGate(3); break;
    }
    case "unlock": {
      const slot = el.dataset.slot;
      shot[slot].locked = false;
      decideTakes(shot, slot, false);
      if (slot === "first") {
        // A new first frame invalidates what was built on it.
        for (const s of ["last", "motion"]) if (shot[s].locked) { shot[s].locked = false; decideTakes(shot, s, false); }
      }
      reopen3();
      save(); renderGate(3); break;
    }
    case "skip-last":
      shot.last.skip = !shot.last.skip; save(); renderGate(3); break;
    case "still":
      shot.motion.still = !shot.motion.still;
      reopen3();
      save(); renderGate(3); break;
    case "motion": startMotion(shot); break;
    case "team": openTeam(); break;
    case "render-cut": renderCut(el); break;
    case "copy-link":
      try { await navigator.clipboard.writeText(`${location.origin}/t/${TEAM}`); toast("Link copied.", "good"); } catch { toast("Long-press the link to copy it.", "bad"); }
      break;
    case "engine": shot.motion.engine = el.dataset.v; buzz(); save(); renderGate(3); break;
    case "local-motion": startLocalMotion(shot); break;
    case "draft-action": draftAction(shot, el); break;
    case "vo-rec": voRecord(); break;
    case "vo-stop": voStop(); break;
    case "del-row": S.provenance.splice(Number(el.dataset.i), 1); save(); renderGate(3); break;
    case "verdict": {
      const c = el.dataset.c;
      S.audit.checks[c] = { ...(S.audit.checks[c] || {}), result: S.audit.checks[c]?.result === el.dataset.v ? null : el.dataset.v };
      if (c === "signature" && S.audit.checks[c].result === "Pass") S.audit.signed_at = nowIso();
      buzz(); save(); renderGate(4); break;
    }
    case "check-intent": checkIntent(el); break;
    case "pack": openPack(); break;
    case "tab": packTab = el.dataset.name; openPack(); break;
    case "copy-pack": {
      const text = textFiles(S, auditMetrics()).map((f) => `===== ${f.name} =====\n${f.data}`).join("\n\n");
      try { await navigator.clipboard.writeText(text); toast("Copied all six files as text.", "good"); }
      catch { toast("This browser blocked the clipboard. Use Download .zip.", "bad"); }
      break;
    }
    case "zip": downloadZip(el); break;
    case "close": closeSheet(); break;
    case "close-to-cut": closeSheet(); $("#gate-4")?.scrollIntoView(); break;
    case "accounts": openAccounts(); break;
    case "forget-token":
      if (!confirm("Remove the useapi.net token from the director's machine?")) break;
      try { await api.post("/api/flow/token", { token: "" }); await loadStatus(); openAccounts(); renderGate(3); toast("Token removed."); } catch (err) { toast(err.message, "bad"); }
      break;
    case "forget-gemini":
      if (!confirm("Remove the Gemini API key from the director's machine?")) break;
      try { await api.post("/api/gemini/key", { key: "" }); await loadStatus(); openAccounts(); renderGate(3); toast("Key removed."); } catch (err) { toast(err.message, "bad"); }
      break;
    case "visibility":
      try {
        const r = await api.post(`/api/teams/${TEAM}/settings`, { visibility: el.dataset.v });
        team.visibility = r.team.visibility;
        toast(r.team.visibility === "community" ? "Shared with the community: listed on the teams page." : "Private: only people with the link.", "good");
        openTeam();
      } catch (err) { toast(err.message, "bad"); }
      break;
    case "check-accounts": {
      el.classList.add("busy");
      try {
        const res = await api.get("/api/flow/accounts");
        const rows = Object.entries(res.accounts);
        $("#accounts-out").innerHTML = rows.length ? rows.map(([email, a]) => `<div class="machine"><b>${h(email)}</b><br>Health: ${h(a.health)}${a.credits ? `<br>Credits: <b class="num">${h(a.credits.credits)}</b> · ${h(a.credits.userPaygateTier || "")}` : ""}${(a.video_models || []).length ? `<br>${a.video_models.map((m) => `${h(m.displayName || m.key)}: ${h(m.creditCost)} cr`).join(" · ")}` : ""}</div>`).join("")
          : `<p class="notice warn">No Google account is connected to this useapi.net token yet. Use the setup link above.</p>`;
        server.status.flow = res.flow;
      } catch (err) { $("#accounts-out").innerHTML = `<p class="notice bad">${h(err.message)}</p>`; }
      finally { el.classList.remove("busy"); }
      break;
    }
    case "reset":
      if (!confirm("Start over? This clears the brief, shots, audit and the provenance log on this phone. Frames stay on the server.")) break;
      S = fresh(); save(); renderAll(); window.scrollTo(0, 0); break;
    default: break;
  }
});

document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#sheet").hidden) closeSheet(); });
document.addEventListener("click", (e) => { if (e.target.id === "sheet") closeSheet(); });

// ------------------------------------------------------------------ boot

function startTimecode() {
  const t0 = performance.now();
  setInterval(() => {
    const ms = performance.now() - t0;
    const s = Math.floor(ms / 1000);
    $("#tc").textContent = `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}:${pad(Math.floor((ms % 1000) / (1000 / 24)))}`;
  }, 125);
}

function watchGates() {
  const io = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (en.isIntersecting) {
        currentGate = Number(en.target.id.slice(5));
        renderRail();
      }
    }
  }, { rootMargin: "-45% 0px -50% 0px" });
  $$(".gate").forEach((g) => io.observe(g));
}

async function loadStatus() {
  try {
    server.status = await api.get("/api/status");
    server.authed = true;
  } catch (e) {
    if (e.status === 401) server.authed = false;
  }
  refreshLights();
}

// The library page queues files to reuse ("Use in shot"); apply them here so
// the provenance row is written the same way as for a fresh take.
function applyImports() {
  if (!S.imports?.length) return false;
  for (const im of S.imports) {
    const shot = shotById(im.shot);
    if (!shot || shot[im.slot].locked) continue;
    const t = shot[im.slot];
    if (!t.takes.includes(im.meta.name)) {
      t.takes.push(im.meta.name);
      logTake(shot, im.slot, { ...im.meta, reused: true, prompt: `${im.meta.prompt || ""} (reused from the library)` });
    }
    t.pick = im.meta.name;
    if (im.slot === "last") t.skip = false;
    if (im.slot === "motion") t.still = false;
  }
  S.imports = [];
  save();
  return true;
}

window.addEventListener("storage", (e) => {
  if (e.key !== KEY) return;
  S = load();
  applyImports();
  renderAll();
});

async function boot() {
  applyImports();
  shell();
  try {
    const s = await api.get("/api/session");
    server.reachable = true;
    server.authed = s.authed;
  } catch { server.reachable = false; }
  if (server.authed) await loadStatus();
  renderAll();
  startTimecode();
  watchGates();
  poll();
  setInterval(() => { if (server.authed && !$("#gate-3").contains(document.activeElement)) loadStatus().then(() => renderRail()); }, 30000);
  if (TEAM) {
    await pull();
    setInterval(() => { if (!document.hidden) pull(); }, 2500);
  }
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "127.0.0.1" || location.hostname === "localhost")) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

boot();
