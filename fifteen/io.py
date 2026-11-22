"""Parsing of puzzle/solution text and formatting of solver output.

Formats are defined in CONTRACT.md, section 6.
"""

from __future__ import annotations

from typing import Optional, Tuple

from fifteen.board import OPPOSITE, Board, State


class InputError(ValueError):
    """Raised for malformed puzzle or solution text."""


def parse_puzzle(text: str) -> Tuple[Board, State]:
    """Parse puzzle text (``R C`` then ``R*C`` values) into ``(board, state)``.

    Values may be separated by any whitespace (CRLF and tabs are fine).
    Content after the ``R*C`` values is ignored.

    Raises:
        InputError: missing/non-integer values, invalid size, or values that are
            not a permutation of ``0 .. R*C-1``.
    """
    tokens = text.split()
    if len(tokens) < 2:
        raise InputError("expected 'R C' on the first line")
    try:
        rows, cols = int(tokens[0]), int(tokens[1])
    except ValueError:
        raise InputError(f"board size must be two integers, got {tokens[0]!r} {tokens[1]!r}") from None
    if rows < 1 or cols < 1 or rows * cols < 2:
        raise InputError(f"invalid board size {rows}x{cols} (need R,C >= 1 and R*C >= 2)")
    size = rows * cols
    values = tokens[2:2 + size]
    if len(values) < size:
        raise InputError(f"expected {size} values for a {rows}x{cols} board, got {len(values)}")
    try:
        state = tuple(int(v) for v in values)
    except ValueError:
        bad = next(v for v in values if not _is_int(v))
        raise InputError(f"board value {bad!r} is not an integer") from None
    if sorted(state) != list(range(size)):
        raise InputError(f"board values must be a permutation of 0..{size - 1}")
    return Board(rows, cols), state


def _is_int(token: str) -> bool:
    try:
        int(token)
    except ValueError:
        return False
    return True


def format_solution(moves: Optional[str]) -> str:
    """Solver stdout: exactly two newline-terminated lines.

    ``None`` means "not solved" -> ``-1`` and an empty line.
    """
    if moves is None:
        return "-1\n\n"
    return f"{len(moves)}\n{moves}\n"


def parse_solution(text: str) -> Tuple[int, str]:
    """Parse solver output into ``(n, moves)``; ``n == -1`` means no solution.

    Raises:
        InputError: missing/non-integer length, letters outside ``LRUD``, or a
            length that does not match the move string.
    """
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise InputError("solution: first line (length) is missing")
    try:
        n = int(lines[0].strip())
    except ValueError:
        raise InputError(f"solution: length {lines[0].strip()!r} is not an integer") from None
    moves = lines[1].strip() if len(lines) > 1 else ""
    if n == -1:
        if moves:
            raise InputError("solution: length is -1 but the move line is not empty")
        return -1, ""
    if n < 0:
        raise InputError(f"solution: invalid length {n}")
    bad = sorted({m for m in moves if m not in OPPOSITE})
    if bad:
        raise InputError(f"solution: invalid move letters {''.join(bad)!r} (allowed: L R U D)")
    if len(moves) != n:
        raise InputError(f"solution: stated length {n} but {len(moves)} moves given")
    return n, moves
