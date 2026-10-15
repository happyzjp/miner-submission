"""Export local training materials with the installed, trusted CapabilityForge renderers.

This optional host-side tool is never called by generator.py. It does not train
a model, read hidden assessments or assert formal audit/qualification success.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from curriculum import generate, jsonl, write_specs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requests", type=Path, nargs="+", help="One or more public learning-unit request files")
    sources_arg = parser.add_mutually_exclusive_group(required=True)
    sources_arg.add_argument("--policy", type=Path, help="Complete published TaskPolicy JSON")
    sources_arg.add_argument("--sources", type=Path, help="Source array; examples/sources.json is development data only")
    parser.add_argument("--output", type=Path, default=ROOT / "var/training-preview")
    args = parser.parse_args()
    try:
        from capabilityforge.shared.contracts.base import Source
        from capabilityforge.shared.contracts.programs import LearningUnit
        from capabilityforge.shared.foundation.serialization import canonical, digest
        from capabilityforge.validator.curriculum.materials import PROBLEM_SPEC, render
        from capabilityforge.validator.curriculum.subject_materials import SubjectProblemSpec, render_subject
    except ModuleNotFoundError as exc:
        raise SystemExit("Use a Python 3.11 environment with the matching public capabilityforge package installed. "
                         "This optional export tool needs its trusted renderers; generator.py uses only the standard library.") from exc
    source_document = json.loads((args.policy or args.sources).read_text(encoding="utf-8"))
    rows = source_document["program"]["sources"] if args.policy else source_document
    sources, source_identifiers = {}, set()
    for row in rows:
        source = Source.model_validate(row)
        if source.source_id in source_identifiers:
            raise ValueError("Source declarations must have unique identifiers")
        source_identifiers.add(source.source_id)
        if source.approved:
            sources[source.source_id] = source
    if not sources:
        raise ValueError("Local export requires explicitly approved source declarations")
    requests, identifiers = [], set()
    policy_units = {u["unit_id"]: u for u in source_document["program"]["units"]} if args.policy else None
    for path in args.requests:
        request = json.loads(path.read_text(encoding="utf-8"))
        unit = LearningUnit.model_validate(request["unit"])
        records = generate(request)
        if unit.unit_id in identifiers:
            raise ValueError("Use unique learning unit IDs in one export")
        identifiers.add(unit.unit_id)
        if any(s not in sources for s in request["source_ids"]):
            raise ValueError("Request source IDs differ from the supplied source declarations")
        if policy_units is not None:
            expected = dict(policy_units.get(unit.unit_id, {}))
            actual = dict(request["unit"])
            expected.pop("generation_seed", None)
            actual.pop("generation_seed", None)
            if expected != actual:
                raise ValueError("Preview unit differs from the published task, apart from its local generation seed")
        requests.append((request, unit, records))
    output = args.output.expanduser().resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "var"):
        raise ValueError("Generated training files inside the repository must be placed under var/")
    if ROOT.is_relative_to(output):
        raise ValueError("Output must not contain the submission repository")
    output.mkdir(parents=True, exist_ok=False)
    reports, materials = [], []
    for request, unit, records in requests:
        write_specs(output / "specs" / unit.unit_id, records)
        seen = set()
        for position, line in enumerate(jsonl(records)):
            spec = PROBLEM_SPEC.validate_json(line)
            identity = digest(spec.model_dump(mode="json", exclude={"id", "answer", "source_id"}))
            if identity in seen:
                raise ValueError("Repeated problem parameters within a learning unit")
            seen.add(identity)
            renderer = render_subject if isinstance(spec, SubjectProblemSpec) else render
            materials.append(renderer(spec, unit, output, position, sources[spec.source_id]))
        reports.append({"unit_id": unit.unit_id, "records": len(records), "stage": str(unit.stage),
                        "generation_seed": unit.generation_seed, "request_sha256": digest(request)})
    material_bytes = b"".join(canonical(m) + b"\n" for m in materials)
    (output / "learning_materials.jsonl").write_bytes(material_bytes)
    (output / "messages.jsonl").write_bytes(b"".join(
        canonical({"id": m["id"], "messages": m["messages"], "images": m["images"]}) + b"\n"
        for m in materials))
    manifest = {"development_only": True, "formal_audit_performed": False,
                "records": len(materials), "units": reports,
                "materials_sha256": hashlib.sha256(material_bytes).hexdigest(),
                "sources": [s.model_dump(mode="json") for s in sources.values()]}
    (output / "curriculum_manifest.json").write_bytes(canonical(manifest) + b"\n")
    print(json.dumps({"output": str(output), "units": len(reports), "records": len(materials),
                      "development_only": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
