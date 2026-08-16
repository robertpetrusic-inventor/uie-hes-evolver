# ISCAS85 c432 provenance

`c432` is an external ISCAS85 benchmark used by
`examples/test_06_iscas85_c432.py`.

The source netlists are **not vendored in this repository**. They are fetched
from the external academic distribution and accepted only when their SHA-256
hashes match the pinned values below.

Sources:

- BENCH: https://pld.ttu.ee/~maksim/benchmarks/iscas85/bench/c432.bench
- Verilog: https://pld.ttu.ee/~maksim/benchmarks/iscas85/verilog/c432.v

Pinned SHA-256:

- `c432.bench`
  `c3a37ac6850aa737f2705f9f3868e1f4ccfa6a6cc1b1a21d3095ac73191e258d`
- `c432.v`
  `5f57a91b4f2f2b4cacf47414e961a4c32aad915f961b116c379725f262690043`

Run:

    python3 benchmarks/iscas85/fetch_c432.py

The BENCH and Verilog representations are parsed separately and cross-checked
before the bit-packed candidate is accepted.
