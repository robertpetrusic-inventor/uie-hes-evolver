"""Minimal correctness-first evolver on a frozen arithmetic holdout.

The point is not to solve hard math. It demonstrates the selection rule:
1) reject wrong candidates, 2) among fully correct candidates choose lower cost.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from uie_evolver.core import Candidate, evaluate, select_verified_min_cost


def oracle(x: int) -> int:
    return x * x + 2 * x + 1


def expanded(x: int) -> int:
    return x * x + 2 * x + 1


def factored(x: int) -> int:
    y = x + 1
    return y * y


def wrong_fast(x: int) -> int:
    return x * x + 1


CANDIDATES = [
    Candidate("expanded", expanded, lambda _x: 5),
    Candidate("factored", factored, lambda _x: 2),
    Candidate("wrong_fast", wrong_fast, lambda _x: 2),
]

# Deliberately fixed/frozen list for reproducibility.
HOLDOUT = [-101, -37, -9, -1, 0, 1, 2, 7, 18, 99, 1001]


def main() -> None:
    evaluations = [evaluate(c, HOLDOUT, oracle) for c in CANDIDATES]
    winner = select_verified_min_cost(evaluations)

    for e in evaluations:
        print(
            f"{e.name:12s} accuracy={e.correct}/{e.total} "
            f"cost={e.total_cost} verified={e.verified}"
        )
    print(f"WINNER={winner.name}")

    assert winner.name == "factored"


if __name__ == "__main__":
    main()
