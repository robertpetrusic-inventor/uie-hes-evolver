from __future__ import annotations

from dataclasses import dataclass, asdict
from fractions import Fraction
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class ProgramGenome:
    """Small executable genome used by the starter evolver.

    `solve` is executable behavior. `static_cost` is an explicit model cost,
    not wall-clock time. `parent` and `mutation` preserve provenance.
    """

    name: str
    solve: Callable[[int], int]
    static_cost: int
    parent: str | None = None
    mutation: str = "seed"


@dataclass(frozen=True)
class GenomeResult:
    name: str
    parent: str | None
    mutation: str
    verified: bool
    correct: int
    total: int
    total_cost: int

    def to_dict(self) -> dict:
        return asdict(self)


def verify_genome(
    genome: ProgramGenome,
    cases: Iterable[int],
    oracle: Callable[[int], int],
) -> GenomeResult:
    correct = 0
    total = 0
    total_cost = 0
    for x in cases:
        total += 1
        actual = genome.solve(x)
        expected = oracle(x)
        correct += int(actual == expected)
        total_cost += genome.static_cost
    return GenomeResult(
        name=genome.name,
        parent=genome.parent,
        mutation=genome.mutation,
        verified=(correct == total),
        correct=correct,
        total=total,
        total_cost=total_cost,
    )


def select_promotable(parent: GenomeResult, children: Sequence[GenomeResult]) -> GenomeResult:
    """Correctness-first promotion: child must be exact and cheaper than parent."""
    verified = [c for c in children if c.verified and c.total_cost < parent.total_cost]
    if not verified:
        return parent
    return min(verified, key=lambda r: (r.total_cost, r.name))


def _solve_linear_system(matrix: list[list[Fraction]], rhs: list[Fraction]) -> list[Fraction]:
    """Exact Gauss-Jordan elimination for the tiny interpolation systems here."""
    n = len(rhs)
    aug = [row[:] + [rhs_i] for row, rhs_i in zip(matrix, rhs)]
    for col in range(n):
        pivot = next((r for r in range(col, n) if aug[r][col] != 0), None)
        if pivot is None:
            raise ValueError("Singular interpolation system")
        aug[col], aug[pivot] = aug[pivot], aug[col]
        div = aug[col][col]
        aug[col] = [v / div for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor:
                aug[r] = [a - factor * b for a, b in zip(aug[r], aug[col])]
    return [aug[i][-1] for i in range(n)]


def infer_polynomial_coefficients(
    parent: ProgramGenome,
    sample_x: Sequence[int],
    max_degree: int = 3,
) -> tuple[Fraction, ...]:
    """Infer exact polynomial coefficients from development I/O only."""
    if len(sample_x) < max_degree + 1:
        raise ValueError("Need at least max_degree + 1 distinct samples")

    xs = list(dict.fromkeys(sample_x))[: max_degree + 1]
    if len(xs) < max_degree + 1:
        raise ValueError("Samples must contain enough distinct x values")

    ys = [Fraction(parent.solve(x)) for x in xs]
    matrix = [[Fraction(x) ** p for p in range(max_degree + 1)] for x in xs]
    coeffs = _solve_linear_system(matrix, ys)
    while len(coeffs) > 1 and coeffs[-1] == 0:
        coeffs.pop()
    return tuple(coeffs)


def compile_polynomial_mutation(
    parent: ProgramGenome,
    coeffs: Sequence[Fraction],
) -> ProgramGenome:
    """Compile inferred coefficients into an executable Horner child."""
    coeffs = tuple(coeffs)

    def horner(x: int) -> int:
        value = coeffs[-1]
        for c in reversed(coeffs[:-1]):
            value = value * x + c
        if value.denominator != 1:
            raise ArithmeticError("Inferred polynomial produced a non-integer output")
        return value.numerator

    coeff_tag = ",".join(str(c) for c in coeffs)
    degree = len(coeffs) - 1
    static_cost = max(1, 2 * degree)
    return ProgramGenome(
        name=f"poly_horner_deg{degree}[{coeff_tag}]",
        solve=horner,
        static_cost=static_cost,
        parent=parent.name,
        mutation="infer_polynomial_horner",
    )


def infer_polynomial_mutation(
    parent: ProgramGenome,
    sample_x: Sequence[int],
    max_degree: int = 3,
) -> ProgramGenome:
    """Generate a polynomial child from observed parent behavior.

    This does not contain the target formula. It infers exact coefficients from
    parent I/O samples, then compiles them into a Horner evaluator. The frozen
    holdout remains unseen until verification.
    """
    coeffs = infer_polynomial_coefficients(parent, sample_x, max_degree=max_degree)
    return compile_polynomial_mutation(parent, coeffs)


def coefficient_perturbation_mutants(
    inferred: ProgramGenome,
    coefficients: Sequence[Fraction],
) -> list[ProgramGenome]:
    """Generate deliberately risky nearby mutants for verifier pressure testing."""
    mutants: list[ProgramGenome] = []
    for idx in range(len(coefficients)):
        for delta in (-1, 1):
            changed = list(coefficients)
            changed[idx] += delta

            def make_solver(coeffs: tuple[Fraction, ...]):
                def solve(x: int) -> int:
                    value = coeffs[-1]
                    for c in reversed(coeffs[:-1]):
                        value = value * x + c
                    if value.denominator != 1:
                        raise ArithmeticError("Non-integer mutant output")
                    return value.numerator
                return solve

            tag = ",".join(str(c) for c in changed)
            degree = len(changed) - 1
            mutants.append(
                ProgramGenome(
                    name=f"perturb_c{idx}_{delta:+d}[{tag}]",
                    solve=make_solver(tuple(changed)),
                    static_cost=max(1, 2 * degree),
                    parent=inferred.parent,
                    mutation=f"perturb_coefficient_{idx}_{delta:+d}",
                )
            )
    return mutants
