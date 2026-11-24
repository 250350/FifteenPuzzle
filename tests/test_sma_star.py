"""M5: SMA* optimality, actual node residency and branch regeneration."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from weakref import WeakSet

from fifteen.board import Board
from fifteen.search import get_strategy, sma_star
from fifteen.search.common import SearchConfig, reconstruct_path
from fifteen.stats import SearchStats
from tests.test_cli import SOLVER, run
from tools.generate import puzzle_text, states_by_depth
from tools.verify import verify_text


class SmaStarTest(unittest.TestCase):
    def solve_counting_nodes(self, board, state, config):
        live = WeakSet()
        peak = 0
        test = self
        stats = SearchStats()

        class TrackedNode(sma_star._Node):
            __slots__ = ("__weakref__",)

            def __init__(self, *args):
                super().__init__(*args)
                nonlocal peak
                live.add(self)
                peak = max(peak, len(live))
                test.assertLessEqual(peak, config.memory_limit)

        # Counts all live instances at construction, including any victim
        # accidentally kept alive while its replacement is being created.
        with patch.object(sma_star, "_Node", TrackedNode):
            moves = sma_star.solve(board, state, config, stats)
        self.assertFalse(live)
        self.assertEqual(peak, stats.peak_stored_states)
        return moves, stats

    def test_all_generated_puzzles_with_default_and_small_limits(self):
        board = Board(4, 4)
        layers = states_by_depth(board, 7)
        self.assertEqual(sum(len(layers[d]) for d in range(1, 8)), 413)
        for hid in range(4):
            for config in (SearchConfig("sma", heuristic=hid),
                           SearchConfig("sma", heuristic=hid, memory_limit=50)):
                for d in range(1, 8):
                    for state in layers[d]:
                        with self.subTest(hid=hid, limit=config.memory_limit, d=d, state=state):
                            moves, _ = self.solve_counting_nodes(board, state, config)
                            self.assertIsNotNone(moves)
                            self.assertEqual(len(moves), d)
                            self.assertEqual(board.apply_moves(state, moves), board.goal)

    def test_evicted_branch_is_restored_with_its_backed_up_score(self):
        board = Board(2, 2)
        start = (2, 0, 1, 3)
        config = SearchConfig("sma", heuristic=0, memory_limit=4)
        forget = sma_star._Search._forget
        generate = sma_star._Search._generate
        events = []
        expanding = None

        def record_eviction(search, serial):
            leaf = search.nodes[serial]
            parent = leaf.parent
            candidates = (n for n in search.nodes.values()
                          if not n.children and n.serial != expanding)
            self.assertIs(leaf, max(candidates, key=lambda n: (n.f, -n.g, n.serial)))
            forget(search, serial)
            if reconstruct_path(leaf) == "RU":
                self.assertNotIn(serial, search.nodes)
                self.assertNotIn("U", parent.children)
                self.assertEqual(parent.forgotten["U"], 3)
                self.assertEqual(parent.f, 3)
                events.append(("forgotten", serial))

        def record_restoration(search, node):
            nonlocal expanding
            expanding = node.serial
            old_f = node.forgotten.get("U")
            generate(search, node)
            if old_f is not None and reconstruct_path(node) == "R" and "U" in node.children:
                child = search.nodes[node.children["U"]]
                self.assertNotIn("U", node.forgotten)
                self.assertEqual(child.f, old_f)
                self.assertGreater(child.f, child.g)  # h0, so the fresh estimate would be g.
                events.append(("restored", child.serial))

        with (patch.object(sma_star._Search, "_forget", record_eviction),
              patch.object(sma_star._Search, "_generate", record_restoration)):
            moves, stats = self.solve_counting_nodes(board, start, config)
        self.assertEqual([event for event, _ in events], ["forgotten", "restored"])
        self.assertNotEqual(events[0][1], events[1][1])
        self.assertEqual(moves, "RUL")
        self.assertEqual(board.apply_moves(start, moves), board.goal)
        self.assertEqual(stats.peak_stored_states, 4)

    def test_goal_and_cutoff_at_depth_limit(self):
        board = Board(2, 2)
        start = (2, 0, 1, 3)
        for state, limit, expected, depth in ((start, 3, None, 2), (start, 1, None, 0),
                                              (board.goal, 1, "", 0)):
            with self.subTest(limit=limit, state=state):
                moves, stats = self.solve_counting_nodes(
                    board, state, SearchConfig("sma", memory_limit=limit),
                )
                self.assertEqual(moves, expected)
                self.assertEqual(stats.max_depth_reached, depth)
                if limit == 1:
                    self.assertEqual((stats.visited_states, stats.processed_states), (1, 0))

    def test_rectangular_and_single_line_boards(self):
        config = SearchConfig("sma", heuristic=2)
        for size in ((2, 3), (3, 2), (3, 4), (2, 4), (1, 4), (3, 1)):
            board = Board(*size)
            for depth, states in states_by_depth(board, 6).items():
                for state in states:
                    with self.subTest(size=size, depth=depth, state=state):
                        moves, _ = self.solve_counting_nodes(board, state, config)
                        self.assertEqual(len(moves), depth)
                        self.assertEqual(board.apply_moves(state, moves), board.goal)

    def test_exhausted_search_and_registry(self):
        self.assertIs(get_strategy("sma"), sma_star.solve)
        board = Board(2, 2)
        moves, _ = self.solve_counting_nodes(board, (2, 1, 3, 0), SearchConfig("sma"))
        self.assertIsNone(moves)

    def test_cli_stats_and_memory_limit(self):
        puzzle = "2 2\n2 0\n1 3\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.json"
            for flag, limit, output, result in (("-s", 4, "3\nRUL\n", "solved"),
                                                 ("--sma", 3, "-1\n\n", "not_found")):
                with self.subTest(limit=limit):
                    args = [flag, "0", "--memory-limit", str(limit), "--stats", str(path)]
                    proc = run(SOLVER, args, puzzle)
                    self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, output, ""))
                    stats = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual((stats["strategy"], stats["param"]), ("sma", "0"))
                    self.assertEqual((stats["memory_limit"], stats["result"]), (limit, result))
                    if result == "solved":
                        self.assertTrue(verify_text(puzzle, proc.stdout)[0])

    def test_equal_bounds_under_memory_pressure_make_progress(self):
        puzzle = puzzle_text(Board(2, 3), (5, 2, 3, 1, 0, 4))
        proc = run(SOLVER, ["-s", "1", "--memory-limit", "11"], puzzle)
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))
        self.assertEqual(proc.stdout.splitlines()[0], "9")
        self.assertTrue(verify_text(puzzle, proc.stdout)[0])
