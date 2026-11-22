import unittest

from fifteen.io import InputError, format_solution, parse_puzzle, parse_solution


class ParsePuzzleTest(unittest.TestCase):
    def test_basic(self):
        board, state = parse_puzzle("2 3\n1 2 3\n4 0 5\n")
        self.assertEqual((board.rows, board.cols), (2, 3))
        self.assertEqual(state, (1, 2, 3, 4, 0, 5))

    def test_whitespace_tolerant(self):
        _, state = parse_puzzle("2 2\r\n1\t2\r\n  3   0  \r\n")
        self.assertEqual(state, (1, 2, 3, 0))

    def test_trailing_content_ignored(self):
        _, state = parse_puzzle("1 2\n1 0\nextra stuff 99\n")
        self.assertEqual(state, (1, 0))

    def test_errors(self):
        bad = {
            "empty": "",
            "only one dim": "4",
            "non-int size": "4 x\n",
            "too few values": "2 2\n1 2 3\n",
            "non-int value": "2 2\n1 2 a 0\n",
            "duplicate": "2 2\n1 1 2 0\n",
            "out of range": "2 2\n1 2 4 0\n",
            "no blank": "2 2\n1 2 3 4\n",
            "1x1": "1 1\n0\n",
            "zero rows": "0 4\n",
            "negative": "-2 2\n",
        }
        for name, text in bad.items():
            with self.subTest(name), self.assertRaises(InputError):
                parse_puzzle(text)


class SolutionFormatTest(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_solution("LUR"), "3\nLUR\n")
        self.assertEqual(format_solution(""), "0\n\n")
        self.assertEqual(format_solution(None), "-1\n\n")

    def test_parse_roundtrip(self):
        for moves in ["LUR", "", None]:
            n, m = parse_solution(format_solution(moves))
            self.assertEqual((n, m), (-1, "") if moves is None else (len(moves), moves))

    def test_parse_crlf_and_missing_second_line(self):
        self.assertEqual(parse_solution("2\r\nLU\r\n"), (2, "LU"))
        self.assertEqual(parse_solution("-1\n"), (-1, ""))
        self.assertEqual(parse_solution("0"), (0, ""))

    def test_parse_errors(self):
        for text in ["", "x\nLU\n", "3\nLU\n", "2\nLX\n", "-1\nLU\n", "-5\n\n"]:
            with self.subTest(text=text), self.assertRaises(InputError):
                parse_solution(text)


if __name__ == "__main__":
    unittest.main()
