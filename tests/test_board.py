import unittest

from fifteen.board import MOVES, OPPOSITE, Board, IllegalMoveError, find_blank, format_state


class BoardTest(unittest.TestCase):
    def test_goal_any_size(self):
        self.assertEqual(Board(4, 4).goal, tuple(range(1, 16)) + (0,))
        self.assertEqual(Board(2, 3).goal, (1, 2, 3, 4, 5, 0))
        self.assertEqual(Board(1, 2).goal, (1, 0))

    def test_invalid_size(self):
        for r, c in [(1, 1), (0, 4), (4, 0), (-1, 3)]:
            with self.assertRaises(ValueError):
                Board(r, c)

    def test_legal_moves_corners_and_center(self):
        b = Board(3, 3)
        self.assertEqual(b.legal_moves(0), ["R", "D"])
        self.assertEqual(b.legal_moves(2), ["L", "D"])
        self.assertEqual(b.legal_moves(4), ["L", "R", "U", "D"])
        self.assertEqual(b.legal_moves(8), ["L", "U"])
        self.assertEqual(Board(1, 3).legal_moves(1), ["L", "R"])

    def test_blank_semantics(self):
        # Blank in the centre of a 3x3; each letter moves the blank that way.
        b = Board(3, 3)
        s = (1, 2, 3, 4, 0, 5, 6, 7, 8)
        self.assertEqual(b.apply(s, 4, "L"), ((1, 2, 3, 0, 4, 5, 6, 7, 8), 3))
        self.assertEqual(b.apply(s, 4, "R"), ((1, 2, 3, 4, 5, 0, 6, 7, 8), 5))
        self.assertEqual(b.apply(s, 4, "U"), ((1, 0, 3, 4, 2, 5, 6, 7, 8), 1))
        self.assertEqual(b.apply(s, 4, "D"), ((1, 2, 3, 4, 7, 5, 6, 0, 8), 7))

    def test_illegal_move(self):
        b = Board(4, 4)
        with self.assertRaises(IllegalMoveError):
            b.apply(b.goal, 15, "R")
        with self.assertRaises(IllegalMoveError):
            b.apply(b.goal, 15, "D")

    def test_opposite_moves_undo(self):
        b = Board(4, 4)
        for m in b.legal_moves(15):
            s, blank = b.apply(b.goal, 15, m)
            back, blank2 = b.apply(s, blank, OPPOSITE[m])
            self.assertEqual((back, blank2), (b.goal, 15))
        self.assertEqual({OPPOSITE[OPPOSITE[m]] for m in MOVES}, set(MOVES))

    def test_apply_moves(self):
        b = Board(4, 4)
        s = b.apply_moves(b.goal, "LLUR")
        self.assertEqual(b.apply_moves(s, "LDRR"), b.goal)
        self.assertEqual(b.apply_moves(b.goal, ""), b.goal)

    def test_apply_moves_reports_step(self):
        b = Board(2, 2)
        with self.assertRaisesRegex(IllegalMoveError, "step 2"):
            b.apply_moves(b.goal, "LL")
        with self.assertRaisesRegex(IllegalMoveError, "unknown move"):
            b.apply_moves(b.goal, "X")

    def test_helpers(self):
        b = Board(2, 3)
        self.assertEqual(find_blank(b.goal), 5)
        self.assertEqual(b.coords(4), (1, 1))
        self.assertEqual(format_state(b, b.goal), "1 2 3\n4 5 0")


if __name__ == "__main__":
    unittest.main()
