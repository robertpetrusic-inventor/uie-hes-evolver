# UIE External Validation

Independent external-validation tracks for UIE / Math+Lang.

## SAT External
`external_validation/sat/uie_sat_external_v0_2.py`

- DIMACS-CNF input
- external SAT solver
- SAT model replay verification
- PASS / PASS* / FAIL / noData
- top-3 post-test audit

## Formal Logic External
`external_validation/logic/uie_logic_external_v0_1.py`

- TPTP input
- independent theorem prover
- SZS status
- comparison with external TPTP truth
- PASS / PASS* / FAIL / noData
- top-3 post-test audit

## Independence rule

SAT External and Formal Logic External are separate evidence axes and must not be double-counted.

Required order:

Detect Parameters -> Detect Language -> Representation Gate -> Execute -> Verify -> Audit

No empirical result is reported unless the test was actually executed.
