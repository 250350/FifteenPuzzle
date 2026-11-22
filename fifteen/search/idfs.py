"""Iterative deepening DFS (CONTRACT.md, section 7.3).

Runs ``depth_limited_search`` for limits ``1, 2, ..., max_depth`` (limit 0 is
just the goal test of the start state) with a fresh depth map per iteration.
Counters are summed over iterations; ``peak_stored_states`` is the largest
depth map of any iteration. The first solution found has optimal length.
Stops early if an iteration had no cutoff (reachable space exhausted).
"""

from __future__ import annotations

from typing import Optional

from fifteen.board import Board, State
from fifteen.search.common import SearchConfig, make_order
from fifteen.search.dfs import depth_limited_search
from fifteen.stats import SearchStats


def solve(board: Board, start: State, config: SearchConfig, stats: SearchStats) -> Optional[str]:
    stats.visited_states = 1
    stats.update_peak(1)
    if board.is_goal(start):
        return ""
    next_order = make_order(config.order, config.seed)  # one RNG for the whole run
    for limit in range(1, config.max_depth + 1):
        stats.visited_states += 1  # the start node is re-created in each iteration
        moves, cutoff = depth_limited_search(board, start, limit, next_order, stats)
        if moves is not None:
            return moves
        if not cutoff:
            return None
    return None
