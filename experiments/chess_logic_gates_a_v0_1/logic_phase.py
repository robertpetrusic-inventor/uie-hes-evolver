#!/usr/bin/env python3
"""Isolated phase 1: verify and freeze Logic Core without importing chess."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from chess_logic.mastery import LogicMastery  # noqa: E402

LOGIC_FILES = (ROOT / "chess_logic" / "gates.py", ROOT / "chess_logic" / "mastery.py")
ALLOWED_MODULES = {"chess_logic.gates", "chess_logic.mastery"}


def source_hashes() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in LOGIC_FILES
    }


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    report = LogicMastery.run()
    loaded = sorted(name for name in sys.modules if name.startswith("chess_logic."))
    forbidden = sorted(set(loaded) - ALLOWED_MODULES)
    lock_body = {
        "phase": "LOGIC_ONLY",
        "certificate": report.certificate.to_dict(),
        "logic_source_hashes": source_hashes(),
        "loaded_project_modules": loaded,
        "forbidden_chess_modules": forbidden,
        "no_chess_imports": not forbidden,
    }
    lock = {**lock_body, "lock_sha256": canonical_sha256(lock_body)}
    args.output.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(lock, indent=2))
    return 0 if report.certificate.locked and not forbidden else 1


if __name__ == "__main__":
    raise SystemExit(main())

