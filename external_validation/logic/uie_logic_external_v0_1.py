#!/usr/bin/env python3
"""
UIE / Math+Lang Logic External v0.1
===================================
Independent formal-logic benchmark runner for TPTP problems.

Purpose
-------
Provide a logic test independent from SAT/CNF-only benchmarking.

Method
------
1. Detect TPTP language (FOF/TFF/CNF/THF).
2. Detect expected TPTP status from problem header when available.
3. Run Vampire (or another prover producing SZS status lines).
4. Parse SZS status.
5. Compare prover result to external TPTP truth.
6. Return PASS / PASS* / FAIL / noData.
7. Produce TOP3_POST_TEST_AUDIT.json.

Important methodological limits
-------------------------------
- A theorem prover saying "Theorem" is solver-grounded evidence.
- Full proof-level independent verification requires separately checking a proof object.
- If no external truth is available, a solved instance can be at most PASS*.
- Unknown / timeout is noData, not FAIL, unless an expected result was contradicted.
- Runtime is secondary to correctness.

Example
-------
python3 uie_logic_external_v0_1.py \
    --prover ./vampire \
    --input ./TPTP/Problems \
    --output ./uie_logic_external_results \
    --timeout 30 \
    --limit 100
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


# Common TPTP problem statuses and their corresponding expected SZS solution classes.
# We keep the mapping conservative.
THEOREM_LIKE = {
    "Theorem", "Unsatisfiable", "ContradictoryAxioms"
}
COUNTER_LIKE = {
    "CounterSatisfiable", "Satisfiable"
}
UNKNOWN_LIKE = {
    "Unknown", "Open"
}

SUPPORTED_LANGS = {"fof", "tff", "cnf", "thf"}


def read_head(path: Path, max_lines: int = 120) -> List[str]:
    lines = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            lines.append(line.rstrip("\n"))
            if i + 1 >= max_lines:
                break
    return lines


def detect_tptp_language(path: Path) -> Tuple[str, Optional[str]]:
    try:
        text = "\n".join(read_head(path, 200)).lower()
    except Exception:
        return "FAIL", None

    found = []
    for lang in SUPPORTED_LANGS:
        if re.search(rf"\b{lang}\s*\(", text):
            found.append(lang)

    if not found:
        return "FAIL", None

    # Mixed include files are possible; use the first recognized top-level language family.
    return "PASS", sorted(found)[0].upper()


def detect_parameters(path: Path) -> Dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    counts = {}
    for lang in SUPPORTED_LANGS:
        counts[lang.upper()] = len(re.findall(rf"\b{lang}\s*\(", text, flags=re.IGNORECASE))
    roles = {}
    for role in [
        "axiom", "hypothesis", "definition", "assumption", "lemma",
        "theorem", "corollary", "conjecture", "negated_conjecture",
        "plain", "type"
    ]:
        roles[role] = len(re.findall(rf",\s*{role}\s*,", text, flags=re.IGNORECASE))

    return {
        "status": "PASS",
        "formula_counts": counts,
        "role_counts": roles,
        "has_conjecture": roles["conjecture"] > 0 or roles["negated_conjecture"] > 0,
        "logic_task": True,
    }


def expected_status_from_header(path: Path) -> Optional[str]:
    """
    Parse standard TPTP header line such as:
      % Status   : Theorem
    """
    for line in read_head(path, 160):
        m = re.match(r"\s*%\s*Status\s*:\s*([A-Za-z_]+)", line)
        if m:
            return m.group(1)
    return None


def normalize_expected(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    if raw in THEOREM_LIKE:
        return "THEOREM"
    if raw in COUNTER_LIKE:
        return "COUNTER"
    if raw in UNKNOWN_LIKE:
        return "UNKNOWN"
    return raw.upper()


def parse_szs_status(text: str) -> Optional[str]:
    """
    Parse SZS status lines such as:
      % SZS status Theorem for ...
      % SZS status CounterSatisfiable for ...
      % SZS status Unsatisfiable for ...
    """
    statuses = []
    for line in text.splitlines():
        m = re.search(r"SZS\s+status\s+([A-Za-z_]+)", line, flags=re.IGNORECASE)
        if m:
            statuses.append(m.group(1))

    if not statuses:
        return None

    # Prefer the last SZS status printed by the prover.
    return statuses[-1]


def normalize_prover_status(raw: Optional[str]) -> str:
    if raw is None:
        return "UNKNOWN"
    if raw in THEOREM_LIKE:
        return "THEOREM"
    if raw in COUNTER_LIKE:
        return "COUNTER"
    if raw in UNKNOWN_LIKE:
        return "UNKNOWN"
    return raw.upper()


def run_prover(
    prover: Path,
    problem: Path,
    timeout_s: float,
    extra_args: Sequence[str],
) -> Dict[str, object]:
    cmd = [str(prover), *extra_args, str(problem)]
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
        combined = cp.stdout + "\n" + cp.stderr
        raw_status = parse_szs_status(combined)
        return {
            "execution": "PASS",
            "elapsed_s": elapsed,
            "returncode": cp.returncode,
            "raw_status": raw_status,
            "normalized_status": normalize_prover_status(raw_status),
            "stdout_tail": cp.stdout[-5000:],
            "stderr_tail": cp.stderr[-5000:],
            "cmd": cmd,
        }
    except subprocess.TimeoutExpired:
        return {
            "execution": "noData",
            "elapsed_s": time.perf_counter() - t0,
            "returncode": None,
            "raw_status": None,
            "normalized_status": "UNKNOWN",
            "error": f"timeout after {timeout_s}s",
            "cmd": cmd,
        }
    except Exception as e:
        return {
            "execution": "FAIL",
            "elapsed_s": time.perf_counter() - t0,
            "returncode": None,
            "raw_status": None,
            "normalized_status": "UNKNOWN",
            "error": repr(e),
            "cmd": cmd,
        }


def classify_instance(
    expected: Optional[str],
    got: str,
    execution: str,
) -> Tuple[str, str]:
    if execution == "FAIL":
        return "FAIL", "prover execution failed"
    if execution == "noData":
        return "noData", "timeout / no completed prover result"

    if got == "UNKNOWN":
        return "noData", "prover returned no decisive SZS result"

    if expected is None:
        return "PASS*", "decisive prover result, but no external TPTP status found"

    if expected == "UNKNOWN":
        return "PASS*", f"external status is {expected}; prover returned {got}"

    if expected == got:
        return "PASS", f"external TPTP status matched: {got}"

    return "FAIL", f"external truth={expected}, prover={got}"


def collect_inputs(root: Path) -> List[Path]:
    if root.is_file():
        return [root]
    # TPTP problems typically use .p
    return sorted(p for p in root.rglob("*.p") if p.is_file())


def summarize(rows: List[Dict[str, object]]) -> Dict[str, object]:
    counts = {"PASS": 0, "PASS*": 0, "FAIL": 0, "noData": 0}
    truth_scored = 0
    truth_correct = 0
    solved = 0

    for r in rows:
        counts[r["verdict"]] += 1
        got = r.get("prover_status")
        exp = r.get("expected_status")
        if got in {"THEOREM", "COUNTER"}:
            solved += 1
        if exp in {"THEOREM", "COUNTER"} and got in {"THEOREM", "COUNTER"}:
            truth_scored += 1
            truth_correct += int(exp == got)

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
        "decisive_solved": solved,
        "solve_rate": solved / len(rows) if rows else None,
        "truth_scored": truth_scored,
        "truth_accuracy": truth_correct / truth_scored if truth_scored else None,
        "total_prover_time_s": sum(float(r.get("elapsed_s", 0.0)) for r in rows),
    }


def top3_audit(summary: Dict[str, object], rows: List[Dict[str, object]]) -> Dict[str, object]:
    ta = summary["truth_accuracy"]
    sr = summary["solve_rate"]

    a1_status = "noData" if ta is None else ("PASS" if ta == 1.0 else "FAIL")
    a2_status = "noData" if sr is None else ("PASS" if sr == 1.0 else "PASS*")

    unsupported = sum(1 for r in rows if r.get("language_gate") != "PASS")
    a3_status = "PASS" if unsupported == 0 else "FAIL"

    return {
        "top3": [
            {
                "rank": 1,
                "status": a1_status,
                "finding": (
                    "External TPTP truth accuracy="
                    + ("noData" if ta is None else f"{ta:.2%}")
                    + "."
                ),
            },
            {
                "rank": 2,
                "status": a2_status,
                "finding": (
                    "Decisive prover solve rate="
                    + ("noData" if sr is None else f"{sr:.2%}")
                    + ". Timeout/Unknown remains noData, not FAIL."
                ),
            },
            {
                "rank": 3,
                "status": a3_status,
                "finding": f"Unsupported / undetected TPTP language inputs={unsupported}.",
            },
        ],
        "methodological_boundary": (
            "This is independent from SAT-only testing because TPTP FOF/TFF may contain quantified "
            "first-order structure. Prover results are compared against external TPTP problem status. "
            "Full proof-object replay is a stronger future gate."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prover", required=True, type=Path, help="Path to Vampire binary.")
    ap.add_argument("--input", required=True, type=Path, help="TPTP .p file or directory tree.")
    ap.add_argument("--output", type=Path, default=Path("uie_logic_external_results"))
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--limit", type=int, default=0, help="0=all")
    ap.add_argument(
        "--prover-args",
        default="--mode casc",
        help='Extra prover arguments, shell-style string. Default: "--mode casc"',
    )
    args = ap.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    if not args.prover.exists():
        print(json.dumps({"verdict":"noData","error":f"prover not found: {args.prover}"}, indent=2))
        return 2

    problems = collect_inputs(args.input)
    if args.limit:
        problems = problems[:args.limit]

    if not problems:
        print(json.dumps({"verdict":"noData","error":"no TPTP .p files found"}, indent=2))
        return 0

    extra = shlex.split(args.prover_args)
    rows = []

    for p in problems:
        row = {"file": str(p), "filename": p.name}

        lang_gate, lang = detect_tptp_language(p)
        row["language_gate"] = lang_gate
        row["language"] = lang

        if lang_gate != "PASS":
            row.update({
                "parameter_gate": "noData",
                "representation_gate": "noData",
                "expected_status": None,
                "prover_status": "UNKNOWN",
                "verdict": "FAIL",
                "reason": "could not detect supported TPTP logic language",
            })
            rows.append(row)
            continue

        try:
            row["parameter_gate"] = "PASS"
            row["representation_gate"] = "PASS"
            row["parameters"] = detect_parameters(p)
        except Exception as e:
            row.update({
                "parameter_gate": "FAIL",
                "representation_gate": "FAIL",
                "expected_status": None,
                "prover_status": "UNKNOWN",
                "verdict": "FAIL",
                "reason": f"parameter/representation parsing failed: {e}",
            })
            rows.append(row)
            continue

        raw_expected = expected_status_from_header(p)
        expected = normalize_expected(raw_expected)
        row["raw_expected_status"] = raw_expected
        row["expected_status"] = expected

        run = run_prover(args.prover, p, args.timeout, extra)
        got = str(run["normalized_status"])
        row["execution"] = run["execution"]
        row["elapsed_s"] = run["elapsed_s"]
        row["returncode"] = run["returncode"]
        row["raw_prover_status"] = run["raw_status"]
        row["prover_status"] = got

        verdict, reason = classify_instance(expected, got, str(run["execution"]))
        row["verdict"] = verdict
        row["reason"] = reason
        rows.append(row)

        print(
            f"{p.name}: lang={lang} expected={expected or 'noData'} "
            f"prover={got} verdict={verdict} time={row['elapsed_s']:.3f}s",
            flush=True,
        )

    summary = summarize(rows)
    audit = top3_audit(summary, rows)

    with (args.output / "INSTANCE_RESULTS.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    (args.output / "SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (args.output / "TOP3_POST_TEST_AUDIT.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")

    print("\n" + json.dumps(summary, indent=2))
    return 1 if summary["overall_verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
