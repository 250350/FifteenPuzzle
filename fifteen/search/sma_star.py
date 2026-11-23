"""Memory-bounded A* with one successor at a time and backed-up costs."""

from __future__ import annotations

import heapq
from itertools import count
from math import inf

from fifteen.board import OPPOSITE, Board, State, find_blank
from fifteen.heuristics import make_heuristic
from fifteen.search.common import INFORMED_ORDER, Node, SearchConfig, reconstruct_path
from fifteen.stats import SearchStats

_Priority = tuple[float, int, int]


class _Queue:
    """Keep priorities by node id (signed in the key to control FIFO ties)."""

    def __init__(self) -> None:
        self._heap: list[_Priority] = []
        self._keys: dict[int, _Priority] = {}

    def update(self, serial: int, key: _Priority | None) -> None:
        if self._keys.get(serial) == key:
            return
        if key is None:
            del self._keys[serial]
        else:
            self._keys[serial] = key
            heapq.heappush(self._heap, key)
        # Obsolete priorities hold no node references and are compacted here.
        if len(self._heap) > 2 * len(self._keys):
            self._heap = list(self._keys.values())
            heapq.heapify(self._heap)

    def first(self) -> _Priority | None:
        while self._heap:
            key = self._heap[0]
            if self._keys.get(abs(key[-1])) == key:
                return key
            heapq.heappop(self._heap)
        return None


class _Node(Node):
    __slots__ = ("serial", "h", "bound", "f", "pending", "children", "forgotten")
    parent: _Node | None

    def __init__(self, state: State, blank: int, parent: _Node | None,
                 move: str | None, serial: int, h: int, f: float) -> None:
        super().__init__(state, blank, parent, move, 0 if parent is None else parent.g + 1)
        self.serial = serial
        self.h = h
        self.bound = self.f = f
        self.pending: str | None = None   # None until the first expansion
        self.children: dict[str, int] = {}
        self.forgotten: dict[str, float] = {}

    def available_f(self) -> float:
        # Any untried move may still achieve the bound inherited at creation.
        if self.pending is None or self.pending:
            return self.bound
        return min(self.forgotten.values(), default=inf)


class _Search:
    def __init__(self, board: Board, config: SearchConfig, stats: SearchStats) -> None:
        self.board = board
        self.limit = config.memory_limit
        self.stats = stats
        self.heuristic = make_heuristic(config.heuristic or 0, board)
        self.serials = count()
        self.nodes: dict[int, _Node] = {}
        self.frontier = _Queue()
        self.restorable = _Queue()
        self.leaves = _Queue()

    def _backup(self, node: _Node | None) -> None:
        while node is not None:
            available = node.available_f()
            best_child = min((self.nodes[i].f for i in node.children.values()), default=inf)
            old_f = node.f
            node.f = min(available, best_child)
            serial = node.serial
            fresh = available < inf and node.pending != ""
            forgotten = available < inf and node.pending == ""
            self.frontier.update(serial, (available, node.h, serial) if fresh else None)
            self.restorable.update(serial, (available, -node.g, serial) if forgotten else None)
            if node.f == inf and node.parent is not None:
                # An exhausted branch only needs its infinity marker.
                self._detach(node)
                node = node.parent
                continue
            self.leaves.update(serial, (-node.f, node.g, -serial) if not node.children else None)
            if node.f == old_f:
                break
            node = node.parent

    def _worst_leaf(self, parent: _Node) -> _Priority:
        # Inserting a child needs its parent to stay in the tree.
        worst = self.leaves.first()
        if worst is not None and -worst[-1] == parent.serial:
            self.leaves.update(parent.serial, None)
            alternative = self.leaves.first()
            self.leaves.update(parent.serial, worst)
            worst = alternative
        assert worst is not None  # A full tree with only one leaf is a path at the depth limit.
        return worst

    def _detach(self, leaf: _Node) -> None:
        parent = leaf.parent
        assert parent is not None and leaf.move is not None and not leaf.children
        del self.nodes[leaf.serial]
        self.frontier.update(leaf.serial, None)
        self.restorable.update(leaf.serial, None)
        self.leaves.update(leaf.serial, None)
        parent.forgotten[leaf.move] = leaf.f
        del parent.children[leaf.move]

    def _forget(self, serial: int) -> None:
        leaf = self.nodes[serial]
        self._detach(leaf)
        self._backup(leaf.parent)

    def _select(self) -> _Node | None:
        fresh = self.frontier.first()
        forgotten = self.restorable.first()
        # On equal bounds, finish resident work first. When only forgotten
        # alternatives remain at that bound, restore the deepest first so its
        # new leaf survives the shallowest-leaf eviction rule.
        if forgotten is not None and (fresh is None or forgotten[0] < fresh[0]):
            return self.nodes[forgotten[-1]]
        return self.nodes[fresh[-1]] if fresh is not None else None

    def _generate(self, node: _Node) -> None:
        if node.pending is None:
            self.stats.processed_states += 1
            reverse = OPPOSITE[node.move] if node.move is not None else None
            targets = self.board.targets[node.blank]
            node.pending = "".join(m for m in INFORMED_ORDER if m != reverse and targets[m] != -1)
            if not node.pending:
                self._backup(node)
                return

        bound = node.available_f()
        if node.pending:
            move = node.pending[0]
        else:
            move = min(node.forgotten, key=node.forgotten.__getitem__)
        state, blank = self.board.apply(node.state, node.blank, move)
        g = node.g + 1
        self.stats.visited_states += 1
        self.stats.max_depth_reached = max(self.stats.max_depth_reached, g)
        h = self.heuristic(state)
        f = max(bound, g + h)
        if f >= self.limit or (g == self.limit - 1 and state != self.board.goal):
            f = inf
        # A repeated state on this path cannot improve a solution.
        ancestor: _Node | None = node
        while ancestor is not None:
            if state == ancestor.state:
                f = inf
                break
            ancestor = ancestor.parent

        serial = next(self.serials)
        keep = f < inf
        if keep and len(self.nodes) == self.limit:
            worst = self._worst_leaf(node)
            keep = (-f, g, -serial) > worst
            if keep:
                # Release the victim before creating the new node.
                self._forget(-worst[-1])
        if node.pending:
            node.pending = node.pending[1:]
        if keep:
            node.forgotten.pop(move, None)
            self.nodes[serial] = _Node(state, blank, node, move, serial, h, f)
            node.children[move] = serial
            self._backup(self.nodes[serial])
            self.stats.update_peak(len(self.nodes))
        else:
            node.forgotten[move] = f
        self._backup(node)

    def run(self, start: State) -> str | None:
        h = self.heuristic(start)
        f = inf if h >= self.limit or (self.limit == 1 and start != self.board.goal) else h
        root = _Node(start, find_blank(start), None, None, next(self.serials), h, f)
        self.nodes[root.serial] = root
        self.stats.visited_states = 1
        self.stats.update_peak(len(self.nodes))
        self._backup(root)

        while (node := self._select()) is not None:
            if node.state == self.board.goal:
                return reconstruct_path(node)
            self._generate(node)
        return None


def solve(board: Board, start: State, config: SearchConfig, stats: SearchStats) -> str | None:
    """Find a solution using at most ``config.memory_limit`` stored nodes."""
    if config.memory_limit < 1:
        raise ValueError("memory_limit must be positive")
    return _Search(board, config, stats).run(start)
