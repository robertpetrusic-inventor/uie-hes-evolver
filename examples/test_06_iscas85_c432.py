"""ISCAS85 c432 cross-format verification.

Three paths:
1. Verilog scalar reference parser/evaluator.
2. BENCH scalar parser/evaluator.
3. BENCH bit-packed evaluator.

The benchmark files are hash-pinned. No optimization/promotion is accepted
unless all representations agree exactly on the frozen verification set.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import subprocess
import sys
from functools import reduce
from operator import and_, xor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "iscas85" / "c432.bench"
VERILOG = ROOT / "benchmarks" / "iscas85" / "c432.v"
RESULT = ROOT / "results" / "iscas85_c432.json"
FETCHER = ROOT / "benchmarks" / "iscas85" / "fetch_c432.py"

EXPECTED_SHA256 = {
    BENCH.name: "c3a37ac6850aa737f2705f9f3868e1f4ccfa6a6cc1b1a21d3095ac73191e258d",
    VERILOG.name: "5f57a91b4f2f2b4cacf47414e961a4c32aad915f961b116c379725f262690043",
}

Gate = tuple[str, str, tuple[str, ...]]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(name: str) -> str:
    name = name.strip()
    return name if name.startswith("N") else f"N{name}"


def parse_bench(path: Path) -> tuple[list[str], list[str], list[Gate]]:
    inputs: list[str] = []
    outputs: list[str] = []
    gates: list[Gate] = []

    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue

        m = re.fullmatch(r"INPUT\(([^)]+)\)", line)
        if m:
            inputs.append(normalize(m.group(1)))
            continue

        m = re.fullmatch(r"OUTPUT\(([^)]+)\)", line)
        if m:
            outputs.append(normalize(m.group(1)))
            continue

        m = re.fullmatch(
            r"([A-Za-z0-9_]+)\s*=\s*([A-Za-z]+)\(([^)]*)\)", line
        )
        if m:
            out = normalize(m.group(1))
            op = m.group(2).upper()
            args = tuple(normalize(x) for x in m.group(3).split(","))
            gates.append((out, op, args))
            continue

        raise ValueError(f"Unparsed BENCH line: {raw!r}")

    return inputs, outputs, gates


def parse_verilog(path: Path) -> tuple[list[str], list[str], list[Gate]]:
    text = path.read_text()
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)

    input_match = re.search(r"\binput\s+([^;]+);", text, flags=re.DOTALL)
    output_match = re.search(r"\boutput\s+([^;]+);", text, flags=re.DOTALL)

    if not input_match or not output_match:
        raise ValueError("Missing Verilog input/output declarations")

    def names(block: str) -> list[str]:
        return [x.strip() for x in block.replace("\n", " ").split(",") if x.strip()]

    inputs = names(input_match.group(1))
    outputs = names(output_match.group(1))

    gate_re = re.compile(
        r"\b(not|nand|nor|and|xor)\s+\w+\s*\(([^;]+)\)\s*;",
        flags=re.IGNORECASE,
    )

    gates: list[Gate] = []
    for match in gate_re.finditer(text):
        op = match.group(1).upper()
        pins = tuple(x.strip() for x in match.group(2).split(","))
        gates.append((pins[0], op, pins[1:]))

    return inputs, outputs, gates


def scalar_gate(op: str, xs: tuple[int, ...]) -> int:
    if op == "NOT":
        return 1 - xs[0]
    if op == "AND":
        return int(all(xs))
    if op == "NAND":
        return 1 - int(all(xs))
    if op == "NOR":
        return 1 - int(any(xs))
    if op == "XOR":
        return reduce(xor, xs, 0)
    raise ValueError(op)


def scalar_eval(
    gates: list[Gate],
    inputs: list[str],
    outputs: list[str],
    vector: tuple[int, ...],
) -> tuple[int, ...]:
    values = dict(zip(inputs, vector))

    for out, op, args in gates:
        values[out] = scalar_gate(op, tuple(values[x] for x in args))

    return tuple(values[x] for x in outputs)


def bitpacked_eval(
    gates: list[Gate],
    inputs: list[str],
    outputs: list[str],
    vectors: list[tuple[int, ...]],
) -> tuple[int, ...]:
    n = len(vectors)
    mask = (1 << n) - 1
    values = {name: 0 for name in inputs}

    for bit_index, row in enumerate(vectors):
        for input_index, value in enumerate(row):
            if value:
                values[inputs[input_index]] |= 1 << bit_index

    for out, op, args in gates:
        xs = tuple(values[x] for x in args)

        if op == "NOT":
            value = (~xs[0]) & mask
        elif op == "AND":
            value = reduce(and_, xs, mask)
        elif op == "NAND":
            value = (~reduce(and_, xs, mask)) & mask
        elif op == "NOR":
            value = (~reduce(lambda a, b: a | b, xs, 0)) & mask
        elif op == "XOR":
            value = reduce(xor, xs, 0) & mask
        else:
            raise ValueError(op)

        values[out] = value

    return tuple(values[x] for x in outputs)


def frozen_vectors(width: int, count: int = 8192) -> list[tuple[int, ...]]:
    mask = (1 << width) - 1
    integers: list[int] = []
    seen: set[int] = set()

    def add(value: int) -> None:
        value &= mask
        if value not in seen:
            seen.add(value)
            integers.append(value)

    add(0)
    add(mask)
    add(int("10" * (width // 2), 2))
    add(int("01" * (width // 2), 2))

    for i in range(width):
        add(1 << i)
        add(mask ^ (1 << i))

    rng = random.Random(432_2026)
    while len(integers) < count:
        add(rng.getrandbits(width))

    return [
        tuple((value >> bit) & 1 for bit in range(width))
        for value in integers[:count]
    ]


def main() -> None:
    if not BENCH.exists() or not VERILOG.exists():
        subprocess.run([sys.executable, str(FETCHER)], check=True)

    actual_hashes = {
        BENCH.name: sha256(BENCH),
        VERILOG.name: sha256(VERILOG),
    }
    assert actual_hashes == EXPECTED_SHA256, (
        "Benchmark provenance/hash failure",
        actual_hashes,
    )

    b_inputs, b_outputs, b_gates = parse_bench(BENCH)
    v_inputs, v_outputs, v_gates = parse_verilog(VERILOG)

    assert len(b_inputs) == len(v_inputs) == 36
    assert len(b_outputs) == len(v_outputs) == 7
    assert len(b_gates) == len(v_gates) == 160

    assert b_inputs == v_inputs
    assert b_outputs == v_outputs

    structural_exact = b_gates == v_gates
    assert structural_exact

    vectors = frozen_vectors(len(v_inputs), 8192)

    packed_outputs = bitpacked_eval(
        b_gates, b_inputs, b_outputs, vectors
    )

    scalar_matches = 0
    packed_matches = 0

    for i, vector in enumerate(vectors):
        verilog_ref = scalar_eval(
            v_gates, v_inputs, v_outputs, vector
        )
        bench_scalar = scalar_eval(
            b_gates, b_inputs, b_outputs, vector
        )
        bench_packed = tuple(
            (word >> i) & 1 for word in packed_outputs
        )

        assert bench_scalar == verilog_ref, (
            "BENCH/Verilog mismatch",
            i,
            vector,
            verilog_ref,
            bench_scalar,
        )
        assert bench_packed == verilog_ref, (
            "Bit-packed mismatch",
            i,
            vector,
            verilog_ref,
            bench_packed,
        )

        scalar_matches += 1
        packed_matches += 1

    scalar_dispatches = len(vectors) * len(v_gates)
    bitpacked_dispatches = len(b_gates)
    reduction = 1 - bitpacked_dispatches / scalar_dispatches

    result = {
        "benchmark": "ISCAS85 c432",
        "inputs": len(v_inputs),
        "outputs": len(v_outputs),
        "gates": len(v_gates),
        "verification_vectors": len(vectors),
        "bench_vs_verilog_exact": scalar_matches,
        "bitpacked_vs_verilog_exact": packed_matches,
        "structural_cross_format_exact": structural_exact,
        "scalar_gate_dispatches": scalar_dispatches,
        "bitpacked_gate_dispatches": bitpacked_dispatches,
        "modeled_dispatch_reduction": reduction,
        "sha256": actual_hashes,
    }

    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    print("benchmark=ISCAS85_c432")
    print(
        f"inputs={len(v_inputs)} outputs={len(v_outputs)} "
        f"gates={len(v_gates)}"
    )
    print(f"sha256_gate=PASS")
    print(f"cross_format_structure=PASS")
    print(
        f"bench_vs_verilog={scalar_matches}/{len(vectors)} PASS"
    )
    print(
        f"bitpacked_vs_verilog={packed_matches}/{len(vectors)} PASS"
    )
    print(f"scalar_gate_dispatches={scalar_dispatches}")
    print(f"bitpacked_gate_dispatches={bitpacked_dispatches}")
    print(f"modeled_dispatch_reduction={reduction:.6%}")


if __name__ == "__main__":
    main()
