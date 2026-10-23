// Builds the files the starter kit reads: brief.md and brief.json (schemas/
// brief.schema.json), shots.json (schemas/shot_breakdown.schema.json),
// research_log.csv, provenance.csv (pipelines/common.py columns, CRLF) and
// audit.md (workshop-build/templates/audit_template.md).

import { CHECKS, PRESETS } from "./data.js";

const PROV_FIELDS = ["asset_id", "timestamp", "stage", "tool_or_model", "checkpoint_hash", "seed",
  "prompt_or_input", "human_approver", "status"];

const csvCell = (v) => {
  const s = String(v ?? "");
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

const decisionLine = (g) => g?.at
  ? `${g.decision} by ${g.director} on ${g.at.slice(0, 10)}`
  : "Not decided";

export function briefJson(s) {
  const b = s.brief;
  return {
    project_title: b.project_title,
    client: b.client,
    target_audience: b.target_audience,
    core_feeling: b.core_feeling,
    call_to_action: b.call_to_action,
    key_message: b.key_message,
    runtime_sec: Number(b.runtime_sec) || 30,
    tone: b.tone,
    exclusions: b.exclusions,
    references: b.references.split("\n").map((r) => r.trim()).filter(Boolean),
  };
}

export function briefMd(s) {
  const b = s.brief;
  const refs = b.references.split("\n").map((r) => r.trim()).filter(Boolean);
  return `# Project Brief: ${b.project_title || "(project title)"}

Client: ${b.client || "(client)"}

## 1. Director's three answers

- **Who is it for?** ${b.target_audience}
- **What should they feel?** ${b.core_feeling}
- **What should they do next?** ${b.call_to_action}

## 2. Key message

${b.key_message}

## 3. Runtime

${Number(b.runtime_sec) || 30} seconds.

## 4. Exclusions (at least three)

This spot will never:

${b.exclusions.map((e, i) => `${i + 1}. ${e}`).join("\n") || "1.\n2.\n3."}

## 5. References

${refs.map((r) => `- ${r}`).join("\n") || "(none yet)"}

Tone: ${b.tone.join(", ") || "(none yet)"}

## Approval

- Gate 01 decision: ${decisionLine(s.gates.g1)}
`;
}

export function researchCsv(s) {
  const facts = s.brief.facts || PRESETS[s.brief.preset]?.facts || [];
  const rows = [["source_id", "claim", "source", "verified_by", "verified_on"]];
  for (const [id, claim] of facts) rows.push([id, claim, `Client fact sheet (${s.brief.client})`, "", ""]);
  return rows.map((r) => r.map(csvCell).join(",")).join("\r\n") + "\r\n";
}

export function shotsJson(s) {
  return {
    scene_id: "SC01",
    scene_name: s.brief.project_title || "Scene 1",
    shots: s.shots.map((sh, i) => ({
      shot_number: i + 1,
      framing: sh.framing,
      lens_mm: Number(sh.lens_mm),
      duration_sec: Number(sh.duration_sec),
      camera_move: sh.camera_move,
      location_id: sh.location_id,
      characters: sh.characters,
      action_description: sh.action_description,
      visual_prompt: sh.visual_prompt,
      voiceover_line: sh.voiceover_line,
      source_ids: sh.source_ids,
      claims_sourced: sh.voiceover_line.trim() === "" || sh.source_ids.length > 0,
    })),
  };
}

export function provenanceCsv(s) {
  const lines = [PROV_FIELDS.join(",")];
  for (const r of s.provenance) lines.push(PROV_FIELDS.map((k) => csvCell(r[k])).join(","));
  return lines.join("\r\n") + "\r\n";
}

export function auditMd(s, metrics) {
  const a = s.audit;
  const rows = CHECKS.map((c) => {
    const r = a.checks[c.id] || {};
    const ev = [r.evidence, metrics.machine[c.id]].filter(Boolean).join(" Machine: ").replace(/\|/g, "/");
    return `| ${c.n} | ${c.name}: ${c.ask[0].toLowerCase()}${c.ask.slice(1)} | ${r.result || ""} | ${ev} |`;
  }).join("\n");
  return `# Anti-Slop Audit: ${s.brief.project_title || "(project title)"}

Auditor: ${a.auditor}
Date: ${a.date || new Date().toISOString().slice(0, 10)}
Cut reviewed (file name): ${a.cut}

Mark each check **Pass** or **Fail** and write one line of evidence. Check 7 is non-negotiable: without it the cut does not ship, whatever the other scores.

| Number | Check | Result | Evidence |
| --- | --- | --- | --- |
${rows}

Score: ${metrics.passed} of 7${metrics.passed === 7 ? "" : ". Release needs 7 of 7."}

## What the agent did, what broke, how we caught it, where a human made it better

${a.notes || "- Writer crew:\n- Previs crew:\n- Frames crew:\n- Edit and Sound crew:"}

## Gate decisions

- Gate 01 brief: ${decisionLine(s.gates.g1)}
- Gate 02 shot list: ${decisionLine(s.gates.g2)}
- Gate 03 frames and motion: ${decisionLine(s.gates.g3)}

## Release

Director signature: ${a.signature}
Date: ${a.signature ? a.signed_at?.slice(0, 10) || "" : ""}
`;
}

export function textFiles(s, metrics) {
  return [
    { name: "brief.md", data: briefMd(s) },
    { name: "brief.json", data: JSON.stringify(briefJson(s), null, 2) + "\n" },
    { name: "research_log.csv", data: researchCsv(s) },
    { name: "shots.json", data: JSON.stringify(shotsJson(s), null, 2) + "\n" },
    { name: "provenance.csv", data: provenanceCsv(s) },
    { name: "audit.md", data: auditMd(s, metrics) },
  ];
}
