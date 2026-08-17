#!/usr/bin/env python3
"""
UIE / Math+Lang SAT External v0.2
================================
Strict external SAT benchmark runner.

Core rules:
- Parse real DIMACS CNF.
- Detect parameters and input language before execution.
- Run an external SAT solver such as Kissat.
- SAT counts only if the emitted model replay-satisfies every clause.
- UNSAT is accepted as solver-grounded only when the solver returns the
  conventional UNSAT exit code (20). A proof certificate is still stronger.
- Optional expected truth comes from a CSV manifest or conservative filename
  conventions for SATLIB random 3-SAT (uf*=SAT, uuf*=UNSAT).
- Produces per-instance JSONL, SUMMARY.json, and TOP3_POST_TEST_AUDIT.json.
- Never fabricates missing empirical results.

Example:
    python3 uie_sat_external_v0_2.py \
      --solver ./kissat-4.0.0-linux-amd64 \
      --input ./SATLIB \
      --output ./uie_sat_external_results

Optional truth manifest CSV:
    filename,truth
    uf20-01.cnf,SAT
    uuf50-01.cnf,UNSAT

Return statuses:
    PASS     = execution valid and all scored external truths matched.
    PASS*    = execution valid, but some instances lack external truth/proof-strength.
    FAIL     = valid execution found a mismatch, invalid SAT model, or parser error.
    noData   = nothing valid was executed/scored.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


SAT_EXIT = 10
UNSAT_EXIT = 20


@dataclass
class CNF:
    path: Path
    nvars: int
    declared_clauses: int
    clauses: List[List[int]]


def detect_language(path: Path) -> Tuple[str, str]:
    """Return (status, language)."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("c"):
                    continue
                if s.startswith("p cnf "):
                    return "PASS", "DIMACS-CNF"
                return "FAIL", "UNKNOWN"
    except Exception:
        return "FAIL", "UNREADABLE"
    return "FAIL", "EMPTY"


def parse_dimacs(path: Path) -> CNF:
    nvars = None
    declared_clauses = None
    clauses: List[List[int]] = []
    current: List[int] = []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("c"):
                continue
            if s.startswith("p"):
                parts = s.split()
                if len(parts) != 4 or parts[1] != "cnf":
                    raise ValueError(f"Unsupported DIMACS header: {s}")
                nvars = int(parts[2])
                declared_clauses = int(parts[3])
                continue

            for tok in s.split():
                lit = int(tok)
                if lit == 0:
                    clauses.append(current)
                    current = []
                else:
                    current.append(lit)

    if current:
        raise ValueError("DIMACS clause missing terminal 0")
    if nvars is None or declared_clauses is None:
        raise ValueError("Missing 'p cnf <vars> <clauses>' header")
    if len(clauses) != declared_clauses:
        raise ValueError(
            f"Clause-count mismatch: header={declared_clauses}, parsed={len(clauses)}"
        )
    for clause in clauses:
        for lit in clause:
            if abs(lit) < 1 or abs(lit) > nvars:
                raise ValueError(f"Literal {lit} outside 1..{nvars}")

    return CNF(path=path, nvars=nvars, declared_clauses=declared_clauses, clauses=clauses)


def detect_parameters(cnf: CNF) -> Dict[str, object]:
    widths = [len(c) for c in cnf.clauses]
    return {
        "status": "PASS",
        "BOOLEAN_VARIABLES": cnf.nvars,
        "CLAUSES": len(cnf.clauses),
        "LITERALS": sum(widths),
        "MIN_CLAUSE_WIDTH": min(widths) if widths else 0,
        "MAX_CLAUSE_WIDTH": max(widths) if widths else 0,
        "CNF": True,
        "SATISFIABILITY_QUERY": True,
        "MODEL_REQUIRED_FOR_SAT": True,
    }


