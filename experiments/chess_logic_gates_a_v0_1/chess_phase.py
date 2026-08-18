#!/usr/bin/env python3
"""Isolated phase 2: consume a frozen logic lock, then run chess gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from chess_logic.mastery import LogicMastery, MasteryCertificate  # noqa: E402

LOGIC_FILES = (ROOT / "chess_logic" / "gates.py", ROOT / "chess_logic" / "mastery.py")


def source_hashes() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in LOGIC_FILES
    }


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def fail_closed(args: argparse.Namespace, reason: str, lock_sha: str | None) -> int:
    result = {
        "phase": "CHESS_LOCKED",
        "reason": reason,
        "logic_lock_sha256": lock_sha,
        "chess_executed": False,
        "capability": "noData",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logic-lock", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    lock = json.loads(args.logic_lock.read_text(encoding="utf-8"))
    lock_sha = lock.get("lock_sha256")
    body = {key: value for key, value in lock.items() if key != "lock_sha256"}
    if lock_sha != canonical_sha256(body):
        return fail_closed(args, "logic lock digest mismatch", lock_sha)
    if not lock.get("no_chess_imports"):
        return fail_closed(args, "logic phase imported chess modules", lock_sha)

    before_hashes = source_hashes()
    if before_hashes != lock.get("logic_source_hashes"):
        return fail_closed(args, "logic source changed after certification", lock_sha)

    certificate = MasteryCertificate(**lock["certificate"])
    if not LogicMastery.verify_certificate(certificate):
        return fail_closed(args, "logic certificate failed current verification", lock_sha)

    # Chess code is imported only after all frozen logic checks pass.
    from chess_logic.board import Board
    from chess_logic.curriculum import CASES
    from chess_logic.system import ChessLogicSystem

    system = ChessLogicSystem(certificate)
    rows = []
    for name, fen, move, expected in CASES:
        analysis = system.analyze(Board.from_fen(fen), move)
        found = sorted(motif["name"] for motif in analysis["tactics"]["motifs"])
        rows.append(
            {
                "case": name,
                "move": move,
                "expected": expected,
                "found": found,
                "passed": expected in found,
            }
        )

    after_hashes = source_hashes()
    no_backflow = before_hashes == after_hashes == lock["logic_source_hashes"]
    result = {
        "phase": "CHESS_AFTER_FROZEN_LOGIC",
        "logic_lock_sha256": lock_sha,
        "logic_hashes_before": before_hashes,
        "logic_hashes_after": after_hashes,
        "no_logic_backflow": no_backflow,
        "chess_executed": True,
        "chess_smoke": {
            "passed": sum(int(row["passed"]) for row in rows),
            "total": len(rows),
            "rows": rows,
        },
        "evidence_scope": "CLEAN_INTERNAL_REGRESSION_NOT_EXTERNAL_CHESS_STRENGTH",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if no_backflow and all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

