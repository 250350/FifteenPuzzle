#!/usr/bin/env python3
"""Generate every puzzle at each exact optimal distance (CONTRACT.md, section 10.1).

A full BFS from the goal (no reverse-move pruning, global visited set) assigns
each reachable state its optimal distance ``d``. Every state with
``1 <= d <= max_depth`` is written to its own file in solver input format::

    {out}/{R}x{C}_{d:02d}_{k:05d}.txt      (k = 1, 2, ... within each depth)

The order inside a depth is deterministic: the BFS tries the blank directions
left, right, up, down (move letters ``RLDU``, since letters name the direction
of the moving tile). This fixed physical order keeps file numbering identical
to the puzzle set used for the published results, independent of the letter
convention, so the same file always holds the same puzzle.

Usage::

    python3 tools/generate.py                      # 4x4, depths 1..7 -> data/puzzles
    python3 tools/generate.py --rows 3 --cols 3 --max-depth 10 --out data/puzzles
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fifteen.board import Board, State, find_blank  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "puzzles"
# Blank goes left, right, up, down = tile moves R, L, D, U (see module docstring).
GENERATION_ORDER = "RLDU"


def states_by_depth(board: Board, max_depth: int) -> Dict[int, List[State]]:
    """Map ``d -> [states at optimal distance d]`` for ``d = 0 .. max_depth``."""
    layers: Dict[int, List[State]] = {0: [board.goal]}
    seen = {board.goal}
    current = [board.goal]
    for depth in range(1, max_depth + 1):
        nxt: List[State] = []
        for state in current:
            blank = find_blank(state)
            for move in GENERATION_ORDER:
                if board.targets[blank][move] == -1:
                    continue
                child, _ = board.apply(state, blank, move)
                if child not in seen:
                    seen.add(child)
                    nxt.append(child)
        layers[depth] = nxt
        current = nxt
        if not nxt:
            break
    return layers


def puzzle_text(board: Board, state: State) -> str:
    rows = [
        " ".join(str(v) for v in state[r * board.cols:(r + 1) * board.cols])
        for r in range(board.rows)
    ]
    return f"{board.rows} {board.cols}\n" + "\n".join(rows) + "\n"


def puzzle_filename(board: Board, depth: int, index: int) -> str:
    return f"{board.rows}x{board.cols}_{depth:02d}_{index:05d}.txt"


def write_puzzles(board: Board, max_depth: int, out_dir: Path) -> Dict[int, int]:
    """Write all puzzles for depths ``1..max_depth``; return ``{depth: count}``.

    Old files of the same board size in ``out_dir`` are removed first so the set
    is always exactly the generated one.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"{board.rows}x{board.cols}_*.txt"):
        old.unlink()
    counts: Dict[int, int] = {}
    for depth, states in states_by_depth(board, max_depth).items():
        if depth == 0:
            continue
        for index, state in enumerate(states, start=1):
            path = out_dir / puzzle_filename(board, depth, index)
            path.write_text(puzzle_text(board, state), encoding="utf-8", newline="\n")
        counts[depth] = len(states)
    return counts


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate puzzles at every exact optimal distance.")
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--max-depth", type=int, default=7)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        board = Board(args.rows, args.cols)
    except ValueError as exc:
        parser.error(str(exc))
    if args.max_depth < 1:
        parser.error("--max-depth must be >= 1")

    counts = write_puzzles(board, args.max_depth, args.out)
    for depth, count in counts.items():
        print(f"depth {depth:2d}: {count} puzzles")
    print(f"total: {sum(counts.values())} puzzles in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
