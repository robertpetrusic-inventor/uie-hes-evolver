from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from uie_evolver.evolution import ProgramGenome, infer_polynomial_mutation, verify_genome


def test_inferred_polynomial_generalizes_to_frozen_holdout():
    def parent(n: int) -> int:
        return sum(range(n + 1))

    seed = ProgramGenome("loop", parent, 1)
    child = infer_polynomial_mutation(seed, [0, 1, 2, 3], max_degree=3)
    result = verify_genome(child, [4, 7, 50, 1000], parent)
    assert result.verified
    assert child.parent == "loop"
    assert child.mutation == "infer_polynomial_horner"
