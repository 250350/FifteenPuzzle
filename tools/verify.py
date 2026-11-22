#!/usr/bin/env python3
"""Check a solver output against a puzzle (CONTRACT.md, section 10.2).

Usage::

    python3 tools/verify.py PUZZLE_FILE SOLUTION_FILE

Exit codes:
    0  valid: the moves are legal and reach the goal, or the solution is -1
       and the puzzle really is unsolvable;
    1  invalid: illegal move, goal not reached, length mismatch, or -1 reported
       for a solvable puzzle;
    2  usage error, unreadable file, or malformed puzzle/solution text.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fifteen.board import IllegalMoveError  # noqa: E402
from fifteen.io import InputError, parse_puzzle, parse_solution  # noqa: E402
from fifteen.solvability import is_solvable  # noqa: E402

EXIT_VALID, EXIT_INVALID, EXIT_ERROR = 0, 1, 2


def verify_text(puzzle_text: str, solution_text: str) -> Tuple[bool, str]:
    """Return ``(is_valid, message)``. Raises ``InputError`` on malformed text."""
    board, start = parse_puzzle(puzzle_text)
    n, moves = parse_solution(solution_text)
    solvable = is_solvable(board, start)
    if n == -1:
        if solvable:
            return False, "no solution reported, but the puzzle is solvable"
        return True, "no solution reported; the puzzle is unsolvable"
    try:
        final = board.apply_moves(start, moves)
    except IllegalMoveError as exc:
        return False, f"illegal move: {exc}"
    if not board.is_goal(final):
        return False, f"the {n} moves do not reach the goal state"
    return True, f"valid solution of length {n}"


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: verify.py PUZZLE_FILE SOLUTION_FILE", file=sys.stderr)
        return EXIT_ERROR
    try:
        puzzle_text = Path(argv[0]).read_text(encoding="utf-8")
        solution_text = Path(argv[1]).read_text(encoding="utf-8")
        ok, message = verify_text(puzzle_text, solution_text)
    except (OSError, InputError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(("VALID: " if ok else "INVALID: ") + message)
    return EXIT_VALID if ok else EXIT_INVALID


if __name__ == "__main__":
    sys.exit(main())
