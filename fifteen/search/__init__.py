"""Strategy registry.

``STRATEGIES`` maps a strategy name to its ``solve`` function (see
``fifteen.search.common`` for the signature) or ``None`` while it is not
implemented yet. Implemented strategies are registered here as milestones land.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from fifteen.board import Board, State
from fifteen.search import bfs, dfs, idfs
from fifteen.search.common import SearchConfig
from fifteen.stats import SearchStats

SolveFn = Callable[[Board, State, SearchConfig, SearchStats], Optional[str]]

UNINFORMED = ("bfs", "dfs", "idfs")
INFORMED = ("bf", "astar", "sma")

STRATEGIES: Dict[str, Optional[SolveFn]] = {
    "bfs": bfs.solve,
    "dfs": dfs.solve,
    "idfs": idfs.solve,
    "bf": None,     # M4
    "astar": None,  # M4
    "sma": None,    # M5
}


def get_strategy(name: str) -> Optional[SolveFn]:
    """Return the solve function for ``name`` (``None`` if not implemented)."""
    if name not in STRATEGIES:
        raise KeyError(f"unknown strategy {name!r}")
    return STRATEGIES[name]
