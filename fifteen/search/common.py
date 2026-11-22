"""Shared definitions for all search strategies.

Strategy signature (every strategy module exposes ``solve`` with it)::

    def solve(board: Board, start: State, config: SearchConfig,
              stats: SearchStats) -> Optional[str]

It returns the move string (``""`` if ``start`` is the goal) or ``None`` when no
solution was found, and updates the counters in ``stats``. Timing and the
solvability check are done by the caller (``solver.py``).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Iterator, List, Optional, Sequence, Tuple

from fifteen.board import MOVES, OPPOSITE, Board, State

DEFAULT_MAX_DEPTH = 20
DEFAULT_MEMORY_LIMIT = 100_000
INFORMED_ORDER = "LRUD"
RANDOM_ORDER = "R"

OrderFn = Callable[[], Sequence[str]]


@dataclass(frozen=True)
class SearchConfig:
    """Parameters of one run, built from the CLI.

    Attributes:
        strategy: ``bfs``, ``dfs``, ``idfs``, ``bf``, ``astar`` or ``sma``.
        order: 4-letter permutation, or ``"R"`` (random); informed strategies
            get ``INFORMED_ORDER``.
        heuristic: heuristic id 0..3 for informed strategies, else ``None``.
        max_depth: depth limit for DFS/IDFS.
        memory_limit: node limit for SMA*.
        seed: seed for the random order, or ``None``.
    """

    strategy: str
    order: str = INFORMED_ORDER
    heuristic: Optional[int] = None
    max_depth: int = DEFAULT_MAX_DEPTH
    memory_limit: int = DEFAULT_MEMORY_LIMIT
    seed: Optional[int] = None


class Node:
    """Search-tree node. ``move`` is the letter that produced it from ``parent``
    (``None`` for the root); ``g`` is its depth / path cost."""

    __slots__ = ("state", "blank", "parent", "move", "g")

    def __init__(self, state: State, blank: int, parent: Optional["Node"],
                 move: Optional[str], g: int) -> None:
        self.state = state
        self.blank = blank
        self.parent = parent
        self.move = move
        self.g = g

    def __repr__(self) -> str:
        return f"Node(g={self.g}, move={self.move!r}, state={self.state})"


def reconstruct_path(node: Node) -> str:
    """Move string from the root to ``node`` (follows parent pointers)."""
    moves: List[str] = []
    while node.parent is not None:
        moves.append(node.move)  # type: ignore[arg-type]
        node = node.parent
    moves.reverse()
    return "".join(moves)


def make_order(order: str, seed: Optional[int] = None) -> OrderFn:
    """Return a function giving the move order for one expansion.

    A fixed permutation always returns the same tuple; ``"R"`` returns a fresh
    random permutation of ``LRUD`` on every call (one RNG per run, seeded with
    ``seed``).
    """
    if order == RANDOM_ORDER:
        rng = random.Random(seed)
        return lambda: rng.sample(MOVES, len(MOVES))
    if len(order) != 4 or sorted(order) != sorted(MOVES):
        raise ValueError(f"invalid order {order!r}")
    fixed = tuple(order)
    return lambda: fixed


def expand(board: Board, state: State, blank: int, parent_move: Optional[str],
           moves: Sequence[str]) -> Iterator[Tuple[str, State, int]]:
    """Yield ``(move, child_state, child_blank)`` in the given move order.

    Illegal moves are skipped, as is the move that would undo ``parent_move``
    (reverse-move pruning, CONTRACT.md section 4).
    """
    targets = board.targets[blank]
    reverse = OPPOSITE[parent_move] if parent_move is not None else None
    for move in moves:
        if move == reverse:
            continue
        target = targets[move]
        if target == -1:
            continue
        cells = list(state)
        cells[blank] = cells[target]
        cells[target] = 0
        yield move, tuple(cells), target
