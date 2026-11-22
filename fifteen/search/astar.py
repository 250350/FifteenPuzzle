"""A* search, f = g + h (CONTRACT.md, section 7.3).

Min-heap ordered by ``(f, h, insertion_counter)``: lower f first, then lower h
(deeper nodes), then FIFO. A ``best_g`` map holds the cheapest known cost of
every generated state; a successor is pushed only if it improves ``best_g``
(this also re-opens closed states, so admissible but inconsistent heuristics
stay optimal). Outdated heap entries are skipped when popped (lazy deletion).
Goal test at expansion, so the result is optimal for admissible h.
"""

from __future__ import annotations

import heapq
from itertools import count
from typing import Dict, List, Optional, Tuple

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
    best_g: Dict[State, int] = {start: 0}
    stats.visited_states = 1
    stats.update_peak(1)

    while heap:
        _, _, _, node = heapq.heappop(heap)
        if node.g > best_g[node.state]:
            continue  # stale entry: a cheaper path to this state was found later
        if node.state == goal:
            return reconstruct_path(node)
        stats.processed_states += 1
        g = node.g + 1
        for move, state, blank in expand(board, node.state, node.blank, node.move, next_order()):
            stats.visited_states += 1
            if g > stats.max_depth_reached:
                stats.max_depth_reached = g
            known = best_g.get(state)
            if known is not None and known <= g:
                continue
            best_g[state] = g
            hv = h(state)
            heapq.heappush(heap, (g + hv, hv, next(counter), Node(state, blank, node, move, g)))
        stats.update_peak(len(best_g))
    return None
