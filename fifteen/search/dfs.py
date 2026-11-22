"""Depth-first search with a depth limit (CONTRACT.md, section 7.3).

Iterative (explicit stack, no recursion). Duplicate detection uses a
depth-aware map ``state -> smallest depth seen``: a state is (re)accepted only
when reached at a strictly smaller depth, so the search is complete within
the limit (a plain visited set is not). Goal test at generation.

``depth_limited_search`` is shared with IDFS.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from fifteen.board import Board, State, find_blank
from fifteen.search.common import (
    Node,
    OrderFn,
    SearchConfig,
    expand,
    make_order,
    reconstruct_path,
)
from fifteen.stats import SearchStats


def depth_limited_search(board: Board, start: State, limit: int, next_order: OrderFn,
                         stats: SearchStats) -> Tuple[Optional[str], bool]:
    """One depth-limited DFS from ``start`` (which must not be the goal).

    Returns ``(moves, cutoff)``: ``moves`` is the solution or ``None``;
    ``cutoff`` is True if some node was not expanded because it was at
    ``limit`` (if False and no solution, the reachable space is exhausted).

    Successors are processed in the order given by ``next_order()``: they are
    pushed onto the stack in reverse. Nodes at depth ``limit`` are goal-tested
    when generated but never pushed (they could not be expanded anyway).
    Stale stack entries (a state later reached at a smaller depth) are skipped.
    Updates ``visited_states``, ``processed_states``, ``max_depth_reached`` and
    ``peak_stored_states`` (size of the depth map).
    """
    goal = board.goal
    best: Dict[State, int] = {start: 0}
    stack: List[Node] = [Node(start, find_blank(start), None, None, 0)]
    cutoff = False
    stats.update_peak(1)

    while stack:
        node = stack.pop()
        if best[node.state] < node.g:
            continue  # stale: this state was re-reached at a smaller depth
        stats.processed_states += 1
        depth = node.g + 1
        children: List[Node] = []
        for move, state, blank in expand(board, node.state, node.blank, node.move, next_order()):
            stats.visited_states += 1
            if depth > stats.max_depth_reached:
                stats.max_depth_reached = depth
            seen = best.get(state)
            if seen is not None and seen <= depth:
                continue
            best[state] = depth
            child = Node(state, blank, node, move, depth)
            if state == goal:
                stats.update_peak(len(best))
                return reconstruct_path(child), cutoff
            if depth < limit:
                children.append(child)
            else:
                cutoff = True
        stack.extend(reversed(children))
        stats.update_peak(len(best))
    return None, cutoff


def solve(board: Board, start: State, config: SearchConfig, stats: SearchStats) -> Optional[str]:
    stats.visited_states = 1
    stats.update_peak(1)
    if board.is_goal(start):
        return ""
    if config.max_depth < 1:
        return None
    moves, _ = depth_limited_search(board, start, config.max_depth,
                                    make_order(config.order, config.seed), stats)
    return moves
