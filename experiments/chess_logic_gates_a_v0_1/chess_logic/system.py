"""Locked transition from verified Logic Core to chess circuits."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .board import Board, Move
from .gates import AND
from .mastery import LogicMastery, MasteryCertificate
from .tactics import TacticReport, analyze_tactics


class LogicCoreLockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class MoveGateReport:
    move: str
    signals: dict[str, int]
    legal: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ChessLogicSystem:
    """Architecture A: chess is unreachable without a current 100% certificate."""

    def __init__(self, certificate: MasteryCertificate) -> None:
        if not LogicMastery.verify_certificate(certificate):
            raise LogicCoreLockedError(
                "Chess remains locked: Logic Core certificate is missing, stale, or below 100%."
            )
        self.certificate = certificate
        self.stage = "CHESS_UNLOCKED_AFTER_LOGIC_100"

    def move_gate(self, board: Board, move: Move) -> MoveGateReport:
        piece = board.piece_at(move.from_sq)
        piece_exists = int(piece is not None)
        correct_turn = int(piece is not None and piece.color == board.turn)
        geometry = int(board.geometry_allows(move))
        path_clear = int(board.path_clear(move))
        destination = int(board.destination_ok(move))
        pseudo = int(move in board.pseudo_legal_moves(board.turn))
        king_safe = int(move in board.legal_moves(board.turn))
        legal = AND(
            AND(AND(piece_exists, correct_turn), AND(geometry, path_clear)),
            AND(destination, AND(pseudo, king_safe)),
        )
        signals = {
            "piece_exists": piece_exists,
            "correct_turn": correct_turn,
            "geometry": geometry,
            "path_clear": path_clear,
            "destination": destination,
            "special_rules": pseudo,
            "king_safe": king_safe,
            "legal": legal,
        }
        return MoveGateReport(move.uci(), signals, bool(legal))

    def analyze(self, board: Board, move_uci: str) -> dict[str, Any]:
        move = Move.from_uci(move_uci)
        move_report = self.move_gate(board, move)
        tactic_report: TacticReport = analyze_tactics(board, move)
        return {
            "stage": self.stage,
            "logic_certificate": self.certificate.to_dict(),
            "move_gate": move_report.to_dict(),
            "tactics": tactic_report.to_dict(),
            "evidence": {
                "execution_axis": "EXECUTED_CODE",
                "data_axis": "INTERNAL_AUTHORED_CHESS_REGRESSION",
                "verification_axis": "RULE_REPLAY_AND_EXPECTED_MOTIF_ORACLE",
                "capability_scope": "CHESS_LOGIC_DEVELOPMENT_ONLY",
            },
        }

