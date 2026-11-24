"""End-to-end tests of solver.py and tools/verify.py through subprocesses."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOLVER = ROOT / "solver.py"
VERIFY = ROOT / "tools" / "verify.py"

SOLVABLE = "4 4\n1 2 3 4\n5 6 7 8\n9 10 11 12\n13 14 0 15\n"
UNSOLVABLE = "4 4\n1 2 3 4\n5 6 7 8\n9 10 11 12\n13 15 14 0\n"


def run(script, args, stdin=""):
    return subprocess.run(
        [sys.executable, str(script), *args],
        input=stdin, capture_output=True, text=True, cwd=str(ROOT), timeout=60,
    )


class SolverArgumentsTest(unittest.TestCase):
    def assert_usage_error(self, args):
        proc = run(SOLVER, args, SOLVABLE)
        self.assertEqual(proc.returncode, 2, msg=f"{args}: {proc.stderr}")
        self.assertEqual(proc.stdout, "")
        self.assertIn("usage", proc.stderr)

    def test_strategy_required_and_exclusive(self):
        self.assert_usage_error([])
        self.assert_usage_error(["-b", "LRUD", "-a", "1"])

    def test_invalid_orders(self):
        for order in ["LRU", "LLRD", "lrud", "X", "RR", "LRUDL", ""]:
            with self.subTest(order=order):
                self.assert_usage_error(["-b", order])

    def test_invalid_heuristics(self):
        for hid in ["4", "-1", "a", "1.5"]:
            with self.subTest(hid=hid):
                self.assert_usage_error(["-a", hid])

    def test_invalid_optional_values(self):
        self.assert_usage_error(["-d", "LRUD", "--max-depth", "-3"])
        self.assert_usage_error(["-s", "1", "--memory-limit", "0"])
        self.assert_usage_error(["-b", "R", "--seed", "x"])

    def test_valid_flags_accepted(self):
        valid = [
            ["-b", "RDUL"], ["--bfs", "R"], ["-d", "DULR"], ["-i", "LURD"],
            ["-h", "1"], ["--bf", "0"], ["-a", "3"], ["-s", "2", "--memory-limit", "500"],
            ["-d", "LRUD", "--max-depth", "0"], ["-b", "R", "--seed", "7"],
        ]
        for args in valid:
            with self.subTest(args=args):
                proc = run(SOLVER, args, SOLVABLE)
                self.assertEqual(proc.returncode, 0, msg=proc.stderr)

    def test_dash_h_is_strategy_not_help(self):
        proc = run(SOLVER, ["-h", "2"], SOLVABLE)
        self.assertEqual(proc.returncode, 0)
        self.assertNotIn("usage", proc.stdout)

    def test_long_help(self):
        proc = run(SOLVER, ["--help"])
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--astar", proc.stdout)


class SolverIOTest(unittest.TestCase):
    def test_invalid_input(self):
        for text in ["", "4 4\n1 2 3\n", "2 2\n1 1 2 0\n"]:
            with self.subTest(text=text):
                proc = run(SOLVER, ["-a", "2"], text)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertIn("invalid input", proc.stderr)

    def test_unsolvable_prints_minus_one(self):
        proc = run(SOLVER, ["-b", "LRUD"], UNSOLVABLE)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "-1\n\n")
        self.assertEqual(proc.stderr, "")

    def test_output_is_exactly_two_lines(self):
        proc = run(SOLVER, ["-a", "2"], SOLVABLE)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(len(proc.stdout.split("\n")), 3)  # two lines + final newline
        self.assertTrue(proc.stdout.endswith("\n"))

    def test_stats_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            run(SOLVER, ["-s", "3", "--stats", str(path)], UNSOLVABLE)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["result"], "unsolvable")
            self.assertEqual((data["strategy"], data["param"]), ("sma", "3"))
            self.assertEqual(data["memory_limit"], 100000)
            self.assertIsNone(data["max_depth_limit"])
            expected = {
                "strategy", "param", "rows", "cols", "result", "solution_length", "solution",
                "visited_states", "processed_states", "max_depth_reached", "peak_stored_states",
                "time_ms", "max_depth_limit", "memory_limit", "seed",
            }
            self.assertEqual(set(data), expected)

            run(SOLVER, ["-b", "R", "--seed", "5", "--stats", str(path)], SOLVABLE)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual((data["param"], data["seed"]), ("R", 5))
            self.assertEqual((data["result"], data["solution_length"], data["solution"]),
                             ("solved", 1, "L"))
            self.assertGreater(data["visited_states"], 0)

    def test_no_stats_file_without_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(SOLVER), "-a", "1"], input=SOLVABLE,
                           capture_output=True, text=True, cwd=tmp, timeout=60)
            self.assertEqual(list(Path(tmp).iterdir()), [])


class VerifyTest(unittest.TestCase):
    def check(self, puzzle, solution, expected_code):
        with tempfile.TemporaryDirectory() as tmp:
            p, s = Path(tmp) / "p.txt", Path(tmp) / "s.txt"
            p.write_text(puzzle, encoding="utf-8")
            s.write_text(solution, encoding="utf-8")
            proc = run(VERIFY, [str(p), str(s)])
            self.assertEqual(proc.returncode, expected_code, msg=proc.stdout + proc.stderr)

    def test_cases(self):
        self.check(SOLVABLE, "1\nL\n", 0)          # valid: tile 15 slides left
        self.check(SOLVABLE, "3\nLRL\n", 0)        # valid, non-optimal
        self.check(SOLVABLE, "1\nR\n", 1)          # goal not reached
        self.check(SOLVABLE, "2\nLL\n", 1)         # illegal move
        self.check(SOLVABLE, "-1\n\n", 1)          # -1 for a solvable puzzle
        self.check(UNSOLVABLE, "-1\n\n", 0)        # -1 for an unsolvable puzzle
        self.check(SOLVABLE, "2\nL\n", 2)          # length mismatch -> malformed
        self.check("2 2\n1 1 2 0\n", "0\n\n", 2)   # malformed puzzle

    def test_usage(self):
        self.assertEqual(run(VERIFY, []).returncode, 2)


if __name__ == "__main__":
    unittest.main()
