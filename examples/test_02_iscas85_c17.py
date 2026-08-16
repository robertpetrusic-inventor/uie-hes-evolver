"""Exhaustive ISCAS85 c17 equivalence test.

c17 has five inputs, six 2-input NAND gates and two outputs.
We compare a scalar gate-by-gate evaluator with a bit-packed evaluator over all
2^5 = 32 input vectors. The bit-packed candidate must match exactly.
"""
from __future__ import annotations

from itertools import product

MASK32 = (1 << 32) - 1


def nand_bit(a: int, b: int) -> int:
    return 1 - (a & b)


def scalar_c17(n1: int, n2: int, n3: int, n6: int, n7: int) -> tuple[int, int]:
    n10 = nand_bit(n1, n3)
    n11 = nand_bit(n3, n6)
    n16 = nand_bit(n2, n11)
    n19 = nand_bit(n11, n7)
    n22 = nand_bit(n10, n16)
    n23 = nand_bit(n16, n19)
    return n22, n23


def nand_word(a: int, b: int) -> int:
    return (~(a & b)) & MASK32


def pack_inputs(vectors):
    cols = [0, 0, 0, 0, 0]
    for bit_index, row in enumerate(vectors):
        for col_index, value in enumerate(row):
            cols[col_index] |= (value & 1) << bit_index
    return cols


def bitpacked_c17(vectors):
    n1, n2, n3, n6, n7 = pack_inputs(vectors)
    n10 = nand_word(n1, n3)
    n11 = nand_word(n3, n6)
    n16 = nand_word(n2, n11)
    n19 = nand_word(n11, n7)
    n22 = nand_word(n10, n16)
    n23 = nand_word(n16, n19)
    return n22, n23


def main() -> None:
    vectors = list(product([0, 1], repeat=5))
    out22, out23 = bitpacked_c17(vectors)

    matches = 0
    for i, row in enumerate(vectors):
        expected = scalar_c17(*row)
        actual = ((out22 >> i) & 1, (out23 >> i) & 1)
        assert actual == expected, (row, expected, actual)
        matches += 1

    scalar_gate_dispatches = 6 * len(vectors)
    bitpacked_gate_dispatches = 6
    reduction = 1 - bitpacked_gate_dispatches / scalar_gate_dispatches

    print(f"vectors={len(vectors)} exact_matches={matches}/{len(vectors)}")
    print(f"scalar_gate_dispatches={scalar_gate_dispatches}")
    print(f"bitpacked_gate_dispatches={bitpacked_gate_dispatches}")
    print(f"dispatch_reduction={reduction:.3%}")

    assert matches == 32
    assert bitpacked_gate_dispatches == 6


if __name__ == "__main__":
    main()
