"""Real mutation -> verification -> promotion loop.

Seed program computes triangular numbers by iteration. The mutation operator is
not given the closed-form formula: it observes four development I/O samples,
infers an exact polynomial, compiles it with Horner evaluation, and then faces a
separate frozen holdout. Nearby coefficient mutants are generated too and must
be rejected by the verifier.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from uie_evolver.evolution import (
    ProgramGenome,
    coefficient_perturbation_mutants,
    compile_polynomial_mutation,
    infer_polynomial_coefficients,
    select_promotable,
    verify_genome,
)


def iterative_parent(n: int) -> int:
    if n < 0:
        raise ValueError("n must be non-negative")
    total = 0
    for k in range(1, n + 1):
        total += k
    return total


# Development data visible to the mutation generator.
DEV_SAMPLES = [0, 1, 2, 3]
# Frozen verification data is intentionally separate and includes large values.
FROZEN_HOLDOUT = [4, 7, 13, 31, 100, 999, 10_000, 100_000]


def main(write_result: bool = True) -> None:
    # Conservative worst-case cost model for the loop parent on this holdout:
    # one addition per k. We score total dynamic additions directly below.
    parent = ProgramGenome("iterative_sum", iterative_parent, static_cost=1)

    coeffs = infer_polynomial_coefficients(parent, DEV_SAMPLES, max_degree=3)
    inferred = compile_polynomial_mutation(parent, coeffs)
    children = [inferred] + coefficient_perturbation_mutants(inferred, coeffs)

    # Parent uses dynamic loop cost, child uses fixed compiled arithmetic cost.
    parent_correct = sum(iterative_parent(x) == iterative_parent(x) for x in FROZEN_HOLDOUT)
    parent_total_cost = sum(max(1, x) for x in FROZEN_HOLDOUT)
    from uie_evolver.evolution import GenomeResult
    parent_result = GenomeResult(
        name=parent.name,
        parent=None,
        mutation="seed",
        verified=(parent_correct == len(FROZEN_HOLDOUT)),
        correct=parent_correct,
        total=len(FROZEN_HOLDOUT),
        total_cost=parent_total_cost,
    )

    child_results = [verify_genome(c, FROZEN_HOLDOUT, iterative_parent) for c in children]
    winner = select_promotable(parent_result, child_results)

    print(f"parent={parent_result.name} verified={parent_result.verified} cost={parent_result.total_cost}")
    for r in child_results:
        print(
            f"child={r.name:38s} verified={str(r.verified):5s} "
            f"accuracy={r.correct}/{r.total} cost={r.total_cost}"
        )
    print(f"PROMOTED={winner.name}")

    assert inferred.parent == "iterative_sum"
    assert winner.name == inferred.name
    assert winner.verified
    assert all(not r.verified for r in child_results[1:])
    assert winner.total_cost < parent_result.total_cost

    if write_result:
        result = {
            "experiment": "mutation_evolver_triangular_v0.1",
            "development_samples": DEV_SAMPLES,
            "frozen_holdout": FROZEN_HOLDOUT,
            "parent": parent_result.to_dict(),
            "children": [r.to_dict() for r in child_results],
            "promoted": winner.to_dict(),
            "claim_scope": "behavior-preserving optimization demonstration; not an external math benchmark",
        }
        (ROOT / "results").mkdir(exist_ok=True)
        (ROOT / "results" / "mutation_evolver.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
