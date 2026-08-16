from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from uie_evolver.core import Candidate, evaluate, select_verified_min_cost


def test_correctness_first_selection():
    cases = [0, 1, 2, 10]
    oracle = lambda x: x + 1
    candidates = [
        Candidate("slow_correct", lambda x: x + 1, lambda _x: 5),
        Candidate("fast_correct", lambda x: 1 + x, lambda _x: 1),
        Candidate("fast_wrong", lambda x: x, lambda _x: 0),
    ]
    evals = [evaluate(c, cases, oracle) for c in candidates]
    winner = select_verified_min_cost(evals)
    assert winner.name == "fast_correct"
