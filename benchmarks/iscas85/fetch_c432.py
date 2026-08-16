"""Fetch external ISCAS85 c432 sources and verify pinned SHA-256."""
from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent

FILES = {
    "c432.bench": (
        "https://pld.ttu.ee/~maksim/benchmarks/iscas85/bench/c432.bench",
        "c3a37ac6850aa737f2705f9f3868e1f4ccfa6a6cc1b1a21d3095ac73191e258d",
    ),
    "c432.v": (
        "https://pld.ttu.ee/~maksim/benchmarks/iscas85/verilog/c432.v",
        "5f57a91b4f2f2b4cacf47414e961a4c32aad915f961b116c379725f262690043",
    ),
}

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> None:
    for name, (url, expected) in FILES.items():
        target = HERE / name

        if target.exists() and digest(target.read_bytes()) == expected:
            print(f"{name}: cached SHA256 PASS")
            continue

        print(f"{name}: downloading")
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read()

        actual = digest(data)
        if actual != expected:
            raise RuntimeError(
                f"{name}: SHA256 mismatch: expected {expected}, got {actual}"
            )

        target.write_bytes(data)
        print(f"{name}: download SHA256 PASS")

if __name__ == "__main__":
    main()
