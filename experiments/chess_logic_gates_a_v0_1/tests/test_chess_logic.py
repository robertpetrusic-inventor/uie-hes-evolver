import unittest

from chess_logic.board import Board, Move
from chess_logic.mastery import LogicMastery
from chess_logic.system import ChessLogicSystem


class ChessLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = ChessLogicSystem(LogicMastery.run().certificate)

    def motif_names(self, fen, move):
        result = self.system.analyze(Board.from_fen(fen), move)
        self.assertTrue(result["move_gate"]["legal"])
        return {motif["name"] for motif in result["tactics"]["motifs"]}

    def test_knight_fork(self):
        names = self.motif_names("r3k3/8/8/3N4/8/8/8/4K3 w - - 0 1", "d5c7")
        self.assertIn("FORK", names)

    def test_absolute_pin(self):
        names = self.motif_names("4k3/8/2n5/8/B7/8/8/4K3 w - - 0 1", "a4b5")
        self.assertIn("PIN", names)

    def test_skewer(self):
        names = self.motif_names("7k/5r2/4q3/8/8/8/B7/K7 w - - 0 1", "a2b3")
        self.assertIn("SKEWER", names)

    def test_discovered_attack(self):
        names = self.motif_names("q6k/8/8/8/8/8/B6K/R7 w - - 0 1", "a2b3")
        self.assertIn("DISCOVERED_ATTACK", names)

    def test_mate(self):
        names = self.motif_names("7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "g6g7")
        self.assertIn("CHECK", names)
        self.assertIn("MATE", names)

    def test_castling_gate(self):
        board = Board.from_fen("4k3/8/8/8/8/8/8/4K2R w K - 0 1")
        self.assertIn(Move.from_uci("e1g1"), board.legal_moves())
        after = board.apply(Move.from_uci("e1g1"))
        self.assertEqual(after.piece_at("g1").kind, "K")
        self.assertEqual(after.piece_at("f1").kind, "R")

    def test_en_passant_gate(self):
        board = Board.from_fen("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
        move = Move.from_uci("e5d6")
        self.assertIn(move, board.legal_moves())
        after = board.apply(move)
        self.assertIsNone(after.piece_at("d5"))
        self.assertEqual(after.piece_at("d6").kind, "P")

    def test_promotion_gate(self):
        board = Board.from_fen("7k/P7/8/8/8/8/8/4K3 w - - 0 1")
        move = Move.from_uci("a7a8q")
        self.assertIn(move, board.legal_moves())
        self.assertEqual(board.apply(move).piece_at("a8").kind, "Q")

    def test_illegal_move_is_blocked(self):
        result = self.system.analyze(
            Board.from_fen("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"),
            "e2e5",
        )
        self.assertFalse(result["move_gate"]["legal"])
        self.assertEqual(result["tactics"]["motifs"], [])

    def test_initial_position_perft_depth_3(self):
        board = Board.from_fen(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )

        def perft(position, depth):
            if depth == 0:
                return 1
            return sum(perft(position.apply(move), depth - 1) for move in position.legal_moves())

        self.assertEqual(perft(board, 1), 20)
        self.assertEqual(perft(board, 2), 400)
        self.assertEqual(perft(board, 3), 8902)


if __name__ == "__main__":
    unittest.main()
