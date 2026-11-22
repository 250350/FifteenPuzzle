"""Greedy best-first search, f = h (CONTRACT.md, section 7.3).

Min-heap ordered by ``(f, h, insertion_counter)`` (FIFO on ties). A state is
skipped if it was already generated (closed or in the open set), so every
state enters the heap at most once. Goal test at expansion. Not optimal.
"""

from __future__ import annotations

import heapq
from itertools import count
from typing import List, Optional, Tuple

from fifteen.board import Board, State, find_blank
from fifteen.heuristics import make_heuristic
from fifteen.search.common import Node, SearchConfig, expand, make_order, reconstruct_path
from fifteen.stats import SearchStats

HeapEntry = Tuple[int, int, int, Node]


def solve(board: Board, start: State, config: SearchConfig, stats: SearchStats) -> Optional[str]:
    h = make_heuristic(config.heuristic if config.heuristic is not None else 0, board)
    next_order = make_order(config.order, config.seed)
    goal = board.goal
    counter = count()

    h0 = h(start)
    heap: List[HeapEntry] = [(h0, h0, next(counter), Node(start, find_blank(start), None, None, 0))]
    seen = {start}  # closed set + states currently in the open set
    stats.visited_states = 1
    stats.update_peak(1)

    while heap:
        _, _, _, node = heapq.heappop(heap)
        if node.state == goal:
            return reconstruct_path(node)
        stats.processed_states += 1
        depth = node.g + 1
        for move, state, blank in expand(board, node.state, node.blank, node.move, next_order()):
            stats.visited_states += 1
            if depth > stats.max_depth_reached:
                stats.max_depth_reached = depth
            if state in seen:
                continue
            seen.add(state)
            hv = h(state)
            heapq.heappush(heap, (hv, hv, next(counter), Node(state, blank, node, move, depth)))
        stats.update_peak(len(seen))
    return None
