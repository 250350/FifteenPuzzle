#!/usr/bin/env python3
"""Replay a sliding puzzle solution in a Tk window (CONTRACT.md, section 9)."""

from __future__ import annotations

import argparse
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, font, ttk

from fifteen.io import InputError
from fifteen.replay import Replay, load_replay

SPEEDS = (1, 2, 4, 8)  # steps per second


class _Viewer:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.replay: Replay | None = None
        self.step = 0
        self.timer: str | None = None
        self.font_family = font.nametofont("TkDefaultFont").actual("family")

        root.title("Fifteen Puzzle Viewer")
        root.geometry("680x640")
        root.minsize(470, 410)

        menu = tk.Menu(root)
        files = tk.Menu(menu, tearoff=False)
        files.add_command(label="Open…", underline=0, accelerator="Ctrl+O", command=self._open)
        menu.add_cascade(label="File", underline=0, menu=files)
        root.configure(menu=menu)

        content = ttk.Frame(root, padding=(20, 16))
        content.pack(fill="both", expand=True)
        header = ttk.Frame(content)
        header.pack(fill="x", pady=(0, 10))
        self.position = ttk.Label(header, text="Solution replay",
                                  font=(self.font_family, 17, "bold"))
        self.position.pack(side="left")
        self.detail = ttk.Label(header)
        self.detail.pack(side="right")

        board_frame = ttk.Frame(content)
        board_frame.pack(fill="both", expand=True)
        board_frame.columnconfigure(0, weight=1)
        board_frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(board_frame, background="#edf2f8", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scroll_x = ttk.Scrollbar(board_frame, orient="horizontal", command=self.canvas.xview)
        scroll_y = ttk.Scrollbar(board_frame, orient="vertical", command=self.canvas.yview)
        scroll_x.grid(row=1, column=0, sticky="ew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(xscrollcommand=scroll_x.set, yscrollcommand=scroll_y.set)
        self.canvas.bind("<Configure>", self._draw_board)

        timeline = ttk.Frame(content)
        timeline.pack(fill="x", pady=(12, 8))
        self.slider_value = tk.IntVar(root)
        self.slider = tk.Scale(timeline, from_=0, to=1, orient="horizontal", showvalue=False,
                               highlightthickness=0, variable=self.slider_value,
                               command=lambda value: self._navigate(int(value)))
        self.slider.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ttk.Label(timeline, text="Step").pack(side="left", padx=(0, 5))
        self.step_value = tk.StringVar(root, value="0")
        self.entry = ttk.Entry(timeline, textvariable=self.step_value, width=6)
        self.entry.pack(side="left")
        self.entry.bind("<Return>", self._jump)
        self.jump = ttk.Button(timeline, text="Go", width=5, command=self._jump)
        self.jump.pack(side="left", padx=(6, 0))

        controls = ttk.Frame(content)
        controls.pack(fill="x")
        self.first = ttk.Button(controls, text="First", width=6, command=lambda: self._navigate(0))
        self.prev = ttk.Button(controls, text="Prev", width=6, command=lambda: self._move(-1))
        self.next = ttk.Button(controls, text="Next", width=6, command=lambda: self._move(1))
        self.last = ttk.Button(controls, text="Last", width=6,
                               command=lambda: self._navigate(self._last_step()))
        self.play = ttk.Button(controls, text="Play", width=7, command=self._toggle_play)
        for button in (self.first, self.prev, self.next, self.last, self.play):
            button.pack(side="left", padx=(0, 5))
        self.speed = ttk.Combobox(controls, values=[f"{rate} steps/s" for rate in SPEEDS],
                                  state="readonly", width=10)
        self.speed.current(1)
        self.speed.pack(side="right")
        ttk.Label(controls, text="Speed").pack(side="right", padx=(0, 5))
        self.speed.bind("<<ComboboxSelected>>", self._speed_changed)

        self.feedback = ttk.Label(content, foreground="#a12a32", justify="left")
        self.feedback.pack(fill="x", pady=(8, 0))
        self.feedback.bind("<Configure>", self._wrap_feedback)
        self._bind_keys()
        self._show_step(0)

    def _bind_keys(self) -> None:
        actions = {
            "<Left>": lambda: self._move(-1),
            "<Right>": lambda: self._move(1),
            "<Home>": lambda: self._navigate(0),
            "<End>": lambda: self._navigate(self._last_step()),
            "<space>": self._toggle_play,
        }

        def invoke(event, action, sequence):
            if event.widget is self.entry and sequence != "<space>":
                return None  # Keep the usual cursor movement in the step entry.
            action()
            return "break"

        # Bind focusable widgets directly so their class bindings cannot also
        # handle a shortcut (for example, Space on a focused button).
        for widget in (self.root, self.slider, self.entry, self.jump, self.first, self.prev,
                       self.next, self.last, self.play, self.speed, self.canvas):
            for sequence, action in actions.items():
                if widget is self.entry and sequence != "<space>":
                    continue
                widget.bind(
                    sequence, lambda event, cmd=action, seq=sequence: invoke(event, cmd, seq),
                )
        self.root.bind("<Control-o>", self._open)

    def _open(self, _event=None) -> None:
        self._pause()
        puzzle = filedialog.askopenfilename(parent=self.root, title="Open puzzle file")
        if not puzzle:
            return
        solution = filedialog.askopenfilename(parent=self.root, title="Open solution file",
                                              initialdir=Path(puzzle).parent)
        if solution:
            self._load(Path(puzzle), Path(solution))

    def _load(self, puzzle: Path, solution: Path) -> None:
        try:
            replay = load_replay(puzzle, solution)
        except InputError as exc:
            self.feedback.configure(text=str(exc))
            return
        self.replay = replay
        self.feedback.configure(text="")
        self.slider.configure(to=max(1, self._last_step()))
        self._show_step(0)
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def _wrap_feedback(self, event: tk.Event) -> None:
        self.feedback.configure(wraplength=event.width)

    def _last_step(self) -> int:
        return len(self.replay.states) - 1 if self.replay is not None else 0

    def _show_step(self, step: int) -> None:
        self.step = step
        last = self._last_step()
        self.slider_value.set(step)
        self.step_value.set(str(step))
        if self.replay is not None:
            moves = self.replay.moves
            position = "No solution" if moves is None else f"Step {step} / {last}"
            self.position.configure(text=position)
            if step > 0:
                detail = f"Move {moves[step - 1]}"
            elif moves == "":
                detail = "Already at the goal"
            else:
                detail = "Start position"
            self.detail.configure(text=detail)
        for widget in (self.first, self.prev):
            widget.state(["!disabled" if step > 0 else "disabled"])
        for widget in (self.next, self.last):
            widget.state(["!disabled" if step < last else "disabled"])
        for widget in (self.entry, self.jump, self.play, self.speed):
            widget.state(["!disabled" if last > 0 else "disabled"])
        self.slider.configure(state="normal" if last > 0 else "disabled")
        self._draw_board()

    def _draw_board(self, _event=None) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if self.replay is None:
            canvas.configure(scrollregion=(0, 0, width, height))
            canvas.create_text(
                width / 2, height / 2, text="Open a puzzle and its saved solution.\nFile → Open…",
                justify="center", fill="#364763", font=(self.font_family, 12),
            )
            return

        board = self.replay.board
        margin = 18
        cell = max(32, min(98, (width - 2 * margin) // board.cols,
                           (height - 2 * margin) // board.rows))
        board_width, board_height = cell * board.cols, cell * board.rows
        area_width = max(width, board_width + 2 * margin)
        area_height = max(height, board_height + 2 * margin)
        canvas.configure(scrollregion=(0, 0, area_width, area_height))
        x0 = (area_width - board_width) // 2
        y0 = (area_height - board_height) // 2
        canvas.create_rectangle(x0 - 5, y0 - 5, x0 + board_width + 5, y0 + board_height + 5,
                                fill="#22314a", width=0)
        digits = len(str(board.size - 1))
        text_size = min(30, cell // 3, (cell - 8) // digits)
        tile_font = (self.font_family, -text_size, "bold")
        gap = max(2, cell // 24)
        for index, value in enumerate(self.replay.states[self.step]):
            row, col = board.coords(index)
            x, y = x0 + col * cell, y0 + row * cell
            canvas.create_rectangle(x + gap, y + gap, x + cell - gap, y + cell - gap,
                                    fill="#fafcff" if value else "#3a4e6c", width=0)
            if value:
                canvas.create_text(x + cell / 2, y + cell / 2, text=str(value),
                                   fill="#172b4d", font=tile_font)

    def _navigate(self, step: int) -> None:
        clamped = max(0, min(step, self._last_step()))
        if clamped != self.step:
            self._pause()
            self.feedback.configure(text="")
            self._show_step(clamped)

    def _move(self, delta: int) -> None:
        self._navigate(self.step + delta)

    def _jump(self, _event=None) -> None:
        last = self._last_step()
        if last == 0:
            return
        try:
            step = int(self.step_value.get())
        except ValueError:
            step = -1
        if 0 <= step <= last:
            self._pause()
            self.feedback.configure(text="")
            self._show_step(step)
        else:
            self.feedback.configure(text=f"Enter a step from 0 to {last}.")

    def _pause(self) -> None:
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self.timer = None
        self.play.configure(text="Play")

    def _schedule(self) -> None:
        self.timer = self.root.after(1000 // SPEEDS[self.speed.current()], self._tick)

    def _toggle_play(self) -> None:
        if self.timer is not None:
            self._pause()
        elif self._last_step() > 0:
            if self.step == self._last_step():
                self._show_step(0)
            self.feedback.configure(text="")
            self.play.configure(text="Pause")
            self._schedule()

    def _tick(self) -> None:
        self.timer = None
        self._show_step(self.step + 1)
        if self.step < self._last_step():
            self._schedule()
        else:
            self.play.configure(text="Play")

    def _speed_changed(self, _event: tk.Event) -> None:
        if self.timer is not None:
            self.root.after_cancel(self.timer)
            self._schedule()


def main(argv: list[str] | None = None) -> int:
    """Open an optional puzzle/solution pair and run the viewer event loop."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzle_file", nargs="?", type=Path)
    parser.add_argument("solution_file", nargs="?", type=Path)
    args = parser.parse_args(argv)
    if (args.puzzle_file is None) != (args.solution_file is None):
        parser.error("provide both a puzzle file and a solution file, or neither")

    root = tk.Tk()
    app = _Viewer(root)
    if args.puzzle_file is not None:
        app._load(args.puzzle_file, args.solution_file)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
