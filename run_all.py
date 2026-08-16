from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROGRAMS = [
    ROOT / "examples" / "test_01_evolver_math.py",
    ROOT / "examples" / "test_02_iscas85_c17.py",
    ROOT / "examples" / "test_03_verifier_regression.py",
    ROOT / "examples" / "test_04_mutation_evolver.py",
    ROOT / "examples" / "test_05_eight_puzzle.py",
]


def main() -> None:
    for program in PROGRAMS:
        print(f"\n=== {program.name} ===", flush=True)
        subprocess.run([sys.executable, str(program)], check=True)
    print("\nALL TEST PROGRAMS PASSED")


if __name__ == "__main__":
    main()
