"""Board geometry, goal state and move semantics for the R x C sliding puzzle.

A state is an immutable tuple of length ``rows * cols`` in row-major order, where
``0`` is the blank. A move letter is the direction in which a **tile** moves into
the blank (CONTRACT.md, section 4): ``L`` slides the tile on the blank's right
to the left, so the blank itself moves right.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

State = Tuple[int, ...]

MOVES = "LRUD"
OPPOSITE: Dict[str, str] = {"L": "R", "R": "L", "U": "D", "D": "U"}


class IllegalMoveError(ValueError):
    """Raised when no tile can move in the given direction (the blank is on
    that side of the frame)."""


class Board:
    """Geometry of an R x C frame with precomputed neighbour tables.

    Attributes:
        rows, cols: frame dimensions.
        size: ``rows * cols``.
        goal: goal state ``(1, 2, ..., size-1, 0)``.
        targets: ``targets[blank][move]`` is the index of the tile that moves
            into the blank (i.e. where the blank ends up), or ``-1`` if the
            move is illegal for that blank position.
    """

    __slots__ = ("rows", "cols", "size", "goal", "targets")

    def __init__(self, rows: int, cols: int) -> None:
        if rows < 1 or cols < 1 or rows * cols < 2:
            raise ValueError(f"invalid board size {rows}x{cols} (need R,C >= 1 and R*C >= 2)")
        self.rows = rows
        self.cols = cols
        self.size = rows * cols
        self.goal: State = tuple(range(1, self.size)) + (0,)
        self.targets: Tuple[Dict[str, int], ...] = tuple(
            self._compute_targets(i) for i in range(self.size)
        )

    def _compute_targets(self, index: int) -> Dict[str, int]:
        # Letters name the direction of the moving TILE: the tile on the blank's
        # right moves Left, the tile on its left moves Right, the tile below
        # moves Up and the tile above moves Down.
        row, col = divmod(index, self.cols)
        return {
            "L": index + 1 if col < self.cols - 1 else -1,
            "R": index - 1 if col > 0 else -1,
            "U": index + self.cols if row < self.rows - 1 else -1,
            "D": index - self.cols if row > 0 else -1,
        }

    def __repr__(self) -> str:
        return f"Board({self.rows}, {self.cols})"

    # ------------------------------------------------------------------ queries
    def is_goal(self, state: State) -> bool:
        return state == self.goal

    def legal_moves(self, blank: int) -> List[str]:
        """Legal move letters for a blank at ``blank``, in ``LRUD`` order."""
        t = self.targets[blank]
        return [m for m in MOVES if t[m] != -1]

    def coords(self, index: int) -> Tuple[int, int]:
        """(row, col) of a cell index."""
        return divmod(index, self.cols)

    # ------------------------------------------------------------------ moves
    def apply(self, state: State, blank: int, move: str) -> Tuple[State, int]:
        """Apply one move; return ``(new_state, new_blank)``.

        Raises:
            IllegalMoveError: the move is illegal for this blank position.
            KeyError: ``move`` is not one of ``L, R, U, D``.
        """
        target = self.targets[blank][move]
        if target == -1:
            raise IllegalMoveError(f"move {move!r} is illegal with the blank at index {blank}")
        cells = list(state)
        cells[blank] = cells[target]
        cells[target] = 0
        return tuple(cells), target

    def apply_moves(self, state: State, moves: Iterable[str]) -> State:
        """Apply a whole move sequence and return the resulting state.

        Raises:
            IllegalMoveError: a move is illegal (or not one of ``L, R, U, D``);
                the message includes its position (1-based).
        """
        blank = find_blank(state)
        for step, move in enumerate(moves, start=1):
            if move not in OPPOSITE:
                raise IllegalMoveError(f"step {step}: unknown move letter {move!r}")
            try:
                state, blank = self.apply(state, blank, move)
            except IllegalMoveError as exc:
                raise IllegalMoveError(f"step {step}: {exc}") from None
        return state


def find_blank(state: State) -> int:
    """Index of the blank (0) in ``state``."""
    return state.index(0)


def format_state(board: Board, state: State) -> str:
    """Human-readable grid (one row per line); the blank is shown as 0."""
    width = len(str(board.size - 1))
    lines = []
    for r in range(board.rows):
        row = state[r * board.cols:(r + 1) * board.cols]
        lines.append(" ".join(str(v).rjust(width) for v in row))
    return "\n".join(lines)
