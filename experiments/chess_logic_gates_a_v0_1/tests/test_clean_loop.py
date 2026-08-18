import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CleanLoopTests(unittest.TestCase):
    def test_logic_and_chess_are_process_and_hash_isolated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "clean.json"
            subprocess.run(
                [sys.executable, str(ROOT / "run_clean_loop.py"), "--output", str(output)],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            result = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(result["clean_loop_pass"])
        self.assertTrue(result["separate_processes"])
        self.assertFalse(result["shared_mutable_memory"])
        self.assertTrue(result["logic"]["no_chess_imports"])
        self.assertEqual(result["logic"]["forbidden_chess_modules"], [])
        self.assertTrue(result["chess"]["no_logic_backflow"])
        self.assertEqual(
            result["chess"]["logic_hashes_before"],
            result["chess"]["logic_hashes_after"],
        )

    def test_corrupted_logic_lock_fails_closed_before_chess(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            lock_path = temp / "logic_lock.json"
            output = temp / "chess.json"
            subprocess.run(
                [sys.executable, str(ROOT / "logic_phase.py"), "--output", str(lock_path)],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["certificate"]["score"] = 0.999
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "chess_phase.py"),
                    "--logic-lock",
                    str(lock_path),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(result["chess_executed"])
        self.assertEqual(result["capability"], "noData")