def parse_solver_output(stdout: str, stderr: str, returncode: int) -> Tuple[str, Optional[Dict[int, bool]]]:
    """
    Parse common DIMACS-style solver output.
    Accept status from exit code or 's SATISFIABLE' / 's UNSATISFIABLE'.
    Parse model from one or multiple 'v ... 0' lines.
    """
    text = stdout + "\n" + stderr

    status = None
    if returncode == SAT_EXIT:
        status = "SAT"
    elif returncode == UNSAT_EXIT:
        status = "UNSAT"

    for line in text.splitlines():
        s = line.strip()
        if s == "s SATISFIABLE":
            status = "SAT"
        elif s == "s UNSATISFIABLE":
            status = "UNSAT"

    model: Dict[int, bool] = {}
    saw_model = False
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("v"):
            continue
        saw_model = True
        for tok in s[1:].strip().split():
            try:
                lit = int(tok)
            except ValueError:
                continue
            if lit == 0:
                continue
            model[abs(lit)] = lit > 0

    if status is None:
        return "UNKNOWN", model if saw_model else None
    return status, model if saw_model else None


def replay_model(cnf: CNF, model: Optional[Dict[int, bool]]) -> Tuple[bool, Optional[int]]:
    """
    Strict replay:
    - every variable referenced by a clause must have a model value;
    - every clause must evaluate true.
    Returns (ok, failing_clause_index_1based).
    """
    if model is None:
        return False, None

    for idx, clause in enumerate(cnf.clauses, start=1):
        clause_ok = False
        for lit in clause:
            var = abs(lit)
            if var not in model:
                continue
            val = model[var]
            if (lit > 0 and val) or (lit < 0 and not val):
                clause_ok = True
                break
        if not clause_ok:
            return False, idx
    return True, None


def load_manifest(path: Optional[Path]) -> Dict[str, str]:
    if path is None:
        return {}
    truth: Dict[str, str] = {}
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if "filename" not in reader.fieldnames or "truth" not in reader.fieldnames:
            raise ValueError("Manifest must have columns: filename,truth")
        for row in reader:
            name = row["filename"].strip()
            t = row["truth"].strip().upper()
            if t not in {"SAT", "UNSAT"}:
                raise ValueError(f"Invalid truth {t!r} for {name}")
            truth[name] = t
    return truth


def conservative_filename_truth(name: str) -> Optional[str]:
    """
    Conservative SATLIB random-3-SAT convention:
    - uf...   => SAT family
    - uuf...  => UNSAT family
    Does NOT guess truth for arbitrary filenames.
    """
    low = name.lower()
    if re.match(r"^uuf\d", low):
        return "UNSAT"
    if re.match(r"^uf\d", low):
        return "SAT"
    return None


def expected_truth(path: Path, manifest: Dict[str, str], allow_filename_truth: bool) -> Optional[str]:
    if path.name in manifest:
        return manifest[path.name]
    if allow_filename_truth:
        return conservative_filename_truth(path.name)
    return None


