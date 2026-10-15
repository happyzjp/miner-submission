"""CapabilityForge sandbox entry point; Python 3.11 standard library only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from curriculum import generate, write_specs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    write_specs(args.output, generate(request))


if __name__ == "__main__":
    main()
