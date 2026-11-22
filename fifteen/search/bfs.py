"""Breadth-first search (CONTRACT.md, section 7.3).

Graph search with a FIFO frontier and a global ``visited`` set. States are
added to ``visited`` when generated; the goal test happens at generation
(and on the start state). Optimal in the number of moves.
"""

from __future__ import annotations

from collections import deque
from typing import Deque, Optional

from fifteen.board import Board, State, find_blank
from fifteen.search.common import Node, SearchConfig, expand, make_order, reconstruct_path
from fifteen.stats import SearchStats


def solve(board: Board, start: State, config: SearchConfig, stats: SearchStats) -> Optional[str]:
    stats.visited_states = 1
    stats.update_peak(1)
    if board.is_goal(start):
        return ""

    next_order = make_order(config.order, config.seed)
    goal = board.goal
    visited = {start}
    frontier: Deque[Node] = deque([Node(start, find_blank(start), None, None, 0)])

    while frontier:
        node = frontier.popleft()
        stats.processed_states += 1
        depth = node.g + 1
        for move, state, blank in expand(board, node.state, node.blank, node.move, next_order()):
            stats.visited_states += 1
            if depth > stats.max_depth_reached:
                stats.max_depth_reached = depth
            if state in visited:
                continue
            child = Node(state, blank, node, move, depth)
            visited.add(state)
            if state == goal:
                stats.update_peak(len(visited))
                return reconstruct_path(child)
            frontier.append(child)
        stats.update_peak(len(visited))
    return None