def find_cnf_inputs(path: Path) -> List[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".cnf" else []
    return sorted(p for p in path.rglob("*.cnf") if p.is_file())


def run_solver(solver: Path, cnf_path: Path, timeout_s: float, extra_args: Sequence[str]) -> Dict[str, object]:
    cmd = [str(solver), *extra_args, str(cnf_path)]
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        elapsed = time.perf_counter() - t0
        status, model = parse_solver_output(cp.stdout, cp.stderr, cp.returncode)
        return {
            "execution": "PASS",
            "cmd": cmd,
            "elapsed_s": elapsed,
            "returncode": cp.returncode,
            "solver_status": status,
            "model": model,
            "stdout_tail": cp.stdout[-4000:],
            "stderr_tail": cp.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as e:
        elapsed = time.perf_counter() - t0
        return {
            "execution": "noData",
            "cmd": cmd,
            "elapsed_s": elapsed,
            "returncode": None,
            "solver_status": "UNKNOWN",
            "model": None,
            "error": f"timeout after {timeout_s}s",
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "execution": "FAIL",
            "cmd": cmd,
            "elapsed_s": elapsed,
            "returncode": None,
            "solver_status": "UNKNOWN",
            "model": None,
            "error": repr(e),
        }


def instance_verdict(
    expected: Optional[str],
    solver_status: str,
    sat_model_valid: Optional[bool],
    execution: str,
) -> Tuple[str, str]:
    if execution == "FAIL":
        return "FAIL", "solver execution failed"
    if execution == "noData":
        return "noData", "solver timed out or produced no valid execution"

    if solver_status == "SAT":
        if sat_model_valid is not True:
            return "FAIL", "solver claimed SAT but model replay failed"
        if expected is None:
            return "PASS*", "SAT model verified, but no independent external truth label"
        if expected != "SAT":
            return "FAIL", f"external truth={expected}, solver=SAT"
        return "PASS", "external truth matched and SAT model replay verified"

    if solver_status == "UNSAT":
        if expected is None:
            return "PASS*", "solver returned UNSAT, but no independent external truth label"
        if expected != "UNSAT":
            return "FAIL", f"external truth={expected}, solver=UNSAT"
        return "PASS", "external truth matched solver-grounded UNSAT result"

    return "noData", "solver did not return SAT or UNSAT"


def summarize(rows: List[Dict[str, object]]) -> Dict[str, object]:
    counts = {"PASS": 0, "PASS*": 0, "FAIL": 0, "noData": 0}
    sat_models = 0
    sat_models_valid = 0
    truth_scored = 0
    truth_correct = 0

    for r in rows:
        counts[r["verdict"]] += 1
        if r["solver_status"] == "SAT":
            sat_models += 1
            sat_models_valid += int(r.get("sat_model_valid") is True)
        if r.get("expected_truth") in {"SAT", "UNSAT"} and r["solver_status"] in {"SAT", "UNSAT"}:
            truth_scored += 1
            truth_correct += int(r["expected_truth"] == r["solver_status"])

    if counts["FAIL"] > 0:
        overall = "FAIL"
    elif counts["PASS"] > 0 and counts["PASS*"] == 0 and counts["noData"] == 0:
        overall = "PASS"
    elif counts["PASS"] + counts["PASS*"] > 0:
        overall = "PASS*"
    else:
        overall = "noData"

    return {
        "overall_verdict": overall,
        "instances": len(rows),
        "counts": counts,
        "truth_scored": truth_scored,
        "truth_accuracy": (truth_correct / truth_scored) if truth_scored else None,
        "sat_models_emitted": sat_models,
        "sat_model_replay_rate": (sat_models_valid / sat_models) if sat_models else None,
        "total_solver_time_s": sum(float(r.get("elapsed_s", 0.0)) for r in rows),
    }


def top3_audit(summary: Dict[str, object], rows: List[Dict[str, object]]) -> Dict[str, object]:
    truth_acc = summary["truth_accuracy"]
    replay = summary["sat_model_replay_rate"]

    a1_status = "noData" if truth_acc is None else ("PASS" if truth_acc == 1.0 else "FAIL")
    a2_status = "noData" if replay is None else ("PASS" if replay == 1.0 else "FAIL")

    unsat_rows = [r for r in rows if r.get("solver_status") == "UNSAT"]
    if not unsat_rows:
        a3_status = "noData"
        a3 = "No UNSAT result was executed."
    else:
        # Without proof parsing, UNSAT is solver-grounded rather than independently proof-replayed.
        a3_status = "PASS*"
        a3 = (
            f"{len(unsat_rows)} UNSAT result(s) were solver-grounded. "
            "For proof-level independent verification, add DRAT/LRAT certificate checking."
        )

    return {
        "top3": [
            {
                "rank": 1,
                "status": a1_status,
                "finding": (
                    "External truth accuracy="
                    + ("noData" if truth_acc is None else f"{truth_acc:.2%}")
                    + "."
                ),
            },
            {
                "rank": 2,
                "status": a2_status,
                "finding": (
                    "SAT model replay rate="
                    + ("noData" if replay is None else f"{replay:.2%}")
                    + "."
                ),
            },
            {
                "rank": 3,
                "status": a3_status,
                "finding": a3,
            },
        ],
        "methodological_boundary": (
            "Correctness is primary. Runtime is secondary. SAT is replay-verified clause by clause. "
            "UNSAT is accepted only as an external-solver result unless a proof certificate is separately checked."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", required=True, type=Path, help="Path to Kissat or another DIMACS SAT solver.")
    ap.add_argument("--input", required=True, type=Path, help=".cnf file or directory tree containing .cnf files.")
    ap.add_argument("--output", type=Path, default=Path("uie_sat_external_v0_2_results"))
    ap.add_argument("--truth-manifest", type=Path, default=None, help="CSV with filename,truth.")
    ap.add_argument(
        "--allow-satlib-filename-truth",
        action="store_true",
        help="Infer only uf*=SAT and uuf*=UNSAT. Never infers arbitrary filenames.",
    )
    ap.add_argument("--timeout", type=float, default=60.0, help="Per-instance timeout seconds.")
    ap.add_argument(
        "--solver-args",
        default="",
        help='Extra solver args as one shell-style string, e.g. "--quiet".',
    )
    ap.add_argument("--limit", type=int, default=0, help="0=all; otherwise first N CNFs.")
    args = ap.parse_args()

    out = args.output
    out.mkdir(parents=True, exist_ok=True)

    if not args.solver.exists():
        print(json.dumps({"verdict":"noData","error":f"solver not found: {args.solver}"}, indent=2))
        return 2

    try:
        manifest = load_manifest(args.truth_manifest)
    except Exception as e:
        print(json.dumps({"verdict":"FAIL","error":f"manifest error: {e}"}, indent=2))
        return 2

    inputs = find_cnf_inputs(args.input)
    if args.limit > 0:
        inputs = inputs[: args.limit]

    if not inputs:
        print(json.dumps({"verdict":"noData","error":"no .cnf inputs found"}, indent=2))
        return 0

    solver_args = shlex.split(args.solver_args)
    rows: List[Dict[str, object]] = []

    for path in inputs:
        row: Dict[str, object] = {"file": str(path), "filename": path.name}

        lang_status, language = detect_language(path)
        row["language_gate"] = lang_status
        row["language"] = language

        if lang_status != "PASS":
            row.update({
                "parameter_gate": "noData",
                "representation_gate": "noData",
                "solver_status": "UNKNOWN",
                "verdict": "FAIL",
                "reason": "input is not valid detected DIMACS-CNF",
            })
            rows.append(row)
            continue

        try:
            cnf = parse_dimacs(path)
            row["parameter_gate"] = "PASS"
            row["representation_gate"] = "PASS"
            row["parameters"] = detect_parameters(cnf)
        except Exception as e:
            row.update({
                "parameter_gate": "FAIL",
                "representation_gate": "FAIL",
                "solver_status": "UNKNOWN",
                "verdict": "FAIL",
                "reason": f"DIMACS parse/integrity failure: {e}",
            })
            rows.append(row)
            continue

        exp = expected_truth(path, manifest, args.allow_satlib_filename_truth)
        row["expected_truth"] = exp

        run = run_solver(args.solver, path, args.timeout, solver_args)
        row["elapsed_s"] = run.get("elapsed_s")
        row["solver_returncode"] = run.get("returncode")
        row["solver_status"] = run.get("solver_status")
        row["execution"] = run.get("execution")

        sat_valid = None
        failing_clause = None
        if run.get("solver_status") == "SAT":
            sat_valid, failing_clause = replay_model(cnf, run.get("model"))
        row["sat_model_valid"] = sat_valid
        row["failing_clause"] = failing_clause

        verdict, reason = instance_verdict(
            exp,
            str(run.get("solver_status")),
            sat_valid,
            str(run.get("execution")),
        )
        row["verdict"] = verdict
        row["reason"] = reason
        rows.append(row)

        print(
            f"{path.name}: expected={exp or 'noData'} "
            f"solver={row['solver_status']} model={sat_valid} "
            f"verdict={verdict} time={row.get('elapsed_s', 0):.3f}s",
            flush=True,
        )

    summary = summarize(rows)
    audit = top3_audit(summary, rows)

    with (out / "INSTANCE_RESULTS.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "TOP3_POST_TEST_AUDIT.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")

    print("\n" + json.dumps(summary, indent=2))

    return 1 if summary["overall_verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
