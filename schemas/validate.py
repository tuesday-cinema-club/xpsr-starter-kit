#!/usr/bin/env python3
"""
Validate a JSON file against one of the starter-kit schemas.

No model is involved: this is a deterministic check with one right answer.

Usage:
    python schemas/validate.py brief    path/to/brief.json
    python schemas/validate.py bible    templates/ember-and-oak-bible.json
    python schemas/validate.py shot_breakdown drafts/shots.json
    python schemas/validate.py state    drafts/state.json

Exit code 0 means valid, 1 means invalid.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipelines"))
from common import load_json, load_schema, say, validate  # noqa: E402

SCHEMAS = ["brief", "bible", "shot_breakdown", "state"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("schema", choices=SCHEMAS, help="Which contract to check against")
    parser.add_argument("file", help="JSON file to check")
    args = parser.parse_args()

    errors = validate(load_json(args.file), load_schema(args.schema))
    if errors:
        say("x", f"{args.file} does not match {args.schema}.schema.json ({len(errors)} problem(s)):")
        for e in errors:
            print(f"  - {e}")
        return 1
    say("ok", f"{args.file} matches {args.schema}.schema.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
