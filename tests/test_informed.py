"""M4: heuristics, Best-first and A*."""

import random
import statistics
import subprocess
import sys
import time
import unittest
from pathlib import Path

from fifteen.board import Board
from fifteen.heuristics import HEURISTIC_NAMES, make_heuristic, removals_to_sort
from fifteen.io import format_solution
from fifteen.search import astar, best_first, bfs, get_strategy
from fifteen.search.common import SearchConfig
from fifteen.stats import SearchStats
from tools.generate import puzzle_text, states_by_depth
from tools.verify import verify_text

ROOT = Path(__file__).resolve().parent.parent
BOARD = Board(4, 4)
LAYERS = states_by_depth(BOARD, 7)
HIDS = (0, 1, 2, 3)


def run(module, board, state, hid):
    stats = SearchStats()
    name = "astar" if module is astar else "bf"
    return module.solve(board, state, SearchConfig(name, heuristic=hid), stats), stats


def values(board, state):
    return [make_heuristic(hid, board)(state) for hid in HIDS]


class HeuristicValuesTest(unittest.TestCase):
    def test_goal_is_zero(self):
        for rows, cols in [(4, 4), (3, 3), (2, 3), (1, 4), (5, 2)]:
            board = Board(rows, cols)
            self.assertEqual(values(board, board.goal), [0, 0, 0, 0])

    def test_hand_computed(self):
        # (board, state, [h0, h1, h2, h3])
        cases = [
            # 2x3: 0 1 2 / 3 4 5 -- every tile off by one step, tile 3 by 3; no conflicts
            (Board(2, 3), (0, 1, 2, 3, 4, 5), [0, 5, 7, 7]),
            # 4x4, first row 2 1 3 4: one row conflict -> +2
            (BOARD, (2, 1, 3, 4) + tuple(range(5, 16)) + (0,), [0, 2, 2, 4]),
            # 4x4, first row fully reversed 4 3 2 1: remove 3 tiles -> +6
            (BOARD, (4, 3, 2, 1) + tuple(range(5, 16)) + (0,), [0, 4, 8, 14]),
            # 3x3, column 0 holds 4 1 7: one column conflict -> +2
            (Board(3, 3), (4, 2, 3, 1, 5, 6, 7, 8, 0), [0, 2, 2, 4]),
            # blank is ignored: one move from the goal
            (BOARD, tuple(range(1, 15)) + (0, 15), [0, 1, 1, 1]),
            # 3x3, last row 8 7: a row conflict in the bottom row -> +2
            (Board(3, 3), (1, 2, 3, 4, 5, 6, 8, 7, 0), [0, 2, 2, 4]),
            # 3x3, row 0 is 4 2 3 with 1 below: tile 4 is outside its goal row, so it
            # cannot conflict with 2 and 3 there (only column 0 holds the 4/1 conflict)
            (Board(3, 3), (4, 2, 3, 1, 5, 6, 7, 8, 0), [0, 2, 2, 4]),
            # 2x3, 2 1 3 / 5 4 0: one conflict in each row -> +4
            (Board(2, 3), (2, 1, 3, 5, 4, 0), [0, 4, 4, 8]),
        ]
        for board, state, expected in cases:
            with self.subTest(state=state):
                self.assertEqual(values(board, state), expected)

    def test_removals_to_sort(self):
        self.assertEqual(removals_to_sort([]), 0)
        self.assertEqual(removals_to_sort([0, 1, 2]), 0)
        self.assertEqual(removals_to_sort([1, 0]), 1)
        self.assertEqual(removals_to_sort([3, 2, 1, 0]), 3)
        self.assertEqual(removals_to_sort([2, 0, 1, 3]), 1)

    def test_names_and_unknown_id(self):
        self.assertEqual(sorted(HEURISTIC_NAMES), list(HIDS))
        with self.assertRaises(ValueError):
            make_heuristic(4, BOARD)


class AdmissibilityTest(unittest.TestCase):
    def assert_admissible_and_ordered(self, board, layers):
        hs = [make_heuristic(hid, board) for hid in HIDS]
        for depth, states in layers.items():
            for state in states:
                h0, h1, h2, h3 = (h(state) for h in hs)
                self.assertTrue(h0 <= h1 <= h2 <= h3 <= depth,
                                msg=f"{state}: h={h0, h1, h2, h3}, d={depth}")

    def test_all_generated_puzzles(self):
        self.assert_admissible_and_ordered(BOARD, LAYERS)

    def test_full_state_spaces_against_exact_distances(self):
        for rows, cols in [(2, 3), (3, 2), (2, 2)]:
            board = Board(rows, cols)
            self.assert_admissible_and_ordered(board, states_by_depth(board, 100))

    def test_3x3_up_to_depth_14(self):
        board = Board(3, 3)
        self.assert_admissible_and_ordered(board, states_by_depth(board, 14))


