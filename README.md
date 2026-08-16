# UIE / HES Evolver — Correctness-First Evolutionary Solver

**UIE / HES Evolver** is an open-source Python framework for **evolutionary algorithms, program synthesis, automated reasoning, search optimization, benchmarking, and independent verification**.

It generates candidate solution methods, tests them against frozen holdouts and public benchmarks, rejects regressions, and promotes only **verified improvements**.

> **Generate → Test → Verify → Compare → Promote → Record lineage**

Current public starter: **v0.2**. The project focuses on reproducible, benchmark-driven algorithm evolution. It does **not** claim AGI or universal scientific discovery, and synthetic mechanism tests are kept separate from external benchmark evidence.

## Quick start

Requires Python 3.10+.

```bash
python run_all.py
python -m pip install pytest
pytest -q
```

Expected final line from the program suite:

```text
ALL TEST PROGRAMS PASSED
```

## Current test programs

### 1. `test_01_evolver_math.py` — correctness-first selection

Three implementations face a frozen arithmetic holdout. A cheap but incorrect
candidate is rejected. Among exact candidates, the lower modeled-cost method is
selected.

Current result: **11/11** for the promoted candidate.

### 2. `test_02_iscas85_c17.py` — public circuit equivalence

Self-contained exhaustive test of the public ISCAS85 `c17` combinational
circuit. All **32 possible input vectors** are evaluated.

Current result:

- scalar evaluator: 192 gate dispatches
- bit-packed evaluator: 6 gate dispatches
- exact output equivalence: **32/32**
- modeled dispatch reduction: **96.875%**

This metric is specifically **gate-dispatch count**, not wall-clock speedup.

### 3. `test_03_verifier_regression.py` — independent promotion gate

A correct closed-form optimization and a deliberately broken off-by-one mutant
face frozen parent behavior.

Current result: correct child **PASS**; broken mutant **FAIL**.

### 4. `test_04_mutation_evolver.py` — generated mutation loop

This is the first actual `mutation -> test -> verify -> promote` demonstration.
The seed program computes triangular numbers iteratively. The mutation generator
sees only four development I/O samples (`0,1,2,3`), infers exact polynomial
coefficients, and compiles the discovered child with Horner evaluation.

The frozen holdout is separate and includes values up to `100000`.
Six nearby coefficient mutants are generated automatically to pressure-test the
verifier.

Current result:

- parent: verified, modeled dynamic cost **111,154**
- inferred child: **8/8 frozen PASS**, modeled cost **32**
- six perturbed children: **6/6 rejected**
- promoted child: `poly_horner_deg2[0,1/2,1/2]`

This is a behavior-preserving optimization demonstration, **not** an external
mathematics benchmark.

### 5. `test_05_eight_puzzle.py` — search/planning regression

Classic 3x3 8-puzzle. A BFS baseline is compared with A* using Manhattan
heuristic on three frozen solvable states, including a depth-31 instance.
Every returned path is replayed to the goal and A* must preserve BFS optimal
path length.

Current result:

- BFS expanded states: **244,244**
- A* expanded states: **21,484**
- expanded-state reduction: **91.204%**
- solution validity: **3/3 replay PASS**
- optimal path length preserved: **3/3**

Again, expanded states are the declared cost metric; this is not a wall-clock
speed claim.

## Core lifecycle represented now

```text
SEED / PARENT PROGRAM
        |
        v
MUTATION GENERATOR
        |
        +----> child A
        +----> child B
        +----> child C ...
        |
        v
DEVELOPMENT CHECK
        |
        v
FROZEN / INDEPENDENT VERIFIER ---- fail ----> REJECT + KEEP NEGATIVE RESULT
        |
       pass
        v
QUALITY + COST COMPARISON
        |
        v
PROMOTE VERIFIED IMPROVEMENT
        |
        v
LINEAGE / RESULT RECORD
```

## Repository rules

1. Correctness before optimization.
2. Development data and frozen verification data stay separate.
3. No promotion on training/dev score alone.
4. Negative mutations remain visible in results.
5. Every cost claim names its metric.
6. Public capability claims require external/public benchmarks.
7. Seeds, configs, outputs and lineage should be reproducible.

## What v0.2 proves — and does not prove

It proves that the starter architecture can execute a small evolutionary
promotion cycle, discover one program transformation from development behavior,
reject nearby invalid mutations, preserve frozen behavior, and compare search
algorithms under replay verification.

It does **not** yet prove that the Evolver can invent broadly useful algorithms
across unrelated domains without domain-specific mutation operators.

## Next milestones

1. Add a larger external logic benchmark such as ISCAS85 `c432` with source
   provenance/checksum and an independent equivalence path.
2. Replace the single polynomial mutation family with multiple competing
   mutation operators and a mutation budget.
3. Add parent -> child lineage JSON with seeds/hashes for every run.
4. Add a public Boxoban/Sokoban adapter with replay verification.
5. Run frozen cross-domain promotion tests before naming a new champion.
