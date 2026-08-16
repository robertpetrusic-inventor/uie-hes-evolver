"""Independent verifier / regression-gate demonstration.

A candidate is not promoted merely because it is cheaper. It must preserve
all frozen parent outputs first.
"""
from __future__ import annotations


def parent_solver(n: int) -> int:
    # Sum 1..n, valid for n >= 0.
    return sum(range(n + 1))


def optimized_solver(n: int) -> int:
    return n * (n + 1) // 2


def broken_solver(n: int) -> int:
    # Common off-by-one mutation.
    return n * (n - 1) // 2


FROZEN_REGRESSION = [0, 1, 2, 3, 10, 99, 1000, 100_000]


def verify(candidate) -> tuple[bool, list[tuple[int, int, int]]]:
    failures = []
    for x in FROZEN_REGRESSION:
        expected = parent_solver(x)
        actual = candidate(x)
        if actual != expected:
            failures.append((x, expected, actual))
    return not failures, failures


def main() -> None:
    ok, failures = verify(optimized_solver)
    bad_ok, bad_failures = verify(broken_solver)

    print(f"optimized_solver: PASS={ok}, failures={len(failures)}")
    print(f"broken_solver:    PASS={bad_ok}, failures={len(bad_failures)}")

    assert ok
    assert not bad_ok
    assert bad_failures


if __name__ == "__main__":
    main()
