"""Pure digital-logic primitives and small composed circuits.

All public functions accept and return strict bits (0 or 1).  The composed
circuits intentionally call the primitive gates so the verification ladder is
visible and auditable.
"""

from __future__ import annotations

from dataclasses import dataclass


def _bit(value: int | bool) -> int:
    if value not in (0, 1, False, True):
        raise ValueError(f"expected bit 0/1, got {value!r}")
    return int(bool(value))


def AND(a: int | bool, b: int | bool) -> int:
    return _bit(a) & _bit(b)


def OR(a: int | bool, b: int | bool) -> int:
    return _bit(a) | _bit(b)


def NOT(a: int | bool) -> int:
    return 1 - _bit(a)


def XOR(a: int | bool, b: int | bool) -> int:
    return _bit(a) ^ _bit(b)


def NAND(a: int | bool, b: int | bool) -> int:
    return NOT(AND(a, b))


def NOR(a: int | bool, b: int | bool) -> int:
    return NOT(OR(a, b))


def XNOR(a: int | bool, b: int | bool) -> int:
    return NOT(XOR(a, b))


def MUX2(select: int | bool, a: int | bool, b: int | bool) -> int:
    """Select a when select=0 and b when select=1."""
    return OR(AND(NOT(select), a), AND(select, b))


def HALF_ADDER(a: int | bool, b: int | bool) -> tuple[int, int]:
    return XOR(a, b), AND(a, b)


def FULL_ADDER(
    a: int | bool, b: int | bool, carry_in: int | bool
) -> tuple[int, int]:
    sum_ab, carry_ab = HALF_ADDER(a, b)
    total, carry_sum = HALF_ADDER(sum_ab, carry_in)
    return total, OR(carry_ab, carry_sum)


def COMPARE_1BIT(a: int | bool, b: int | bool) -> tuple[int, int, int]:
    """Return (a<b, a==b, a>b)."""
    a_bit, b_bit = _bit(a), _bit(b)
    return AND(NOT(a_bit), b_bit), XNOR(a_bit, b_bit), AND(a_bit, NOT(b_bit))


def DECODER_2_TO_4(a: int | bool, b: int | bool) -> tuple[int, int, int, int]:
    a_bit, b_bit = _bit(a), _bit(b)
    return (
        AND(NOT(a_bit), NOT(b_bit)),
        AND(NOT(a_bit), b_bit),
        AND(a_bit, NOT(b_bit)),
        AND(a_bit, b_bit),
    )


@dataclass
class DFlipFlop:
    """Minimal one-bit state element used by the mastery suite."""

    q: int = 0

    def __post_init__(self) -> None:
        self.q = _bit(self.q)

    def clock(self, d: int | bool) -> int:
        self.q = _bit(d)
        return self.q

