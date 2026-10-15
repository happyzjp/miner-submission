"""Deterministic, bounded curriculum parameters for the existing trusted solvers.

Only problem specifications cross the sandbox boundary. Answers, teaching text,
charts and token budgets belong to CapabilityForge's trusted runtime.
"""
from __future__ import annotations

import json
import random
import re
from collections import deque
from pathlib import Path
from typing import Iterator


SUBJECTS = {
    "chinese_reading": "chinese",
    "english_language": "english",
    "physics_reasoning": "physics",
    "chemistry_reasoning": "chemistry",
    "biology_reasoning": "biology",
}
MATH = {"ratio_scaling", "ratio_transfer", "linear_modeling"}
STAGES = ("FOUNDATION", "TRANSFER", "GROWTH")
BEHAVIORS = ("solution", "hint", "correction", "clarification")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


def validate_request(request: dict) -> dict:
    if not isinstance(request, dict) or request.get("schema_version") != "learning-unit.v5":
        raise ValueError("Expected a learning-unit.v5 public request")
    if request.get("output", "problem_specs.jsonl") != "problem_specs.jsonl":
        raise ValueError("Only problem_specs.jsonl output is supported")
    unit = request.get("unit")
    if not isinstance(unit, dict):
        raise ValueError("Request must contain a learning unit")
    if not isinstance(unit.get("unit_id"), str) or not IDENTIFIER.fullmatch(unit["unit_id"]):
        raise ValueError("Invalid learning unit identifier")
    if unit.get("capability") not in MATH | SUBJECTS.keys():
        raise ValueError("This method does not support the requested capability")
    if unit.get("stage") not in STAGES or unit.get("behavior", "solution") not in BEHAVIORS:
        raise ValueError("Unsupported stage or teaching behavior")
    if unit.get("language") not in ("zh", "en"):
        raise ValueError("Only the frozen Chinese/English language groups are supported")
    if unit.get("age_band") not in (
        {"min_inclusive": 12, "max_exclusive": 14},
        {"min_inclusive": 14, "max_exclusive": 16},
    ):
        raise ValueError("Unsupported age band")
    if unit.get("scenario") not in ("classroom", "recipe", "chart"):
        raise ValueError("Unsupported scenario")
    modalities = unit.get("input_modalities", ["text"])
    if not isinstance(modalities, list) or not modalities or any(m not in ("text", "image") for m in modalities):
        raise ValueError("Unsupported input modalities")
    if type(unit.get("generation_seed")) is not int:
        raise ValueError("A concrete integer generation_seed is required; null seeds are not reproducible")
    if type(unit.get("sample_budget")) is not int or not 1 <= unit["sample_budget"] <= 100000:
        raise ValueError("sample_budget must be an integer in [1, 100000]")
    source_ids = request.get("source_ids")
    if (not isinstance(source_ids, list) or not source_ids
            or any(not isinstance(s, str) or not IDENTIFIER.fullmatch(s) for s in source_ids)
            or len(set(source_ids)) != len(source_ids)):
        raise ValueError("Unique declared source identifiers are required")
    return unit


def problem_kind(unit: dict) -> str:
    if unit.get("behavior", "solution") == "clarification":
        return "missing_condition"
    # Match capability, rather than assuming every GROWTH unit is mathematics.
    return {"ratio_scaling": "direct_scale", "ratio_transfer": "unit_rate",
            "linear_modeling": "linear_equation"}[unit["capability"]]


def generate(request: dict) -> list[dict]:
    unit = validate_request(request)
    subject = SUBJECTS.get(unit["capability"])
    kind = "subject_practice" if subject else problem_kind(unit)
    # Subject solvers accept 2..80. Mathematics allows 1..1000; use a bounded
    # 2..400 domain so large legal quotas still have distinct parameter pairs.
    upper = 80 if subject else 400
    width = upper - 1
    population = width * width
    count = unit["sample_budget"]
    if count > population:
        raise ValueError(f"Requested {count} samples; this method supports at most {population} for this unit")
    rng = random.Random(unit["generation_seed"])
    # Sampling without replacement has finite work even close to domain capacity.
    selected = rng.sample(range(population), count)
    preferred = f"synthetic-{subject}-v1" if subject else "synthetic-ratio-v1"
    source_id = preferred if preferred in request["source_ids"] else request["source_ids"][0]
    records = []
    for index, value in enumerate(selected):
        a, b = 2 + value // width, 2 + value % width
        record = {"id": f"p{index:06d}", "kind": kind, "a": a, "b": b,
                  "scenario": unit["scenario"], "source_id": source_id}
        if subject:
            record.update(subject=subject, stage=unit["stage"])
        else:
            record.update(scale=None if kind == "missing_condition" else rng.randint(2, 20),
                          offset=rng.randint(1, 16) if kind == "linear_equation" else 0)
        records.append(record)
    # A reproducible curriculum: small/easy quantities first, with periodic
    # retrieval of simpler examples in the transfer and growth stages.
    records.sort(key=lambda r: (max(r["a"], r["b"]), r["a"] + r["b"], r.get("offset", 0), r["id"]))
    if unit["stage"] != "FOUNDATION":
        easy, harder = deque(records[:len(records) // 3]), records[len(records) // 3:]
        records = []
        for index, record in enumerate(harder):
            records.append(record)
            if index % 2 == 1 and easy:
                records.append(easy.popleft())
        records.extend(easy)
    return records


def jsonl(records: list[dict]) -> Iterator[str]:
    for record in records:
        yield json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def write_specs(output: Path, records: list[dict]) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    destination = output / "problem_specs.jsonl"
    if destination.exists():
        raise ValueError(f"Refusing to overwrite {destination}; use a fresh output directory")
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.writelines(jsonl(records))
    return destination
