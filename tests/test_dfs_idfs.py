"""M3: DFS and IDFS.

The full DFS check with the default limit (413 puzzles x 8 orders, ~45 min)
runs only when the environment variable FIFTEEN_SLOW=1 is set.
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from fifteen.board import Board, find_blank
from fifteen.io import format_solution
from fifteen.search import dfs, get_strategy, idfs
from fifteen.search.common import SearchConfig, expand, make_order
from fifteen.stats import SearchStats
from tools.generate import puzzle_text, states_by_depth
from tools.verify import verify_text

ROOT = Path(__file__).resolve().parent.parent
ORDERS = ["RDUL", "RDLU", "DRUL", "DRLU", "LUDR", "LURD", "ULDR", "ULRD"]
BOARD = Board(4, 4)
LAYERS = states_by_depth(BOARD, 7)
SLOW = os.environ.get("FIFTEEN_SLOW") == "1"


def run(module, board, state, order="LRUD", max_depth=20, seed=None):
    stats = SearchStats()
    config = SearchConfig(module.__name__.rsplit(".", 1)[-1], order=order,
                          max_depth=max_depth, seed=seed)
    return module.solve(board, state, config, stats), stats


def plain_visited_dfs(board, start, limit, order):
    """Reference DFS with a plain global visited set (incomplete on purpose)."""
    visited = {start}
    stack = [(start, find_blank(start), None, 0)]
    while stack:
        state, blank, parent_move, g = stack.pop()
        children = []
        for move, child, child_blank in expand(board, state, blank, parent_move, order):
            if child in visited:
                continue
            visited.add(child)
            if board.is_goal(child):
                return True
            if g + 1 < limit:
                children.append((child, child_blank, move, g + 1))
        stack.extend(reversed(children))
    return False


class IdfsTest(unittest.TestCase):
    def test_optimal_on_all_puzzles_all_orders(self):
        for depth in range(1, 8):
            for state in LAYERS[depth]:
                text = puzzle_text(BOARD, state)
                for order in ORDERS:
                    moves, stats = run(idfs, BOARD, state, order)
                    with self.subTest(depth=depth, state=state, order=order):
                        self.assertEqual(len(moves), depth)
                        self.assertTrue(verify_text(text, format_solution(moves))[0])
                        self.assertEqual(stats.max_depth_reached, depth)
                        self.assertGreaterEqual(stats.visited_states, stats.processed_states)

    def test_limit_too_small(self):
        for depth in range(1, 8):
            for state in LAYERS[depth][:10]:
                moves, _ = run(idfs, BOARD, state, "LRUD", max_depth=depth - 1)
                self.assertIsNone(moves)

    def test_non_square_boards_optimal(self):
        for rows, cols, max_d in [(2, 3, 21), (3, 2, 21), (3, 4, 9), (2, 4, 12)]:
            board = Board(rows, cols)
            for depth, states in states_by_depth(board, max_d).items():
                for state in states[:10]:
                    moves, _ = run(idfs, board, state, "DRUL", max_depth=max(depth, 1))
                    with self.subTest(size=(rows, cols), depth=depth):
                        self.assertEqual(len(moves), depth)
                        self.assertTrue(board.is_goal(board.apply_moves(state, moves)))

    def test_stops_when_space_exhausted(self):
        # 2x2 unsolvable: the reachable space is a cycle of 12 states, so a DLS
        # can go at most 11 deep along it; iterations stop at limit 12, far
        # before the limit of 1000.
        moves, stats = run(idfs, Board(2, 2), (2, 1, 3, 0), max_depth=1000)
        self.assertIsNone(moves)
        self.assertLessEqual(stats.max_depth_reached, 11)

    def test_stats_accumulate_over_iterations(self):
        state = LAYERS[7][0]
        _, stats = run(idfs, BOARD, state)
        single = SearchStats()
        dfs.depth_limited_search(BOARD, state, 7, make_order("LRUD"), single)
        self.assertGreater(stats.processed_states, single.processed_states)


class DfsTest(unittest.TestCase):
    def test_complete_with_tight_limit_all_puzzles_all_orders(self):
        # With max_depth == optimal depth the only solutions are optimal ones;
        # the depth-aware map must still find one (a plain visited set may not).
        for depth in range(1, 8):
            for state in LAYERS[depth]:
                text = puzzle_text(BOARD, state)
                for order in ORDERS:
                    moves, stats = run(dfs, BOARD, state, order, max_depth=depth)
                    with self.subTest(depth=depth, state=state, order=order):
                        self.assertIsNotNone(moves)
                        self.assertEqual(len(moves), depth)
                        self.assertTrue(verify_text(text, format_solution(moves))[0])
                        self.assertLessEqual(stats.max_depth_reached, depth)

    def test_valid_with_loose_limit(self):
        for depth in range(1, 8):
            for state in LAYERS[depth][:6]:
                for order in ORDERS[:4]:
                    moves, stats = run(dfs, BOARD, state, order, max_depth=depth + 4)
                    with self.subTest(depth=depth, order=order):
                        self.assertLessEqual(len(moves), depth + 4)
                        self.assertTrue(BOARD.is_goal(BOARD.apply_moves(state, moves)))
                        self.assertLessEqual(stats.max_depth_reached, depth + 4)

    def test_limit_too_small_returns_none(self):
        for depth in range(1, 8):
            for state in LAYERS[depth][:10]:
                moves, stats = run(dfs, BOARD, state, "ULDR", max_depth=depth - 1)
                self.assertIsNone(moves)
                self.assertLessEqual(stats.max_depth_reached, max(depth - 1, 0))

    def test_depth_aware_map_reexpands_shallower_states(self):
        # 1) Instrumented: a state is only re-accepted when reached at a strictly
        #    smaller depth (stale entries are skipped), so a state expanded twice
        #    proves such a re-expansion happened.
        expanded = {}

        def spy(board, state, blank, parent_move, moves, _real=expand):
            expanded[state] = expanded.get(state, 0) + 1
            return _real(board, state, blank, parent_move, moves)

        with mock.patch.object(dfs, "expand", spy):
            moves, _ = dfs.depth_limited_search(BOARD, LAYERS[7][0], 12, make_order("LRUD"),
                                                SearchStats())
        self.assertIsNotNone(moves)
        self.assertTrue(any(count > 1 for count in expanded.values()),
                        "expected at least one state re-expanded at a smaller depth")

        # 2) Behavioural: a plain visited set misses solutions within the limit
        #    in some cases; the depth-aware DFS must solve every one of them.
        failures_of_plain = 0
        for depth in range(3, 8):
            for state in LAYERS[depth]:
                for order in ("LRUD", "DRUL"):
                    if not plain_visited_dfs(BOARD, state, depth + 2, order):
                        failures_of_plain += 1
                        moves, _ = run(dfs, BOARD, state, order, max_depth=depth + 2)
                        self.assertIsNotNone(moves)
        self.assertGreater(failures_of_plain, 0)

    def test_successors_processed_in_given_order(self):
        board = Board(3, 3)
        start = (1, 2, 3, 4, 0, 5, 6, 7, 8)  # blank in the centre: all 4 moves legal
        for order in ORDERS:
            calls = []

            def spy(b, state, blank, parent_move, moves, _real=expand):
                calls.append(parent_move)
                return _real(b, state, blank, parent_move, moves)

            with mock.patch.object(dfs, "expand", spy):
                dfs.depth_limited_search(board, start, 3, make_order(order), SearchStats())
            # call 0 expands the root; call 1 expands the first child in `order`.
            self.assertEqual(calls[0], None)
            self.assertEqual(calls[1], order[0], msg=order)

    def test_registry(self):
        self.assertIs(get_strategy("dfs"), dfs.solve)
        self.assertIs(get_strategy("idfs"), idfs.solve)

    @unittest.skipUnless(SLOW, "set FIFTEEN_SLOW=1 for the full default-limit DFS run (~45 min)")
    def test_default_limit_all_puzzles_all_orders(self):
        for order in ORDERS:
            for depth in range(1, 8):
                for state in LAYERS[depth]:
                    moves, _ = run(dfs, BOARD, state, order)
                    with self.subTest(order=order, depth=depth, state=state):
                        self.assertIsNotNone(moves)
                        self.assertLessEqual(len(moves), 20)
                        ok, msg = verify_text(puzzle_text(BOARD, state), format_solution(moves))
                        self.assertTrue(ok, msg)


class EdgeCasesTest(unittest.TestCase):
    def test_both_strategies(self):
        for module in (dfs, idfs):
            with self.subTest(module=module.__name__):
                moves, stats = run(module, BOARD, BOARD.goal)
                self.assertEqual(moves, "")
                self.assertEqual((stats.visited_states, stats.processed_states), (1, 0))
                self.assertIsNone(run(module, BOARD, LAYERS[3][0], max_depth=0)[0])
                self.assertEqual(run(module, Board(1, 4), (1, 0, 2, 3))[0], "RR")
                self.assertEqual(run(module, Board(3, 1), (0, 1, 2))[0], "DD")
                b23 = Board(2, 3)
                for depth, states in states_by_depth(b23, 21).items():
                    for state in states[:5]:
                        moves, _ = run(module, b23, state, "LURD", max_depth=21)
                        self.assertTrue(b23.is_goal(b23.apply_moves(state, moves)))

    def test_random_order_seeded(self):
        state = LAYERS[7][3]
        for module in (dfs, idfs):
            a = run(module, BOARD, state, "R", max_depth=10, seed=9)
            b = run(module, BOARD, state, "R", max_depth=10, seed=9)
            self.assertEqual(a[0], b[0])
            self.assertEqual(a[1].visited_states, b[1].visited_states)
            self.assertTrue(BOARD.is_goal(BOARD.apply_moves(state, a[0])))

    def test_cli(self):
        text = puzzle_text(BOARD, LAYERS[7][0])

        def solver(*args):
            return subprocess.run([sys.executable, str(ROOT / "solver.py"), *args], input=text,
                                  capture_output=True, text=True, cwd=str(ROOT), timeout=120)

        self.assertEqual(solver("-i", "RDUL").stdout.split("\n")[0], "7")
        self.assertEqual(solver("-d", "RDUL", "--max-depth", "3").stdout, "-1\n\n")
        self.assertEqual(solver("-i", "RDUL", "--max-depth", "6").stdout, "-1\n\n")
        proc = solver("-d", "LURD", "--max-depth", "9")
        self.assertTrue(verify_text(text, proc.stdout)[0])


if __name__ == "__main__":
    unittest.main()
