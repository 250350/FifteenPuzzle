"""Validate viewer replays against the shared puzzle and solution formats."""

import tempfile
import unittest
from pathlib import Path

from fifteen.io import InputError
from fifteen.replay import load_replay


class ReplayTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.puzzle = Path(directory.name) / "puzzle.txt"
        self.solution = Path(directory.name) / "solution.txt"
        self.puzzle.write_bytes(b"2\t3\r\n2 3 0\r\n1 4 5\r\n")

    def load(self, solution):
        self.solution.write_bytes(solution)
        return load_replay(self.puzzle, self.solution)

    def test_every_state_in_rectangular_replay(self):
        replay = self.load(b"5\r\nRRULL\r\n")
        self.assertEqual((replay.board.rows, replay.board.cols), (2, 3))
        self.assertEqual(replay.moves, "RRULL")
        self.assertEqual(replay.states, (
            (2, 3, 0, 1, 4, 5),
            (2, 0, 3, 1, 4, 5),
            (0, 2, 3, 1, 4, 5),
            (1, 2, 3, 0, 4, 5),
            (1, 2, 3, 4, 0, 5),
            (1, 2, 3, 4, 5, 0),
        ))

    def test_no_solution_keeps_start_even_for_a_solvable_puzzle(self):
        replay = self.load(b"-1\n\n")
        self.assertIsNone(replay.moves)
        self.assertEqual(replay.states, ((2, 3, 0, 1, 4, 5),))

    def test_already_solved_is_a_zero_step_replay(self):
        self.puzzle.write_bytes(b"1 3\n1 2 0\n")
        replay = self.load(b"0\n\n")
        self.assertEqual(replay.moves, "")
        self.assertEqual(replay.states, ((1, 2, 0),))

    def test_invalid_solution(self):
        for solution, message in (
            (b"2\nL\n", "stated length 2 but 1 moves given"),
            (b"1\nX\n", "invalid move letters"),
            (b"2\nRD\n", "Illegal move D at step 2"),
            (b"1\nR\n", "does not reach the goal state"),
            (b"0\n\n", "does not reach the goal state"),
            (b"\xff", "Cannot read solution.txt"),
        ):
            with self.subTest(solution=solution):
                with self.assertRaisesRegex(InputError, message):
                    self.load(solution)

    def test_invalid_puzzle(self):
        self.puzzle.write_bytes(b"2 3\n2 3 0\n1 4 4\n")
        with self.assertRaisesRegex(InputError, "Puzzle file puzzle.txt.*permutation"):
            self.load(b"-1\n\n")

    def test_missing_file(self):
        with self.assertRaisesRegex(InputError, "Cannot read solution.txt"):
            load_replay(self.puzzle, self.solution)
