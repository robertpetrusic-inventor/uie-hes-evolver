#!/usr/bin/env python3
"""Run Logic and Chess in deterministic, sequential, isolated subprocesses."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def clean_environment() -> dict[str, str]:
    allowed = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR") if key in os.environ}
    return {
        **allowed,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "LC_ALL": "C",
        "LANG": "C",
        "TZ": "UTC",
    }


def run_phase(script: str, *arguments: str) -> None:
    subprocess.run(
        [sys.executable, "-I", "-B", str(ROOT / script), *arguments],
        cwd=ROOT,
        env=clean_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "clean_loop_result.json",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="chess_logic_clean_") as temp_dir:
        temp = Path(temp_dir)
        logic_lock = temp / "logic_lock.json"
        chess_result = temp / "chess_result.json"
        run_phase("logic_phase.py", "--output", str(logic_lock))
        run_phase(
            "chess_phase.py",
            "--logic-lock",
            str(logic_lock),
            "--output",
            str(chess_result),
        )
        lock = json.loads(logic_lock.read_text(encoding="utf-8"))
        chess = json.loads(chess_result.read_text(encoding="utf-8"))

    final = {
        "architecture": "A_HIERARCHICAL_LOGIC_THEN_CHESS",
        "execution_order": ["LOGIC_ONLY_PROCESS", "FROZEN_HASH_LOCK", "CHESS_ONLY_PROCESS", "POST_HASH_CHECK"],
        "separate_processes": True,
        "shared_mutable_memory": False,
        "deterministic_environment": True,
        "logic": lock,
        "chess": chess,
        "clean_loop_pass": bool(
            lock["certificate"]["locked"]
            and lock["no_chess_imports"]
            and chess["no_logic_backflow"]
            and chess["chess_smoke"]["passed"] == chess["chess_smoke"]["total"]
        ),
    }
    args.output.write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(final, indent=2))
    return 0 if final["clean_loop_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

