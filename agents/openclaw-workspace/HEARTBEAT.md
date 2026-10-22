# Periodic Checks

Run these every 30 minutes while a project is active. Each check is read-only and reports to the director; none of them fixes anything on its own.

1. **Schema.** For each new file in the project folder that has a schema, run `python3 schemas/validate.py <schema> <file>`. Report failures by file and field.
2. **Bible match.** For each `shots.json` changed since the last check, run `run_breakdown.py --check-only`. Report unknown character or location ids.
3. **Waiting gates.** List every `*_state.json` whose status is `awaiting_review` and how long it has waited.
4. **Provenance.** List files in `frames/` and `audio/` that have no row in `provenance.csv`.
5. **Disk.** Warn when free disk space drops below 10 GB.

If nothing needs attention, reply with one line: `All gates clear.`
