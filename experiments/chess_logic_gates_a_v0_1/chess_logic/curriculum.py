"""Frozen internal chess smoke cases; no executable logic lives here."""

CASES = (
    ("fork", "r3k3/8/8/3N4/8/8/8/4K3 w - - 0 1", "d5c7", "FORK"),
    ("pin", "4k3/8/2n5/8/B7/8/8/4K3 w - - 0 1", "a4b5", "PIN"),
    ("skewer", "7k/5r2/4q3/8/8/8/B7/K7 w - - 0 1", "a2b3", "SKEWER"),
    ("discovered", "q6k/8/8/8/8/8/B6K/R7 w - - 0 1", "a2b3", "DISCOVERED_ATTACK"),
    ("mate", "7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "g6g7", "MATE"),
)

