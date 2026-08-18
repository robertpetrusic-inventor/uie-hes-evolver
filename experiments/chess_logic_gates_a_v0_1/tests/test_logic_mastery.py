import unittest

from chess_logic.mastery import LogicMastery, MasteryCertificate
from chess_logic.system import ChessLogicSystem, LogicCoreLockedError


class LogicMasteryTests(unittest.TestCase):
    def test_declared_logic_space_is_exhaustive_and_locked(self):
        report = LogicMastery.run()
        self.assertEqual(report.certificate.total, 58)
        self.assertEqual(report.certificate.passed, 58)
        self.assertEqual(report.certificate.score, 1.0)
        self.assertTrue(report.certificate.locked)
        self.assertTrue(LogicMastery.verify_certificate(report.certificate))

    def test_chess_rejects_forged_or_incomplete_certificate(self):
        bad = MasteryCertificate(
            version="logic-core-a-v0.1",
            passed=57,
            total=58,
            score=57 / 58,
            locked=False,
            evidence_sha256="0" * 64,
        )
        with self.assertRaises(LogicCoreLockedError):
            ChessLogicSystem(bad)

    def test_current_certificate_unlocks_chess(self):
        system = ChessLogicSystem(LogicMastery.run().certificate)
        self.assertEqual(system.stage, "CHESS_UNLOCKED_AFTER_LOGIC_100")


if __name__ == "__main__":
    unittest.main()
