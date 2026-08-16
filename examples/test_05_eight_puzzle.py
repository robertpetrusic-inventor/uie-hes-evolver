"""Classic 8-puzzle planning benchmark: BFS parent vs A* Manhattan child.

Both solvers must return a replay-valid path to the same goal. We compare path
length (solution quality) and expanded states (search cost). Manhattan A* is
admissible for this puzzle, so it should preserve optimal path length while
reducing expansions on the frozen cases.
"""
from __future__ import annotations

from collections import deque
from heapq import heappop, heappush
from itertools import count

State = tuple[int, ...]
GOAL: State = (1, 2, 3, 4, 5, 6, 7, 8, 0)
MOVES = {
    0: ((1, "R"), (3, "D")),
    1: ((0, "L"), (2, "R"), (4, "D")),
    2: ((1, "L"), (5, "D")),
    3: ((0, "U"), (4, "R"), (6, "D")),
    4: ((1, "U"), (3, "L"), (5, "R"), (7, "D")),
    5: ((2, "U"), (4, "L"), (8, "D")),
    6: ((3, "U"), (7, "R")),
    7: ((4, "U"), (6, "L"), (8, "R")),
    8: ((5, "U"), (7, "L")),
}

# Increasing difficulty; the last is a standard 31-move hardest-depth instance.
FROZEN_CASES: tuple[State, ...] = (
    (1, 2, 3, 4, 5, 6, 0, 7, 8),
    (7, 2, 4, 5, 0, 6, 8, 3, 1),
    (8, 6, 7, 2, 5, 4, 3, 0, 1),
)


def neighbors(state: State):
    z = state.index(0)
    for j, move in MOVES[z]:
        s = list(state)
        s[z], s[j] = s[j], s[z]
        yield tuple(s), move


def reconstruct(parent: dict[State, tuple[State | None, str | None]], goal: State) -> str:
    moves: list[str] = []
    cur = goal
    while parent[cur][0] is not None:
        prev, move = parent[cur]
        assert prev is not None and move is not None
        moves.append(move)
        cur = prev
    return "".join(reversed(moves))


def bfs(start: State) -> tuple[str, int]:
    q = deque([start])
    parent: dict[State, tuple[State | None, str | None]] = {start: (None, None)}
    expanded = 0
    while q:
        state = q.popleft()
        expanded += 1
        if state == GOAL:
            return reconstruct(parent, state), expanded
        for nxt, move in neighbors(state):
            if nxt not in parent:
                parent[nxt] = (state, move)
                q.append(nxt)
    raise RuntimeError("unsolvable")


def manhattan(state: State) -> int:
    total = 0
    for idx, tile in enumerate(state):
        if tile == 0:
            continue
        goal_idx = tile - 1
        r1, c1 = divmod(idx, 3)
        r2, c2 = divmod(goal_idx, 3)
        total += abs(r1 - r2) + abs(c1 - c2)
    return total


def astar(start: State) -> tuple[str, int]:
    serial = count()
    heap: list[tuple[int, int, int, State]] = [(manhattan(start), 0, next(serial), start)]
    g = {start: 0}
    parent: dict[State, tuple[State | None, str | None]] = {start: (None, None)}
    expanded = 0
    while heap:
        _f, cost, _serial, state = heappop(heap)
        if cost != g.get(state):
            continue
        expanded += 1
        if state == GOAL:
            return reconstruct(parent, state), expanded
        for nxt, move in neighbors(state):
            ng = cost + 1
            if ng < g.get(nxt, 10**9):
                g[nxt] = ng
                parent[nxt] = (state, move)
                heappush(heap, (ng + manhattan(nxt), ng, next(serial), nxt))
    raise RuntimeError("unsolvable")


def replay(start: State, path: str) -> State:
    state = start
    # Need direction to target position from each current zero location, not a
    # global move->position lookup.
    for move in path:
        z = state.index(0)
        options = {m: j for j, m in MOVES[z]}
        if move not in options:
            raise AssertionError(f"illegal move {move} from zero index {z}")
        j = options[move]
        s = list(state)
        s[z], s[j] = s[j], s[z]
        state = tuple(s)
    return state


def main() -> None:
    bfs_expanded = 0
    astar_expanded = 0
    for i, start in enumerate(FROZEN_CASES, 1):
        path_b, exp_b = bfs(start)
        path_a, exp_a = astar(start)
        assert replay(start, path_b) == GOAL
        assert replay(start, path_a) == GOAL
        assert len(path_a) == len(path_b)  # preserve optimal solution quality
        bfs_expanded += exp_b
        astar_expanded += exp_a
        print(
            f"case={i} optimal_moves={len(path_a):2d} "
            f"BFS_expanded={exp_b:6d} A*_expanded={exp_a:6d}"
        )

    reduction = 1 - astar_expanded / bfs_expanded
    print(f"total_BFS_expanded={bfs_expanded}")
    print(f"total_A*_expanded={astar_expanded}")
    print(f"expanded_state_reduction={reduction:.3%}")

    assert astar_expanded < bfs_expanded


if __name__ == "__main__":
    main()
