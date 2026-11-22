"""Solvability check (CONTRACT.md, section 7.1)."""

from __future__ import annotations

from fifteen.board import Board, State, find_blank


def count_inversions(values: State) -> int:
    """Number of pairs ``i < j`` with ``values[i] > values[j]``."""
    n = len(values)
    return sum(1 for i in range(n) for j in range(i + 1, n) if values[i] > values[j])


def is_solvable(board: Board, state: State) -> bool:
    """Return True iff ``state`` can reach ``board.goal``.

    * ``R, C >= 2``: with the blank treated as ``R*C``, the permutation parity
      must equal the parity of the blank's Manhattan distance from its goal cell
      (every move is one transposition and moves the blank by one cell).
    * Single line (``R == 1`` or ``C == 1``): tiles never pass each other, so
      the non-blank tiles must already be in order.
    """
    if board.rows == 1 or board.cols == 1:
        tiles = [v for v in state if v != 0]
        return tiles == list(range(1, board.size))
    full = tuple(board.size if v == 0 else v for v in state)
    blank_row, blank_col = board.coords(find_blank(state))
    blank_distance = (board.rows - 1 - blank_row) + (board.cols - 1 - blank_col)
    return count_inversions(full) % 2 == blank_distance % 2
