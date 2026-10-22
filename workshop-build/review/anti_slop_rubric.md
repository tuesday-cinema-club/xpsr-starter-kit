# The 7-Point Anti-Slop Audit

Every cut is scored on these seven checks before it is screened or released. The Auditor reads them aloud at Gate 04. A phone is enough to run this audit.

Check 7 is non-negotiable. A cut that fails it does not ship, whatever the other scores.

## The checks

### 1. Intent

Does the cut honor the brief: the audience, the feeling and the call to action? Does it break **any** exclusion in `brief.md`?

- Pass: every exclusion respected, and the call to action is clear.
- Fail: any exclusion broken, or the spot could be for a different audience.

### 2. Evidence

Is every factual claim, spoken or on screen, backed by a row in `research_log.csv`?

- Pass: each claim maps to a `source_id`, and `state.json` shows `unverified_sources: 0`.
- Fail: any claim with no source, including vague superlatives such as "best in town".

### 3. Continuity

Do faces, hair, wardrobe, props, set and lighting match `bible.json` from shot to shot?

- Pass: a viewer would read every shot as the same people in the same world.
- Fail: wardrobe changes, face drift, a prop that appears and disappears, or light that flips direction.

### 4. Specificity

Could this spot only be for this client? Is the language and imagery crafted, not default?

- Pass: concrete details from the fact sheet and bible: the roast-date label, the brass pin, the street sign.
- Fail: generic stock moments, or phrases a model writes for everyone ("crafted with passion", "more than just coffee").

### 5. Technical QC

Does the file meet delivery specs? `pipelines/03-post-production/qc_check.py` measures these for you.

- Resolution and aspect ratio match the bible.
- Frame rate matches the bible.
- Runtime is within the brief, normally 30 seconds or less.
- Integrated loudness is near the target (minus 14 LUFS for social media by default) and true peak is at or below minus 1 dBTP.

### 6. Provenance

Does every generated or captured asset have a row in `provenance.csv`, with tool or model, checkpoint hash, seed, the prompt or input, and who approved it?

- Pass: a stranger could trace any frame back to how it was made.
- Fail: any frame, audio file or caption track without a row.

### 7. Human signature (non-negotiable)

Did a named human review, change and approve the cut? Which choices did a human make: a recut, a paint-over, a rewritten line, a rejected frame?

- Pass: the director signs below, and the crew can name at least one place where a human made it better.
- Fail: nobody signed, or the cut went out as the model produced it.

## Scoring

Count the passes out of 7. Release needs **7 of 7**: a single failed check sends the cut back through Revise.

## Sign-off

Director signature:

Date:
