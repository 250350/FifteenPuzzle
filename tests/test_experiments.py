"""Exercise the batch runner's durable rows and result classification."""

import csv
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from tools import run_experiments as experiments

HEADER = ("puzzle,rows,cols,depth,strategy,param,result,solution_length,visited_states,"
          "processed_states,max_depth_reached,peak_stored_states,time_ms,verified")


class ExperimentTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.directory = Path(tmp.name)
        self.puzzle = self.directory / "2x2_01_00001.txt"
        self.puzzle.write_bytes(b"2 2\n1 2\n0 3\n")
        self.csv = self.directory / "results.csv"

    def run_cli(self, *extra):
        return subprocess.run(
            [sys.executable, str(experiments.ROOT / "tools" / "run_experiments.py"),
             "--puzzles-dir", str(self.directory), "--output", str(self.csv),
             "--param", "RDUL", "--param", "2", *extra],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def read_rows(self):
        with self.csv.open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    def test_resume_keeps_complete_rows_and_repairs_a_torn_write(self):
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        good = self.csv.read_bytes()
        lines = good.splitlines(keepends=True)
        self.assertEqual(lines[0], (HEADER + "\n").encode())
        self.assertEqual(len(lines), 7)
        self.csv.write_bytes(b"".join(lines[:3]) + lines[3][:20])
        proc = self.run_cli("--puzzle", "2x2_*.txt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Resuming with 2 complete rows", proc.stdout)
        self.assertTrue(self.csv.read_bytes().startswith(b"".join(lines[:3])))
        rows = self.read_rows()
        self.assertEqual(len(rows), 6)
        self.assertEqual({(r["puzzle"], r["strategy"], r["param"]) for r in rows},
                         {(self.puzzle.name, strategy, param) for strategy, param in (
                             ("bfs", "RDUL"), ("dfs", "RDUL"), ("idfs", "RDUL"),
                             ("bf", "2"), ("astar", "2"), ("sma", "2"),
                         )})
        self.assertTrue(all(r["result"] == "solved" and r["verified"] == "true" for r in rows))

    def test_changed_conditions_or_input_leave_the_csv_untouched(self):
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        saved = self.csv.read_bytes()
        for args in (("--timeout", "59"), ("--max-depth", "21"), ("--memory-limit", "50")):
            with self.subTest(args=args):
                proc = self.run_cli(*args)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("configuration differs", proc.stderr)
                self.assertEqual(self.csv.read_bytes(), saved)
        self.puzzle.write_bytes(b"2 2\n1 2\n0 3\n\n")
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("puzzles_sha256", proc.stderr)
        self.assertEqual(self.csv.read_bytes(), saved)

    def test_timeout_execution_failure_and_invalid_solution_have_distinct_results(self):
        puzzle = experiments._puzzles(self.directory, [self.puzzle.name])[0]
        args = Namespace(max_depth=20, memory_limit=100000, timeout=60, seed=None)
        stats = self.directory / "stats.json"
        for completed, expected in (
            (subprocess.CompletedProcess([], 2, b"", b"failed"), "error"),
            (subprocess.CompletedProcess([], 0, b"1\nD\n", b""), "invalid"),
            (subprocess.CompletedProcess([], 0, b"1\nL\n", b""), "error"),
        ):
            with self.subTest(expected=expected, completed=completed):
                with patch.object(experiments.subprocess, "run", return_value=completed):
                    row, detail = experiments._run(args, puzzle, "bfs", "RDUL", stats)
                self.assertEqual(row["result"], expected)
                self.assertEqual(row["verified"], "false")
                self.assertTrue(detail)

        with patch.object(experiments.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired([], 60)):
            row, _ = experiments._run(args, puzzle, "bfs", "RDUL", stats)
        self.assertEqual((row["result"], row["verified"]), ("timeout", "false"))
