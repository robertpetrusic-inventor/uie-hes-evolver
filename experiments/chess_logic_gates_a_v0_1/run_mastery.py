#!/usr/bin/env python3
"""Run the exhaustive logic lock and the first chess-tactic smoke suite."""

from __future__ import annotations

import json
from pathlib import Path

from chess_logic.mastery import LogicMastery


def main() -> int:
    mastery = LogicMastery.run()
    output: dict[str, object] = {"logic_mastery": mastery.certificate.to_dict()}
    if not mastery.certificate.locked:
        output["chess_stage"] = "LOCKED"
        print(json.dumps(output, indent=2))
        return 1

    from chess_logic.board import Board
    from chess_logic.curriculum import CASES
    from chess_logic.system import ChessLogicSystem

    system = ChessLogicSystem(mastery.certificate)
    chess_rows = []
    for name, fen, move, expected in CASES:
        result = system.analyze(Board.from_fen(fen), move)
        found = {motif["name"] for motif in result["tactics"]["motifs"]}
        chess_rows.append(
            {
                "case": name,
                "move": move,
                "expected": expected,
                "found": sorted(found),
                "passed": expected in found,
            }
        )
    output["chess_stage"] = system.stage
    output["chess_smoke"] = {
        "passed": sum(int(row["passed"]) for row in chess_rows),
        "total": len(chess_rows),
        "rows": chess_rows,
        "evidence_scope": "INTERNAL_AUTHORED_REGRESSION_NOT_EXTERNAL_CHESS_STRENGTH",
    }
    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(exist_ok=True)
    (results_dir / "logic_mastery_and_chess_smoke.json").write_text(
        json.dumps(output, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, indent=2))
    return 0 if all(row["passed"] for row in chess_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
