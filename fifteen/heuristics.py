"""Heuristics for informed search (CONTRACT.md, section 5.3).

All heuristics ignore the blank and are admissible for any R x C board:

* 0 ``zero``            h(x) = 0
* 1 ``hamming``         number of tiles not in their goal cell
* 2 ``manhattan``       sum of tile distances |drow| + |dcol| to the goal cell
* 3 ``linear_conflict`` Manhattan + 2 * (for every row and column: the minimum
  number of tiles to remove so that the tiles already in their goal row/column
  appear in goal order, i.e. ``len - LIS``)

Use ``make_heuristic(hid, board)`` to get a fast ``State -> int`` function with
the goal-position tables precomputed for that board.
"""

from __future__ import annotations

from bisect import bisect_left
from typing import Callable, Dict, List, Sequence

from fifteen.board import Board, State

Heuristic = Callable[[State], int]

HEURISTIC_NAMES: Dict[int, str] = {
    0: "zero",
    1: "hamming",
    2: "manhattan",
    3: "linear_conflict",
}


def make_heuristic(hid: int, board: Board) -> Heuristic:
    """Return heuristic ``hid`` (0..3) specialised for ``board``.

    Raises:
        ValueError: unknown heuristic id.
    """
    if hid == 0:
        return _zero
    if hid == 1:
        return _make_hamming(board)
    if hid == 2:
        return _make_manhattan(board)
    if hid == 3:
        return _make_linear_conflict(board)
    raise ValueError(f"unknown heuristic id {hid!r} (expected 0..3)")


def _zero(state: State) -> int:
    return 0


def _make_hamming(board: Board) -> Heuristic:
    goal = board.goal

    def hamming(state: State) -> int:
        return sum(1 for v, g in zip(state, goal) if v != g and v != 0)

    return hamming


def _distance_table(board: Board) -> List[List[int]]:
    """``table[v][i]`` = Manhattan distance of tile ``v`` at cell ``i`` from its
    goal cell (row 0 = blank, all zeros)."""
    cols = board.cols
    table = [[0] * board.size]
    for v in range(1, board.size):
        gr, gc = divmod(v - 1, cols)
        table.append([abs(i // cols - gr) + abs(i % cols - gc) for i in range(board.size)])
    return table


def _make_manhattan(board: Board) -> Heuristic:
    table = _distance_table(board)
    cells = range(board.size)

    def manhattan(state: State) -> int:
        return sum(table[state[i]][i] for i in cells)

    return manhattan


def removals_to_sort(values: Sequence[int]) -> int:
    """Minimum number of elements to remove so the rest is strictly increasing
    (``len(values) - length of the longest increasing subsequence``)."""
    tails: List[int] = []
    for v in values:
        k = bisect_left(tails, v)
        if k == len(tails):
            tails.append(v)
        else:
            tails[k] = v
    return len(values) - len(tails)


def _make_linear_conflict(board: Board) -> Heuristic:
    rows, cols = board.rows, board.cols
    manhattan = _make_manhattan(board)
    # goal row / column per tile value (index 0 = blank, unused)
    goal_row = [-1] + [(v - 1) // cols for v in range(1, board.size)]
    goal_col = [-1] + [(v - 1) % cols for v in range(1, board.size)]
    row_cells = [range(r * cols, (r + 1) * cols) for r in range(rows)]
    col_cells = [range(c, board.size, cols) for c in range(cols)]

    def linear_conflict(state: State) -> int:
        extra = 0
        for r, cells in enumerate(row_cells):
            line = [goal_col[v] for v in (state[i] for i in cells) if v and goal_row[v] == r]
            if len(line) > 1:
                extra += removals_to_sort(line)
        for c, cells in enumerate(col_cells):
            line = [goal_row[v] for v in (state[i] for i in cells) if v and goal_col[v] == c]
            if len(line) > 1:
                extra += removals_to_sort(line)
        return manhattan(state) + 2 * extra

    return linear_conflict