class AStarTest(unittest.TestCase):
    def test_optimal_all_puzzles_all_heuristics(self):
        for depth in range(1, 8):
            for state in LAYERS[depth]:
                text = puzzle_text(BOARD, state)
                for hid in HIDS:
                    moves, stats = run(astar, BOARD, state, hid)
                    with self.subTest(depth=depth, state=state, h=hid):
                        self.assertEqual(len(moves), depth)
                        self.assertTrue(verify_text(text, format_solution(moves))[0])
                        self.assertGreaterEqual(stats.visited_states, stats.processed_states)

    def test_heuristic_strength_on_depth_7(self):
        means = []
        for hid in HIDS:
            processed = [run(astar, BOARD, s, hid)[1].processed_states for s in LAYERS[7]]
            means.append(statistics.mean(processed))
        h0, h1, h2, h3 = means
        self.assertTrue(h3 <= h2 <= h1 <= h0, msg=f"mean processed: {means}")
        self.assertLess(h1, h0)

    def test_optimal_on_non_square_boards(self):
        for rows, cols, max_d in [(2, 3, 21), (3, 2, 21), (3, 3, 14), (3, 4, 9)]:
            board = Board(rows, cols)
            for depth, states in states_by_depth(board, max_d).items():
                for state in states[:8]:
                    for hid in HIDS:
                        moves, _ = run(astar, board, state, hid)
                        with self.subTest(size=(rows, cols), depth=depth, h=hid):
                            self.assertEqual(len(moves), depth)
                            self.assertTrue(board.is_goal(board.apply_moves(state, moves)))

    def test_deeper_puzzles_all_admissible_heuristics_agree(self):
        # Random 4x4 puzzles of depth ~20-30: every admissible h must give the
        # same (optimal) length; on 3x3 we can compare with BFS directly.
        rng = random.Random(2026)
        board3 = Board(3, 3)
        for _ in range(15):
            state = self.random_walk(board3, 40, rng)
            moves_bfs = bfs.solve(board3, state, SearchConfig("bfs"), SearchStats())
            for hid in HIDS:
                self.assertEqual(len(run(astar, board3, state, hid)[0]), len(moves_bfs))
        for _ in range(8):
            state = self.random_walk(BOARD, 60, rng)
            lengths = {len(run(astar, BOARD, state, hid)[0]) for hid in (2, 3)}
            self.assertEqual(len(lengths), 1)

    @staticmethod
    def random_walk(board, steps, rng):
        state, blank = board.goal, board.size - 1
        for _ in range(steps):
            state, blank = board.apply(state, blank, rng.choice(board.legal_moves(blank)))
        return state

    def test_h0_matches_bfs_lengths(self):
        for state in LAYERS[6][:30]:
            self.assertEqual(len(run(astar, BOARD, state, 0)[0]),
                             len(bfs.solve(BOARD, state, SearchConfig("bfs"), SearchStats())))


class BestFirstTest(unittest.TestCase):
    def test_valid_all_puzzles_h1_to_h3(self):
        for depth in range(1, 8):
            for state in LAYERS[depth]:
                text = puzzle_text(BOARD, state)
                for hid in (1, 2, 3):
                    moves, _ = run(best_first, BOARD, state, hid)
                    with self.subTest(depth=depth, state=state, h=hid):
                        self.assertIsNotNone(moves)
                        self.assertGreaterEqual(len(moves), depth)
                        self.assertTrue(verify_text(text, format_solution(moves))[0])

    def test_h0_terminates_in_time(self):
        start = time.perf_counter()
        for state in LAYERS[7]:
            moves, _ = run(best_first, BOARD, state, 0)
            self.assertTrue(BOARD.is_goal(BOARD.apply_moves(state, moves)))
        self.assertLess(time.perf_counter() - start, 60)

    def test_not_always_optimal_is_allowed(self):
        # Greedy search may return longer paths; just check they are valid on deeper puzzles.
        rng = random.Random(7)
        for _ in range(10):
            state = AStarTest.random_walk(BOARD, 50, rng)
            for hid in (1, 2, 3):
                moves, _ = run(best_first, BOARD, state, hid)
                self.assertTrue(BOARD.is_goal(BOARD.apply_moves(state, moves)))


class EdgeCasesTest(unittest.TestCase):
    def test_both_strategies(self):
        for module in (best_first, astar):
            for hid in HIDS:
                with self.subTest(module=module.__name__, h=hid):
                    moves, stats = run(module, BOARD, BOARD.goal, hid)
                    self.assertEqual(moves, "")
                    self.assertEqual((stats.visited_states, stats.processed_states), (1, 0))
                    self.assertEqual(run(module, Board(1, 4), (1, 0, 2, 3), hid)[0], "RR")
                    self.assertEqual(run(module, Board(3, 1), (0, 1, 2), hid)[0], "DD")
                    b23 = Board(2, 3)
                    for depth, states in states_by_depth(b23, 21).items():
                        for state in states[:3]:
                            moves, _ = run(module, b23, state, hid)
                            self.assertTrue(b23.is_goal(b23.apply_moves(state, moves)))

    def test_exhausted_space_returns_none(self):
        for module in (best_first, astar):
            moves, stats = run(module, Board(2, 2), (2, 1, 3, 0), 2)
            self.assertIsNone(moves)
            self.assertEqual(stats.peak_stored_states, 12)

    def test_registry(self):
        self.assertIs(get_strategy("bf"), best_first.solve)
        self.assertIs(get_strategy("astar"), astar.solve)

    def test_cli(self):
        text = puzzle_text(BOARD, LAYERS[7][0])
        for flag in ("-a", "-h"):
            for hid in ("0", "1", "2", "3"):
                proc = subprocess.run([sys.executable, str(ROOT / "solver.py"), flag, hid],
                                      input=text, capture_output=True, text=True,
                                      cwd=str(ROOT), timeout=60)
                with self.subTest(flag=flag, h=hid):
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertTrue(verify_text(text, proc.stdout)[0])
                    if flag == "-a":
                        self.assertEqual(proc.stdout.split("\n")[0], "7")


if __name__ == "__main__":
    unittest.main()
