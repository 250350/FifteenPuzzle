"""Search statistics (CONTRACT.md, section 8)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

RESULT_SOLVED = "solved"
RESULT_NOT_FOUND = "not_found"
RESULT_UNSOLVABLE = "unsolvable"


@dataclass
class SearchStats:
    """Counters for one solver run. Strategies update the counters; the solver
    fills in the metadata, ``result``, ``solution*`` and ``time_ms``."""

    strategy: str = ""
    param: str = ""
    rows: int = 0
    cols: int = 0
    result: str = RESULT_NOT_FOUND
    solution_length: int = -1
    solution: str = ""
    visited_states: int = 0
    processed_states: int = 0
    max_depth_reached: int = 0
    peak_stored_states: int = 0
    time_ms: float = 0.0
    max_depth_limit: Optional[int] = None
    memory_limit: Optional[int] = None
    seed: Optional[int] = None

    def set_solution(self, moves: Optional[str]) -> None:
        """Record the outcome of a finished (solvable) search."""
        if moves is None:
            self.result = RESULT_NOT_FOUND
            self.solution_length = -1
            self.solution = ""
        else:
            self.result = RESULT_SOLVED
            self.solution_length = len(moves)
            self.solution = moves

    def update_peak(self, stored: int) -> None:
        """Track the maximum number of simultaneously stored states."""
        if stored > self.peak_stored_states:
            self.peak_stored_states = stored

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["time_ms"] = round(self.time_ms, 3)
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def write_json(self, path: Union[str, Path]) -> None:
        Path(path).write_text(self.to_json() + "\n", encoding="utf-8")


class Timer:
    """Context manager measuring wall time in milliseconds (``perf_counter``).

    Usage::

        with Timer() as t:
            ...
        t.elapsed_ms
    """

    def __init__(self) -> None:
        self._start = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0
