"""M2: BFS, shared search helpers and the puzzle generator."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fifteen.board import Board, find_blank
from fifteen.io import format_solution, parse_puzzle
from fifteen.search import bfs, get_strategy
from fifteen.search.common import Node, SearchConfig, expand, make_order, reconstruct_path
from fifteen.solvability import is_solvable
from fifteen.stats import SearchStats
from tools.generate import puzzle_text, states_by_depth, write_puzzles
from tools.verify import verify_text

ROOT = Path(__file__).resolve().parent.parent
ORDERS = ["RDUL", "RDLU", "DRUL", "DRLU", "LUDR", "LURD", "ULDR", "ULRD"]
EXPECTED_COUNTS = {1: 2, 2: 4, 3: 10, 4: 24, 5: 54, 6: 107, 7: 212}


def run_bfs(board, state, order="LRUD", seed=None):
    stats = SearchStats()
    moves = bfs.solve(board, state, SearchConfig("bfs", order=order, seed=seed), stats)
    return moves, stats


class CommonHelpersTest(unittest.TestCase):
    def test_make_order_fixed(self):
        nxt = make_order("DULR")
        self.assertEqual(tuple(nxt()), ("D", "U", "L", "R"))
        self.assertEqual(tuple(nxt()), ("D", "U", "L", "R"))
        with self.assertRaises(ValueError):
            make_order("LLRD")

    def test_make_order_random_is_seeded_permutation(self):
        a, b = make_order("R", 42), make_order("R", 42)
        seq_a = [tuple(a()) for _ in range(50)]
        seq_b = [tuple(b()) for _ in range(50)]
        self.assertEqual(seq_a, seq_b)
        self.assertTrue(all(sorted(p) == ["D", "L", "R", "U"] for p in seq_a))
        self.assertGreater(len(set(seq_a)), 1)  # actually varies per node

    def test_expand_order_legality_and_pruning(self):
        board = Board(3, 3)
        state = (1, 2, 3, 4, 0, 5, 6, 7, 8)
        moves = [m for m, _, _ in expand(board, state, 4, None, "DULR")]
        self.assertEqual(moves, ["D", "U", "L", "R"])
        moves = [m for m, _, _ in expand(board, state, 4, "R", "DULR")]  # came by R -> no L
        self.assertEqual(moves, ["D", "U", "R"])
        corner = [m for m, _, _ in expand(board, board.goal, 8, None, "LRUD")]
        self.assertEqual(corner, ["R", "D"])
        for move, child, blank in expand(board, state, 4, None, "LRUD"):
            self.assertEqual((child, blank), board.apply(state, 4, move))

    def test_reconstruct_path(self):
        root = Node((1, 0), 1, None, None, 0)
        child = Node((0, 1), 0, root, "L", 1)
        self.assertEqual(reconstruct_path(root), "")
        self.assertEqual(reconstruct_path(child), "L")


class GeneratorTest(unittest.TestCase):
    def test_counts_4x4(self):
        layers = states_by_depth(Board(4, 4), 7)
        self.assertEqual({d: len(s) for d, s in layers.items() if d}, EXPECTED_COUNTS)
        all_states = [s for layer in layers.values() for s in layer]
        self.assertEqual(len(all_states), len(set(all_states)))

    def test_full_space_2x3(self):
        layers = states_by_depth(Board(2, 3), 100)
        self.assertEqual(sum(len(s) for s in layers.values()), 360)  # 6!/2

    def test_write_files_and_naming(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "4x4_99_00001.txt").write_text("stale", encoding="utf-8")
            counts = write_puzzles(Board(4, 4), 3, out)
            self.assertEqual(counts, {1: 2, 2: 4, 3: 10})
            names = sorted(p.name for p in out.iterdir())
            self.assertEqual(len(names), 16)
            self.assertEqual(names[0], "4x4_01_00001.txt")
            self.assertEqual(names[-1], "4x4_03_00010.txt")
            board, state = parse_puzzle((out / "4x4_02_00003.txt").read_text(encoding="utf-8"))
            self.assertEqual(board.rows, 4)
            self.assertIn(state, states_by_depth(Board(4, 4), 2)[2])

    def test_deterministic(self):
        self.assertEqual(states_by_depth(Board(4, 4), 6), states_by_depth(Board(4, 4), 6))


class BfsOptimalityTest(unittest.TestCase):
    def test_all_generated_puzzles_all_orders(self):
        board = Board(4, 4)
        layers = states_by_depth(board, 7)
        for depth in range(1, 8):
            for state in layers[depth]:
                text = puzzle_text(board, state)
                for order in ORDERS:
                    moves, stats = run_bfs(board, state, order)
                    with self.subTest(depth=depth, state=state, order=order):
                        self.assertEqual(len(moves), depth)
                        ok, msg = verify_text(text, format_solution(moves))
                        self.assertTrue(ok, msg)
                        self.assertEqual(stats.max_depth_reached, depth)
                        self.assertGreaterEqual(stats.visited_states, stats.processed_states)
                        self.assertLessEqual(stats.peak_stored_states, stats.visited_states)

    def test_random_order_seeded_all_puzzles(self):
        board = Board(4, 4)
        for depth, states in states_by_depth(board, 7).items():
            for state in states[:20]:
                moves, _ = run_bfs(board, state, "R", seed=depth)
                self.assertEqual(len(moves), depth)


class BfsEdgeCasesTest(unittest.TestCase):
    def test_start_is_goal(self):
        board = Board(4, 4)
        moves, stats = run_bfs(board, board.goal)
        self.assertEqual(moves, "")
        self.assertEqual((stats.visited_states, stats.processed_states), (1, 0))
        self.assertEqual(format_solution(moves), "0\n\n")

    def test_non_square_boards_optimal(self):
        # Compare with the exact distances from the generator's full BFS.
        for rows, cols, max_d in [(2, 3, 30), (3, 2, 30), (3, 4, 9), (2, 4, 12)]:
            board = Board(rows, cols)
            for depth, states in states_by_depth(board, max_d).items():
                for state in states[:15]:
                    moves, _ = run_bfs(board, state)
                    with self.subTest(size=(rows, cols), depth=depth):
                        self.assertEqual(len(moves), depth)
                        self.assertTrue(board.is_goal(board.apply_moves(state, moves)))

    def test_single_line_boards(self):
        board = Board(1, 4)
        moves, _ = run_bfs(board, (1, 0, 2, 3))
        self.assertEqual(moves, "LL")
        board = Board(3, 1)
        moves, _ = run_bfs(board, (0, 1, 2))
        self.assertEqual(moves, "UU")

    def test_exhausted_search_returns_none(self):
        # BFS is only called on solvable boards, but it must still terminate
        # cleanly when the space is exhausted.
        board = Board(2, 2)
        unsolvable = (2, 1, 3, 0)
        self.assertFalse(is_solvable(board, unsolvable))
        moves, stats = run_bfs(board, unsolvable)
        self.assertIsNone(moves)
        self.assertEqual(stats.peak_stored_states, 12)  # half of 4!

    def test_registry(self):
        self.assertIs(get_strategy("bfs"), bfs.solve)


class BfsEndToEndTest(unittest.TestCase):
    def run_solver(self, args, stdin):
        return subprocess.run([sys.executable, str(ROOT / "solver.py"), *args], input=stdin,
                              capture_output=True, text=True, cwd=str(ROOT), timeout=60)

    def test_solver_cli(self):
        board = Board(4, 4)
        state = states_by_depth(board, 7)[7][0]
        text = puzzle_text(board, state)
        proc = self.run_solver(["-b", "RDUL"], text)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.split("\n")
        self.assertEqual(lines[0], "7")
        self.assertEqual(len(lines[1]), 7)
        self.assertTrue(verify_text(text, proc.stdout)[0])

    def test_solver_already_solved_and_unsolvable(self):
        self.assertEqual(self.run_solver(["-b", "LRUD"], "2 2\n1 2\n3 0\n").stdout, "0\n\n")
        self.assertEqual(self.run_solver(["-b", "LRUD"], "2 2\n2 1\n3 0\n").stdout, "-1\n\n")

    def test_random_seed_reproducible(self):
        board = Board(4, 4)
        text = puzzle_text(board, states_by_depth(board, 6)[6][5])
        with tempfile.TemporaryDirectory() as tmp:
            outputs = []
            for i in range(3):
                stats_path = Path(tmp) / f"s{i}.json"
                proc = self.run_solver(["-b", "R", "--seed", "123", "--stats", str(stats_path)], text)
                stats = stats_path.read_text(encoding="utf-8")
                # Everything but the timing must be identical.
                stats = "\n".join(l for l in stats.splitlines() if "time_ms" not in l)
                outputs.append((proc.stdout, stats))
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[1], outputs[2])


if __name__ == "__main__":
    unittest.main()
