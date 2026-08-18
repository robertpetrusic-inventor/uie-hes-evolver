"""Exhaustive finite mastery contract for the Logic Core."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any, Callable

from . import gates


MASTERY_VERSION = "logic-core-a-v0.1"


@dataclass(frozen=True)
class MasteryCertificate:
    version: str
    passed: int
    total: int
    score: float
    locked: bool
    evidence_sha256: str
    execution_axis: str = "EXECUTED_CODE"
    data_axis: str = "EXHAUSTIVE_FINITE_TRUTH_TABLES"
    verification_axis: str = "INDEPENDENT_TRUTH_TABLE_ORACLE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MasteryReport:
    certificate: MasteryCertificate
    rows: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "certificate": self.certificate.to_dict(),
            "rows": list(self.rows),
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    return value


class LogicMastery:
    """Run every declared truth-table row and issue a lock certificate."""

    @staticmethod
    def _case(
        rows: list[dict[str, Any]],
        circuit: str,
        inputs: tuple[int, ...],
        expected: Any,
        implementation: Callable[..., Any],
    ) -> None:
        actual = implementation(*inputs)
        rows.append(
            {
                "circuit": circuit,
                "inputs": list(inputs),
                "expected": _jsonable(expected),
                "actual": _jsonable(actual),
                "passed": actual == expected,
            }
        )

    @classmethod
    def run(cls) -> MasteryReport:
        rows: list[dict[str, Any]] = []

        for a in (0, 1):
            cls._case(rows, "NOT", (a,), 1 - a, gates.NOT)

        binary = {
            "AND": (gates.AND, lambda a, b: a & b),
            "OR": (gates.OR, lambda a, b: a | b),
            "XOR": (gates.XOR, lambda a, b: a ^ b),
            "NAND": (gates.NAND, lambda a, b: 1 - (a & b)),
            "NOR": (gates.NOR, lambda a, b: 1 - (a | b)),
            "XNOR": (gates.XNOR, lambda a, b: 1 - (a ^ b)),
        }
        for name, (implementation, oracle) in binary.items():
            for a, b in product((0, 1), repeat=2):
                cls._case(rows, name, (a, b), oracle(a, b), implementation)

        for select, a, b in product((0, 1), repeat=3):
            cls._case(rows, "MUX2", (select, a, b), b if select else a, gates.MUX2)

        for a, b in product((0, 1), repeat=2):
            cls._case(rows, "HALF_ADDER", (a, b), ((a + b) & 1, (a + b) >> 1), gates.HALF_ADDER)
            cls._case(
                rows,
                "COMPARE_1BIT",
                (a, b),
                (int(a < b), int(a == b), int(a > b)),
                gates.COMPARE_1BIT,
            )
            expected_decoder = tuple(int(i == (a * 2 + b)) for i in range(4))
            cls._case(rows, "DECODER_2_TO_4", (a, b), expected_decoder, gates.DECODER_2_TO_4)

        for a, b, carry in product((0, 1), repeat=3):
            value = a + b + carry
            cls._case(rows, "FULL_ADDER", (a, b, carry), (value & 1, int(value >= 2)), gates.FULL_ADDER)

        for q, d in product((0, 1), repeat=2):
            actual = gates.DFlipFlop(q).clock(d)
            rows.append(
                {
                    "circuit": "D_FLIP_FLOP",
                    "inputs": [q, d],
                    "expected": d,
                    "actual": actual,
                    "passed": actual == d,
                }
            )

        passed = sum(int(row["passed"]) for row in rows)
        total = len(rows)
        source_sha = hashlib.sha256(Path(gates.__file__).read_bytes()).hexdigest()
        evidence_payload = {
            "version": MASTERY_VERSION,
            "gate_source_sha256": source_sha,
            "rows": rows,
        }
        evidence_sha = hashlib.sha256(
            json.dumps(evidence_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        certificate = MasteryCertificate(
            version=MASTERY_VERSION,
            passed=passed,
            total=total,
            score=passed / total if total else 0.0,
            locked=total > 0 and passed == total,
            evidence_sha256=evidence_sha,
        )
        return MasteryReport(certificate=certificate, rows=tuple(rows))

    @classmethod
    def verify_certificate(cls, certificate: MasteryCertificate) -> bool:
        current = cls.run().certificate
        return (
            certificate == current
            and certificate.locked
            and certificate.score == 1.0
            and certificate.passed == certificate.total
        )

