"""Shared definitions for all search strategies.

Strategy signature (every strategy module exposes ``solve`` with it)::

    def solve(board: Board, start: State, config: SearchConfig,
              stats: SearchStats) -> Optional[str]

It returns the move string (``""`` if ``start`` is the goal) or ``None`` when no
solution was found, and updates the counters in ``stats``. Timing and the
solvability check are done by the caller (``solver.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DEFAULT_MAX_DEPTH = 20
DEFAULT_MEMORY_LIMIT = 100_000
INFORMED_ORDER = "LRUD"
RANDOM_ORDER = "R"


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
