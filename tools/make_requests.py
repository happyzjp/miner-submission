"""Create LOCAL preview requests from a saved public TaskPolicy; no network I/O."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from curriculum import validate_request


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True, help="Local preview seed, never an official task seed")
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--output", type=Path, default=ROOT / "var/requests")
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    program = policy["program"]
    approved = [s["source_id"] for s in program["sources"] if s["approved"] is True]
    source_ids = args.source_id or approved
    if not source_ids or any(s not in approved for s in source_ids):
        raise ValueError("Select source IDs already approved in the published policy")
    requests, seen = [], set()
    for original in program["units"]:
        unit = dict(original)
        # Official generators receive a concrete post-freeze generation seed.
        # This separate namespace is only for local reproducibility/development.
        body = json.dumps(["miner-local-preview-v1", args.seed, unit["unit_id"]]).encode("utf-8")
        unit["generation_seed"] = int.from_bytes(hashlib.sha256(body).digest()[:8], "big")
        request = {"schema_version": "learning-unit.v5", "unit": unit, "source_ids": source_ids,
                   "output": "problem_specs.jsonl", "public_diagnostics": program.get("public_diagnostics", {})}
        validate_request(request)
        if unit["unit_id"] in seen:
            raise ValueError("Duplicate policy unit identifiers")
        seen.add(unit["unit_id"])
        requests.append(request)
    if not requests:
        raise ValueError("The public policy contains no learning units")
    output = args.output.expanduser().resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "var"):
        raise ValueError("Generated requests inside the repository must be placed under var/")
    if ROOT.is_relative_to(output):
        raise ValueError("Output must not contain the submission repository")
    output.mkdir(parents=True, exist_ok=False)
    for request in requests:
        (output / (request["unit"]["unit_id"] + ".json")).write_text(
            json.dumps(request, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
            encoding="utf-8")
    print(f"Wrote {len(requests)} LOCAL preview requests to {output}; official frozen seeds are unchanged.")


if __name__ == "__main__":
    main()
