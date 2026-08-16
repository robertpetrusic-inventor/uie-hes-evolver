from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Any


@dataclass(frozen=True)
class Candidate:
    name: str
    solve: Callable[[Any], Any]
    cost: Callable[[Any], int]


@dataclass(frozen=True)
class Evaluation:
    name: str
    correct: int
    total: int
    total_cost: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def verified(self) -> bool:
        return self.correct == self.total


def evaluate(
    candidate: Candidate,
    cases: Iterable[Any],
    oracle: Callable[[Any], Any],
) -> Evaluation:
    correct = 0
    total = 0
    total_cost = 0
    for case in cases:
        expected = oracle(case)
        actual = candidate.solve(case)
        total += 1
        total_cost += candidate.cost(case)
        correct += int(actual == expected)
    return Evaluation(candidate.name, correct, total, total_cost)


def select_verified_min_cost(evaluations: Iterable[Evaluation]) -> Evaluation:
    verified = [e for e in evaluations if e.verified]
    if not verified:
        raise RuntimeError("No fully verified candidate exists.")
    return min(verified, key=lambda e: (e.total_cost, e.name))
