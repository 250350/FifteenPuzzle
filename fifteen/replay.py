"""Load and validate the step-by-step states displayed by the viewer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fifteen.board import Board, IllegalMoveError, State, find_blank
from fifteen.io import InputError, parse_puzzle, parse_solution


@dataclass(frozen=True)
class Replay:
    """A puzzle and its checked states, including the starting state at index 0."""

    board: Board
    states: tuple[State, ...]
    moves: str | None  # None represents a solver result of -1.


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InputError(f"Cannot read {path.name}: {exc}") from None


def load_replay(puzzle_file: Path, solution_file: Path) -> Replay:
    """Read the two solver files or raise InputError with a displayable message."""
    puzzle_text = _read_text(puzzle_file)
    try:
        board, state = parse_puzzle(puzzle_text)
    except InputError as exc:
        raise InputError(f"Puzzle file {puzzle_file.name}: {exc}") from None

    solution_text = _read_text(solution_file)
    try:
        length, moves = parse_solution(solution_text)
    except InputError as exc:
        message = str(exc).removeprefix("solution: ")
        raise InputError(f"Solution file {solution_file.name}: {message}") from None
    if length == -1:
        return Replay(board, (state,), None)

    states = [state]
    blank = find_blank(state)
    for step, move in enumerate(moves, start=1):
        try:
            state, blank = board.apply(state, blank, move)
        except IllegalMoveError:
            row, col = board.coords(blank)
            raise InputError(
                f"Illegal move {move} at step {step} (blank at row {row + 1}, column {col + 1})."
            ) from None
        states.append(state)
    if not board.is_goal(state):
        raise InputError("The solution does not reach the goal state.")
    return Replay(board, tuple(states), moves)
