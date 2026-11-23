#!/usr/bin/env python3
"""Run and resume the solver experiment matrix (CONTRACT.md, section 10.3)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import platform
import re
import subprocess
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fifteen.board import MOVES  # noqa: E402
from fifteen.io import InputError, parse_puzzle, parse_solution  # noqa: E402
from fifteen.search import UNINFORMED  # noqa: E402
from fifteen.search.common import DEFAULT_MAX_DEPTH, DEFAULT_MEMORY_LIMIT  # noqa: E402
from fifteen.stats import RESULT_NOT_FOUND, RESULT_SOLVED, RESULT_UNSOLVABLE  # noqa: E402
from solver import HEURISTIC_IDS, non_negative_int, positive_int  # noqa: E402
from tools.generate import DEFAULT_OUT  # noqa: E402
from tools.verify import verify_text  # noqa: E402

FLAGS = {"bfs": "-b", "dfs": "-d", "idfs": "-i", "bf": "-h", "astar": "-a", "sma": "-s"}
ORDERS = ("RDUL", "RDLU", "DRUL", "DRLU", "LUDR", "LURD", "ULDR", "ULRD")
HEURISTICS = tuple(map(str, HEURISTIC_IDS))
PUZZLE_NAME = re.compile(r"(\d+)x(\d+)_(\d{2,})_(\d{5,})\.txt", re.ASCII)
COUNTERS = ("visited_states", "processed_states", "max_depth_reached", "peak_stored_states")
METRICS = (*COUNTERS, "time_ms")
COLUMNS = ("puzzle", "rows", "cols", "depth", "strategy", "param", "result", "solution_length",
           *METRICS, "verified")
SOLVER_RESULTS = (RESULT_SOLVED, RESULT_NOT_FOUND, RESULT_UNSOLVABLE)
FAILURES = ("timeout", "error", "invalid")
DEFAULT_OUTPUT = ROOT / "results" / "results.csv"
Key = tuple[str, str, str]


@dataclass(frozen=True)
class _Puzzle:
    name: str
    rows: int
    cols: int
    depth: int
    text: str


def _is_order(param: str) -> bool:
    return param == "R" or sorted(param) == sorted(MOVES)


def _puzzles(directory: Path, patterns: list[str]) -> list[_Puzzle]:
    puzzles = []
    for path in sorted(directory.glob("*.txt")):
        if patterns and not any(fnmatchcase(path.name, pattern) for pattern in patterns):
            continue
        match = PUZZLE_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError(f"{path.name} does not use the generator's puzzle filename format")
        rows, cols, depth, _ = map(int, match.groups())
        # Keep the input snapshot used to identify and run this experiment.
        text = path.read_bytes().decode("utf-8")
        board, _ = parse_puzzle(text)
        if (board.rows, board.cols) != (rows, cols):
            raise ValueError(f"{path.name} does not match the board dimensions in the file")
        puzzles.append(_Puzzle(path.name, rows, cols, depth, text))
    if not puzzles:
        raise ValueError(f"no matching puzzles in {directory}. Run tools/generate.py first")
    return puzzles


def _pairs(args: argparse.Namespace) -> list[tuple[str, str]]:
    requested = tuple(dict.fromkeys(args.param))
    for param in requested:
        if param not in HEURISTICS and not _is_order(param):
            raise ValueError(f"unknown parameter {param!r}")
    pairs = []
    for strategy in FLAGS:
        if args.strategy and strategy not in args.strategy:
            continue
        if strategy in UNINFORMED:
            defaults = [p for p in ORDERS if not requested or p in requested]
            extra = sorted(p for p in requested if _is_order(p) and p not in ORDERS)
            params = defaults + extra
        else:
            params = [p for p in HEURISTICS if p in requested] if requested else HEURISTICS
        pairs.extend((strategy, param) for param in params)
    if not pairs:
        raise ValueError("no compatible strategy and parameter pairs selected")
    if any(param == "R" for _, param in pairs) and args.seed is None:
        raise ValueError("the random order R requires --seed for a resumable experiment")
    return pairs


def _digest(records) -> str:
    digest = hashlib.sha256()
    for name, data in records:
        digest.update(name.encode("utf-8") + b"\0" + hashlib.sha256(data).digest())
    return digest.hexdigest()


def _manifest(args: argparse.Namespace, puzzles: list[_Puzzle], pairs: list[tuple[str, str]]) -> dict:
    paths = [ROOT / "solver.py", ROOT / "tools" / "verify.py", Path(__file__).resolve()]
    paths.extend(sorted((ROOT / "fifteen").glob("*.py")))
    paths.extend(sorted((ROOT / "fifteen" / "search").glob("*.py")))
    return {
        "timeout_s": args.timeout,
        "max_depth": args.max_depth,
        "memory_limit": args.memory_limit,
        "seed": args.seed,
        "pairs": [list(pair) for pair in pairs],
        "puzzles": len(puzzles),
        "puzzles_sha256": _digest((p.name, p.text.encode("utf-8")) for p in puzzles),
        "code_sha256": _digest((p.relative_to(ROOT).as_posix(), p.read_bytes()) for p in paths),
        "machine_sha256": hashlib.sha256(platform.node().encode("utf-8")).hexdigest(),
        "platform": f"{platform.system()} {platform.release()} {platform.machine()}",
        "python": f"{platform.python_implementation()} {platform.python_version()}",
    }


@contextmanager
def _output_lock(output: Path):
    # Leave the lock file in place so concurrent invocations always lock the
    # same file. The OS releases the lock when the process exits or is killed.
    lock_path = output.with_name(output.name + ".lock.tmp")
    with lock_path.open("a+b") as lock:
        try:
            if os.name == "nt":
                import msvcrt

                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError(f"cannot lock {output}. Another runner may be active") from exc
        yield


def _sync(stream) -> None:
    stream.flush()
    os.fsync(stream.fileno())


def _check_manifest(output: Path, manifest: dict) -> None:
    path = output.with_name(output.name + ".meta.json")
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved != manifest:
            changed = ", ".join(k for k in manifest if not isinstance(saved, dict)
                                or manifest[k] != saved.get(k))
            raise ValueError(f"experiment configuration differs ({changed or 'metadata'}). "
                             "Use a different --output")
    elif output.exists():
        raise ValueError(f"missing experiment metadata {path.name}. Use a different --output")
    else:
        temp = path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(manifest, stream, indent=2)
            stream.write("\n")
            _sync(stream)
        temp.replace(path)


def _non_negative(value: str) -> bool:
    return value.isascii() and value.isdecimal()


def _complete(row: dict[str, str]) -> bool:
    result = row["result"]
    length = row["solution_length"]
    if result in FAILURES:
        return (row["verified"] == "false" and length == "-1"
                and all(row[field] == "" for field in METRICS))
    if result not in SOLVER_RESULTS:
        return False
    if not all(_non_negative(row[field]) for field in COUNTERS):
        return False
    time_ms = float(row["time_ms"])
    if not math.isfinite(time_ms) or time_ms < 0:
        return False
    if result == RESULT_SOLVED:
        return row["verified"] == "true" and _non_negative(length)
    return row["verified"] == "false" and length == "-1"


def _completed(output: Path, expected: dict[Key, _Puzzle]) -> tuple[set[Key], Counter]:
    if not output.exists():
        return set(), Counter()
    data = output.read_bytes()
    end = data.rfind(b"\n") + 1
    rows = csv.reader(io.StringIO(data[:end].decode("utf-8"), newline=""), strict=True)
    if end and tuple(next(rows)) != COLUMNS:
        raise ValueError(f"unexpected CSV header in {output}")
    completed: set[Key] = set()
    counts: Counter = Counter()
    for number, values in enumerate(rows, start=2):
        if len(values) != len(COLUMNS) or any("\n" in value or "\r" in value for value in values):
            raise ValueError(f"malformed CSV row {number} in {output}")
        row = dict(zip(COLUMNS, values))
        key = (row["puzzle"], row["strategy"], row["param"])
        puzzle = expected.get(key)
        if puzzle is None or key in completed:
            raise ValueError(f"unexpected or duplicate key {key} at CSV row {number}")
        try:
            complete = _complete(row)
        except ValueError:
            complete = False
        if not complete or (row["rows"], row["cols"], row["depth"]) != (
                str(puzzle.rows), str(puzzle.cols), str(puzzle.depth)):
            raise ValueError(f"incomplete or inconsistent CSV row {number} for {key}")
        completed.add(key)
        counts[row["result"]] += 1
    if end < len(data):
        with output.open("r+b") as stream:
            stream.truncate(end)
            _sync(stream)
        print(f"Discarded an interrupted final CSV write ({len(data) - end} bytes).", flush=True)
    return completed, counts


def _statistics(path: Path, args: argparse.Namespace, puzzle: _Puzzle, strategy: str,
                param: str, length: int, moves: str) -> dict:
    stats = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "strategy": strategy, "param": param, "rows": puzzle.rows, "cols": puzzle.cols,
        "solution_length": length, "solution": moves,
        "max_depth_limit": args.max_depth if strategy in ("dfs", "idfs") else None,
        "memory_limit": args.memory_limit if strategy == "sma" else None,
        "seed": args.seed if param == "R" else None,
    }
    if any(stats[field] != value for field, value in expected.items()):
        raise ValueError("solver statistics do not match the attempt or stdout")
    result = stats["result"]
    if result not in SOLVER_RESULTS or (result == RESULT_SOLVED) != (length >= 0):
        raise ValueError("solver result conflicts with stdout")
    if any(type(stats[field]) is not int or stats[field] < 0 for field in COUNTERS):
        raise ValueError("invalid search counter in solver statistics")
    time_ms = stats["time_ms"]
    if type(time_ms) not in (int, float) or not math.isfinite(time_ms) or time_ms < 0:
        raise ValueError("invalid search time in solver statistics")
    return stats


def _run(args: argparse.Namespace, puzzle: _Puzzle, strategy: str, param: str,
         stats_path: Path) -> tuple[dict, str]:
    row = dict(puzzle=puzzle.name, rows=puzzle.rows, cols=puzzle.cols, depth=puzzle.depth,
               strategy=strategy, param=param, result="error", solution_length=-1, verified="false")
    command = [sys.executable, "-X", "utf8", str(ROOT / "solver.py"), FLAGS[strategy], param,
               "--stats", str(stats_path), "--max-depth", str(args.max_depth),
               "--memory-limit", str(args.memory_limit)]
    if param == "R":
        command.extend(("--seed", str(args.seed)))
    stats_path.unlink(missing_ok=True)
    try:
        proc = subprocess.run(command, cwd=ROOT, input=puzzle.text.encode("utf-8"),
                              capture_output=True, timeout=args.timeout)
        stdout = proc.stdout.decode("utf-8")
        stderr = proc.stderr.decode("utf-8")
    except subprocess.TimeoutExpired:
        row["result"] = "timeout"
        return row, f"exceeded {args.timeout:g} s"
    except (OSError, UnicodeError) as exc:
        return row, str(exc)
    if proc.returncode != 0 or stderr:
        return row, f"solver exit {proc.returncode}. {stderr.strip()}"

    try:
        length, moves = parse_solution(stdout)
        if length >= 0:
            valid, message = verify_text(puzzle.text, stdout)
            if not valid:
                row["result"] = "invalid"
                return row, message
    except InputError as exc:
        row["result"] = "invalid"
        return row, str(exc)

    try:
        stats = _statistics(stats_path, args, puzzle, strategy, param, length, moves)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        return row, f"invalid solver statistics. {exc}"
    row.update((field, stats[field]) for field in METRICS)
    row.update(result=stats["result"], solution_length=length,
               verified="true" if length >= 0 else "false")
    return row, ""


def _experiment(args: argparse.Namespace) -> None:
    pairs = _pairs(args)
    puzzles = _puzzles(args.puzzles_dir, args.puzzle)
    expected = {(p.name, strategy, param): p for p in puzzles for strategy, param in pairs}
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with _output_lock(output):
        _check_manifest(output, _manifest(args, puzzles, pairs))
        completed, counts = _completed(output, expected)
        total = len(expected)
        print(f"{len(puzzles)} puzzles x {len(pairs)} parameter pairs = {total} attempts. "
              f"Resuming with {len(completed)} complete rows.", flush=True)
        with (tempfile.TemporaryDirectory(prefix="fifteen-stats-") as tmp,
              output.open("a", encoding="utf-8", newline="") as stream):
            stats_path = Path(tmp) / "stats.json"
            writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator="\n")
            if stream.tell() == 0:
                writer.writeheader()
                _sync(stream)
            done = len(completed)
            for key, puzzle in expected.items():
                if key in completed:
                    continue
                row, detail = _run(args, puzzle, key[1], key[2], stats_path)
                writer.writerow(row)
                _sync(stream)
                done += 1
                counts[row["result"]] += 1
                if detail:
                    print(f"{' '.join(key)} {row['result']}: {detail}", file=sys.stderr, flush=True)
                if done % 100 == 0 or done == total:
                    print(f"{done}/{total} attempts saved.", flush=True)
        print(", ".join(f"{name}={counts[name]}" for name in (*SOLVER_RESULTS, *FAILURES)),
              flush=True)


def main(argv: list[str] | None = None) -> int:
    """Run, resume or summarize an experiment selected through the CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puzzles-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--puzzle", action="append", default=[], metavar="GLOB",
                        help="select puzzle filenames (repeatable, default: all)")
    parser.add_argument("--strategy", action="append", choices=tuple(FLAGS), default=[],
                        help="select a strategy (repeatable, default: all)")
    parser.add_argument("--param", action="append", default=[], metavar="PARAM",
                        help="select an order or heuristic id (repeatable, default: matrix)")
    parser.add_argument("--timeout", type=float, default=60.0, metavar="SECONDS")
    parser.add_argument("--max-depth", type=non_negative_int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--memory-limit", type=positive_int, default=DEFAULT_MEMORY_LIMIT)
    parser.add_argument("--seed", type=int, help="seed for random order R")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    try:
        _experiment(args)
    except KeyboardInterrupt:
        print("Interrupted. Rerun the same command to resume.", file=sys.stderr)
        return 130
    except (OSError, ValueError, csv.Error) as exc:
        print(f"run_experiments.py: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
