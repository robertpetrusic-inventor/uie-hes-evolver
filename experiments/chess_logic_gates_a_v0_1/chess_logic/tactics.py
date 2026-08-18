"""Explainable chess-tactic circuits built after the Logic Core lock."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .board import BLACK, WHITE, Board, Move, opposite, parse_square, square_name
from .gates import AND, OR

VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 100}
ORTHOGONAL = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIAGONAL = ((1, 1), (1, -1), (-1, 1), (-1, -1))


@dataclass(frozen=True)
class Motif:
    name: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class TacticReport:
    move: str
    legal: bool
    gate_signals: dict[str, int]
    motifs: tuple[Motif, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "move": self.move,
            "legal": self.legal,
            "gate_signals": self.gate_signals,
            "motifs": [asdict(motif) for motif in self.motifs],
        }


def _enemy_targets(board: Board, attacker_square: str, attacker_color: str) -> list[str]:
    targets = []
    for target in board.attacks_from(attacker_square):
        piece = board.piece_at(target)
        if piece is not None and piece.color != attacker_color:
            targets.append(target)
    return sorted(targets)


def _fork(after: Board, move: Move, attacker_color: str) -> Motif | None:
    attacker = after.piece_at(move.to_sq)
    if attacker is None:
        return None
    targets = [
        square
        for square in _enemy_targets(after, move.to_sq, attacker_color)
        if VALUES[after.piece_at(square).kind] >= VALUES[attacker.kind]
        or after.piece_at(square).kind == "K"
    ]
    two_targets = int(len(targets) >= 2)
    legal_attacker = int(attacker.color == attacker_color)
    if AND(two_targets, legal_attacker):
        return Motif("FORK", {"attacker": move.to_sq, "targets": targets})
    return None


def _pins(board: Board, attacker_color: str) -> list[Motif]:
    enemy = opposite(attacker_color)
    motifs: list[Motif] = []
    king = board.king_square(enemy)
    if king is None:
        return motifs
    king_xy = parse_square(king)
    for dx, dy in ORTHOGONAL + DIAGONAL:
        candidate: str | None = None
        x, y = king_xy[0] + dx, king_xy[1] + dy
        while 0 <= x < 8 and 0 <= y < 8:
            square = square_name((x, y))
            piece = board.piece_at(square)
            if piece is None:
                x, y = x + dx, y + dy
                continue
            if candidate is None:
                if piece.color == enemy and piece.kind != "K":
                    candidate = square
                    x, y = x + dx, y + dy
                    continue
                break
            matching_slider = piece.color == attacker_color and (
                piece.kind == "Q"
                or (piece.kind == "R" and (dx, dy) in ORTHOGONAL)
                or (piece.kind == "B" and (dx, dy) in DIAGONAL)
            )
            if matching_slider:
                motifs.append(Motif("PIN", {"pinner": square, "pinned": candidate, "king": king}))
            break
    return motifs


def _skewers(board: Board, attacker_color: str) -> list[Motif]:
    motifs: list[Motif] = []
    for origin, attacker in board.iter_pieces(attacker_color):
        if attacker.kind not in {"B", "R", "Q"}:
            continue
        directions = ORTHOGONAL if attacker.kind == "R" else DIAGONAL if attacker.kind == "B" else ORTHOGONAL + DIAGONAL
        x0, y0 = parse_square(origin)
        for dx, dy in directions:
            enemies: list[str] = []
            x, y = x0 + dx, y0 + dy
            while 0 <= x < 8 and 0 <= y < 8:
                square = square_name((x, y))
                piece = board.piece_at(square)
                if piece is not None:
                    if piece.color == attacker_color:
                        break
                    enemies.append(square)
                    if len(enemies) == 2:
                        front = board.piece_at(enemies[0])
                        rear = board.piece_at(enemies[1])
                        if front is not None and rear is not None and VALUES[front.kind] > VALUES[rear.kind]:
                            motifs.append(Motif("SKEWER", {"attacker": origin, "front": enemies[0], "rear": enemies[1]}))
                        break
                x, y = x + dx, y + dy
    return motifs


def _attack_relations(board: Board, attacker_color: str) -> set[tuple[str, str]]:
    relations: set[tuple[str, str]] = set()
    for origin, _piece in board.iter_pieces(attacker_color):
        for target in _enemy_targets(board, origin, attacker_color):
            relations.add((origin, target))
    return relations


def _discovered(before: Board, after: Board, move: Move, attacker_color: str) -> list[Motif]:
    old_relations = _attack_relations(before, attacker_color)
    new_relations = _attack_relations(after, attacker_color)
    return [
        Motif("DISCOVERED_ATTACK", {"revealed_attacker": origin, "target": target, "moved_piece": move.to_sq})
        for origin, target in sorted(new_relations - old_relations)
        if origin != move.to_sq
    ]


def analyze_tactics(before: Board, move: Move) -> TacticReport:
    legal = move in before.legal_moves(before.turn)
    if not legal:
        return TacticReport(move.uci(), False, {"legal_move": 0}, ())

    mover = before.piece_at(move.from_sq)
    assert mover is not None
    target_before = before.piece_at(move.to_sq)
    after = before.apply(move)
    enemy = opposite(mover.color)

    check = int(after.in_check(enemy))
    mate = int(after.is_checkmate(enemy))
    capture = int(target_before is not None and target_before.color == enemy)
    en_passant_capture = int(mover.kind == "P" and move.to_sq == before.en_passant and target_before is None)
    promotion = int(move.promotion is not None)
    signals = {
        "legal_move": 1,
        "capture": OR(capture, en_passant_capture),
        "check": check,
        "mate": AND(check, mate),
        "promotion": promotion,
    }

    motifs: list[Motif] = []
    fork = _fork(after, move, mover.color)
    if fork:
        motifs.append(fork)
    motifs.extend(_pins(after, mover.color))
    motifs.extend(_skewers(after, mover.color))
    motifs.extend(_discovered(before, after, move, mover.color))
    if signals["capture"]:
        motifs.append(Motif("CAPTURE", {"from": move.from_sq, "to": move.to_sq}))
    if signals["check"]:
        motifs.append(Motif("CHECK", {"king": after.king_square(enemy)}))
    if signals["mate"]:
        motifs.append(Motif("MATE", {"king": after.king_square(enemy)}))
    if signals["promotion"]:
        motifs.append(Motif("PROMOTION", {"square": move.to_sq, "piece": move.promotion}))

    unique: dict[tuple[str, str], Motif] = {}
    for motif in motifs:
        key = (motif.name, str(sorted(motif.evidence.items())))
        unique[key] = motif
    return TacticReport(move.uci(), True, signals, tuple(unique[key] for key in sorted(unique)))

