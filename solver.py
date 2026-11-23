#!/usr/bin/env python3
"""Sliding-puzzle solver (CONTRACT.md, section 5).

Reads a puzzle from stdin and writes exactly two lines to stdout: the solution
length (or -1) and the move string. Example::

    python3 solver.py -a 2 < puzzle.txt
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from fifteen.board import MOVES
from fifteen.io import InputError, format_solution, parse_puzzle
from fifteen.search import INFORMED, get_strategy
from fifteen.search.common import (
    DEFAULT_MAX_DEPTH,
    DEFAULT_MEMORY_LIMIT,
    INFORMED_ORDER,
    RANDOM_ORDER,
    SearchConfig,
)
from fifteen.solvability import is_solvable
from fifteen.stats import RESULT_UNSOLVABLE, SearchStats, Timer

HEURISTIC_IDS = (0, 1, 2, 3)
EXIT_OK = 0
EXIT_USAGE = 2


def order_arg(value: str) -> str:
    """argparse type: a permutation of LRUD, or the single character 'R'."""
    if value == RANDOM_ORDER or (len(value) == 4 and sorted(value) == sorted(MOVES)):
        return value
    raise argparse.ArgumentTypeError(
        f"invalid order {value!r}: expected a permutation of {{L,R,U,D}} (e.g. DULR) or 'R' for random"
    )


def heuristic_arg(value: str) -> int:
    """argparse type: a known heuristic id."""
    try:
        hid = int(value)
    except ValueError:
        hid = -1
    if hid not in HEURISTIC_IDS:
        raise argparse.ArgumentTypeError(
            f"invalid heuristic id {value!r}: expected one of {', '.join(map(str, HEURISTIC_IDS))}"
        )
    return hid


def positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = 0
    if number < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {value!r}")
    return number


def non_negative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        number = -1
    if number < 0:
        raise argparse.ArgumentTypeError(f"expected a non-negative integer, got {value!r}")
    return number


def build_parser() -> argparse.ArgumentParser:
    # add_help=False: '-h' is the Best-first flag, help is only '--help'.
    parser = argparse.ArgumentParser(
        prog="solver.py",
        add_help=False,
        description="Solve an R x C sliding puzzle read from stdin.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-b", "--bfs", type=order_arg, metavar="ORDER", help="breadth-first search")
    group.add_argument("-d", "--dfs", type=order_arg, metavar="ORDER", help="depth-first search")
    group.add_argument("-i", "--idfs", type=order_arg, metavar="ORDER", help="iterative deepening DFS")
    group.add_argument("-h", "--bf", type=heuristic_arg, metavar="ID", help="best-first (greedy) search")
    group.add_argument("-a", "--astar", type=heuristic_arg, metavar="ID", help="A* search")
    group.add_argument("-s", "--sma", type=heuristic_arg, metavar="ID", help="SMA* search")
    parser.add_argument("--max-depth", type=non_negative_int, default=DEFAULT_MAX_DEPTH, metavar="N",
                        help=f"depth limit for DFS/IDFS (default {DEFAULT_MAX_DEPTH})")
    parser.add_argument("--memory-limit", type=positive_int, default=DEFAULT_MEMORY_LIMIT, metavar="N",
                        help=f"node limit for SMA* (default {DEFAULT_MEMORY_LIMIT})")
    parser.add_argument("--seed", type=int, default=None, metavar="N",
                        help="seed for the random order 'R'")
    parser.add_argument("--stats", default=None, metavar="PATH",
                        help="write statistics as JSON to PATH")
    parser.add_argument("--help", action="help", help="show this help message and exit")
    return parser


def config_from_args(args: argparse.Namespace) -> SearchConfig:
    for name in ("bfs", "dfs", "idfs", "bf", "astar", "sma"):
        value = getattr(args, name)
        if value is not None:
            break
    else:  # pragma: no cover - argparse enforces the required group
        raise AssertionError("no strategy selected")
    informed = name in INFORMED
    return SearchConfig(
        strategy=name,
        order=INFORMED_ORDER if informed else value,
        heuristic=value if informed else None,
        max_depth=args.max_depth,
        memory_limit=args.memory_limit,
        seed=args.seed,
    )


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)  # exits with code 2 on bad arguments
    config = config_from_args(args)

    try:
        board, start = parse_puzzle(sys.stdin.read())
    except InputError as exc:
        print(f"solver.py: invalid input: {exc}", file=sys.stderr)
        return EXIT_USAGE

    stats = SearchStats(
        strategy=config.strategy,
        param=str(config.heuristic) if config.strategy in INFORMED else config.order,
        rows=board.rows,
        cols=board.cols,
        max_depth_limit=config.max_depth if config.strategy in ("dfs", "idfs") else None,
        memory_limit=config.memory_limit if config.strategy == "sma" else None,
        seed=config.seed if config.order == RANDOM_ORDER else None,
    )

    moves: Optional[str] = None
    if not is_solvable(board, start):
        stats.result = RESULT_UNSOLVABLE
    else:
        solve = get_strategy(config.strategy)
        if solve is not None:
            with Timer() as timer:
                moves = solve(board, start, config, stats)
            stats.time_ms = timer.elapsed_ms
        stats.set_solution(moves)

    sys.stdout.write(format_solution(moves))
    sys.stdout.flush()
    if args.stats:
        stats.write_json(args.stats)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
