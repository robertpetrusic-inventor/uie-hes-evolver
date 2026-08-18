# Chess Logic Gates A v0.1

Executable implementation of the selected hierarchical architecture:

```text
primitive gates
→ composed digital circuits
→ exhaustive finite verification
→ 100% Logic Core lock
→ chess piece/legal-move gates
→ explainable tactic circuits
```

Chess construction is impossible without a current mastery certificate. The
certificate is regenerated from the gate implementation and all 58 declared
truth-table/state-transition rows. A stale, forged, incomplete, or non-100%
certificate keeps chess locked.

## Meaning of 100%

`100%` applies to the **declared finite Logic Core v0.1 contract**:

- NOT;
- AND, OR, XOR, NAND, NOR, XNOR;
- 2:1 multiplexer;
- half and full adders;
- one-bit comparator;
- 2-to-4 decoder;
- one-bit D flip-flop transition.

Every input combination is exhausted: **58/58 truth/state rows**. This is not a
claim that every possible future circuit has already been learned. New circuit
families must be added as new frozen levels and must also reach 100% before
they can extend the chess layer.

## Chess layer v0.1

The dependency-free chess kernel implements:

- pawn, knight, bishop, rook, queen and king movement;
- path blocking and own-piece destination blocking;
- king safety and legal-move filtering;
- check, checkmate and stalemate;
- castling, en passant and promotion;
- explainable detection of fork, absolute pin, skewer, discovered attack,
  capture, check, mate and promotion.

This first chess suite is **internal authored regression evidence**, not a claim
of external chess strength and not a new champion.

## Run

```bash
cd chess_logic_gates_a_v0_1
python3 -m unittest discover -s tests -v
python3 run_mastery.py
```

The run writes `results/logic_mastery_and_chess_smoke.json` with separate logic
and chess evidence scopes.

## Clean-room loop

The preferred run is:

```bash
python3 run_clean_loop.py
```

It removes the main interference paths:

1. Logic mastery runs in its own isolated process and imports no chess module.
2. It writes a hash-bound, immutable-by-contract logic certificate.
3. The process ends, destroying all working memory.
4. A second isolated process verifies the certificate and exact logic-source
   hashes before importing any chess code.
5. Chess runs with no path back into Logic learning.
6. Logic-source hashes are checked again after chess; any difference fails and
   re-locks the pipeline.

Both phases use a minimal deterministic environment, no stdin, no shared
mutable memory, and no Python bytecode writes. The generated
`results/clean_loop_result.json` records every boundary. “Clean” here means the
declared software interference channels are separated and checked; it is not an
unsupported claim about every possible external hardware/OS fault.

## Next frozen level

After v0.1 remains green, the next level should add exhaustive/metamorphic tests
for larger composed circuits. Only after that new level reaches 100% should the
chess curriculum expand to multi-ply tactic sequences and external frozen
positions. Existing `league_100` data and hashes remain untouched.
