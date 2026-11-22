import itertools
import random
import unittest
from collections import deque

from fifteen.board import Board, find_blank
from fifteen.solvability import count_inversions, is_solvable


def reachable_from_goal(board):
    """All states reachable from the goal (exhaustive BFS, small boards only)."""
    seen = {board.goal}
    queue = deque([board.goal])
    while queue:
        state = queue.popleft()
        blank = find_blank(state)
        for move in board.legal_moves(blank):
            nxt, _ = board.apply(state, blank, move)
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def random_walk(board, steps, rng):
    state, blank = board.goal, board.size - 1
    for _ in range(steps):
        state, blank = board.apply(state, blank, rng.choice(board.legal_moves(blank)))
    return state


class SolvabilityTest(unittest.TestCase):
    def test_inversions(self):
        self.assertEqual(count_inversions((1, 2, 3)), 0)
        self.assertEqual(count_inversions((3, 2, 1)), 3)

    def test_exhaustive_small_boards(self):
        # Compare against ground truth for every permutation of small boards.
        for rows, cols in [(2, 2), (2, 3), (3, 2), (1, 2), (1, 3), (1, 4), (3, 1), (4, 1)]:
            board = Board(rows, cols)
            reachable = reachable_from_goal(board)
            for perm in itertools.permutations(range(board.size)):
                with self.subTest(size=(rows, cols), state=perm):
                    self.assertEqual(is_solvable(board, perm), perm in reachable)

    def test_known_4x4_and_3x3(self):
        b4 = Board(4, 4)
        self.assertTrue(is_solvable(b4, b4.goal))
        loyd = tuple(range(1, 14)) + (15, 14, 0)  # Sam Loyd's 14-15 puzzle
        self.assertFalse(is_solvable(b4, loyd))
        b3 = Board(3, 3)
        self.assertFalse(is_solvable(b3, (1, 2, 3, 4, 5, 6, 8, 7, 0)))
        self.assertTrue(is_solvable(b3, (1, 2, 3, 4, 5, 6, 7, 0, 8)))

    def test_random_walks_solvable_and_swaps_unsolvable(self):
        rng = random.Random(12345)
        for rows, cols in [(4, 4), (3, 3), (3, 4), (5, 3)]:
            board = Board(rows, cols)
            for _ in range(200):
                state = random_walk(board, rng.randint(0, 80), rng)
                self.assertTrue(is_solvable(board, state))
                # Swapping two tiles (not the blank) flips solvability.
                i, j = rng.sample([k for k, v in enumerate(state) if v != 0], 2)
                swapped = list(state)
                swapped[i], swapped[j] = swapped[j], swapped[i]
                self.assertFalse(is_solvable(board, tuple(swapped)))


if __name__ == "__main__":
    unittest.main()
