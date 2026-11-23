# Fifteen Puzzle — Project Contract

This document is the single source of truth for the project. All code, tools and the report
must follow it. Any change to it must be agreed on first and recorded in the
[Change log](#13-change-log).

Key words: **MUST** = mandatory, **SHOULD** = strong default, **MAY** = optional.

---

## 1. Scope and deliverables

| # | Deliverable | Entry point |
|---|-------------|-------------|
| D1 | Solver: CLI program, verifiable on Linux, reads stdin and writes stdout | `solver.py` |
| D2 | Viewer: GUI that replays a solution step by step, with jumps | `viewer.py` |
| D3 | Experiment tooling: generator, batch runner, verifier, plots | `tools/` |
| D4 | Technical report with an empirical comparison of all strategies | `report/` |

Compulsory strategies: **BFS, DFS, IDFS, Best-first (greedy), A\*, SMA\***. No additional
strategies are in scope.

---

## 2. Environment and technical rules

- **Language:** Python. All code MUST run on **Python 3.10+**. The usual lab Linux is Ubuntu 22.04,
  which ships 3.10. Development uses the 3.14 venv, so do NOT use 3.11+ features
  (`tomllib`, `typing.Self`, `except*`, PEP 695 `type`/generic syntax, etc.).
- **Dependencies:** `solver.py`, `viewer.py` and the `fifteen/` package MUST use the **standard
  library only** (the viewer uses `tkinter`). `tools/plot.py` MAY use `matplotlib`, and that
  dependency goes in `requirements-tools.txt`.
- **Linux compatibility:**
  - every entry-point script starts with `#!/usr/bin/env python3`
  - **LF** line endings, enforced by `.gitattributes` with `* text=auto eol=lf`
  - UTF-8 encoding
  - paths built with `pathlib` only, no hard-coded Windows paths
  - file names are lowercase
- **Language of artifacts:** everything is in English: code, identifiers, comments, docstrings,
  this contract, and file names.
- **Style:** PEP 8, type hints on public functions, docstrings on modules and public functions.
- **Tests:** `unittest` (stdlib), in `tests/`, run with `python3 -m unittest`.
- **Linux check:** before every milestone the solver MUST be run on real Linux (WSL Ubuntu or a VM)
  through stdin/stdout.

---

## 3. Project layout

```
FifteenPuzzle/
├── CONTRACT.md
├── README.md                 # how to run everything
├── .gitattributes
├── solver.py                 # D1 entry point (CLI only, no algorithm logic)
├── viewer.py                 # D2 entry point
├── fifteen/                  # core package (stdlib only)
│   ├── __init__.py
│   ├── board.py              # Board model, moves, goal, neighbour tables
│   ├── io.py                 # input parsing/validation, output formatting
│   ├── solvability.py        # parity check
│   ├── heuristics.py         # heuristic registry (ids 0..3)
│   ├── stats.py              # SearchStats + JSON serialization
│   └── search/
│       ├── __init__.py       # strategy registry
│       ├── common.py         # Node, path reconstruction, order handling
│       ├── bfs.py
│       ├── dfs.py
│       ├── idfs.py
│       ├── best_first.py
│       ├── astar.py
│       └── sma_star.py
├── tools/
│   ├── generate.py           # test-puzzle generator
│   ├── run_experiments.py    # batch runner -> CSV
│   ├── verify.py             # solution checker
│   └── plot.py               # charts for the report
├── tests/
├── data/puzzles/             # generated puzzles (inputs)
├── results/                  # CSV + stats JSON from experiments
└── report/                   # report sources + figures
```

---

## 4. Board model and conventions

- **Dimensions:** `R` rows and `C` columns, with `R >= 1`, `C >= 1` and `R*C >= 2`. The code MUST
  NOT assume 4×4.
- **State:** an immutable `tuple[int, ...]` of length `R*C` in **row-major** order. `0` is the blank.
  Cell index `i` corresponds to `row = i // C`, `col = i % C`.
- **Goal state:** `1, 2, ..., R*C-1, 0`, so the blank is in the bottom-right corner.
- **Move semantics:** a move letter describes the movement of the **blank** (empty field):

  | Letter | Blank moves | Index change | Legal when |
  |--------|-------------|--------------|------------|
  | `L` | left  | `i - 1` | `col > 0` |
  | `R` | right | `i + 1` | `col < C-1` |
  | `U` | up    | `i - C` | `row > 0` |
  | `D` | down  | `i + C` | `row < R-1` |

  Example: if the blank is to the right of tile `5`, then `L` swaps them and the blank ends up
  where `5` was.
- **Opposite moves:** `L↔R`, `U↔D`.
- **Reverse-move pruning:** ALL strategies MUST skip the successor produced by the move opposite
  to the move that created the current node. The start node has no parent move, so all its legal
  moves are generated.
- **Neighbour tables:** legal moves per blank index are precomputed once per board size.

---

## 5. Solver CLI (D1)

### 5.1 Invocation

```
python3 solver.py STRATEGY_FLAG PARAM [OPTIONS] < input.txt
```

Exactly **one** strategy flag is REQUIRED (they are mutually exclusive):

| Short | Long | Param | Strategy |
|-------|------|-------|----------|
| `-b` | `--bfs`   | order | Breadth-first search |
| `-d` | `--dfs`   | order | Depth-first search |
| `-i` | `--idfs`  | order | Iterative deepening DFS |
| `-h` | `--bf`    | heuristic id | Best-first (greedy, `f = h`) |
| `-a` | `--astar` | heuristic id | A\* (`f = g + h`) |
| `-s` | `--sma`   | heuristic id | SMA\* (`f = g + h`, memory bounded) |

`-h` is a strategy flag, NOT help. The parser MUST be created with `add_help=False`, and help is
available only via `--help`.

### 5.2 `order` parameter

- A **4-character permutation** of `{L, R, U, D}` (case-sensitive, uppercase), e.g. `DULR` or
  `RDUL`, means a fixed successor order: successors are generated (and, for stacks, pushed) so
  that they are **processed** in this order.
- The **single character `R`** means **random**: every expanded node gets its own random
  permutation of the four moves.
- Anything else is an error (see 5.5).
- Informed strategies (`-h`, `-a`, `-s`) generate successors in the fixed order **`LRUD`**.

### 5.3 Heuristic ids

| Id | Name | Definition | Admissible |
|----|------|------------|------------|
| `0` | Zero | `h(x) = 0` | yes |
| `1` | Hamming | number of tiles (blank excluded) not in their goal cell | yes |
| `2` | Manhattan | sum over tiles (blank excluded) of `|Δrow| + |Δcol|` to the goal cell | yes |
| `3` | Linear conflict | Manhattan + `2 ×` (minimum number of tiles to remove from each row/column so that tiles already in their goal row/column are ordered) | yes |

Any other id is an error.

### 5.4 Optional flags

| Flag | Default | Applies to | Meaning |
|------|---------|------------|---------|
| `--max-depth N` | `20` | `-d`, `-i` | Maximum search depth (number of moves) |
| `--memory-limit N` | `100000` | `-s` | Maximum number of nodes SMA\* may store |
| `--seed N` | none | `R` order | Seed for the random order, for reproducibility |
| `--stats PATH` | none | all | Write statistics as JSON to `PATH` (section 8) |
| `--help` | — | — | Print usage and exit 0 |

A flag that doesn't apply to the chosen strategy is accepted and ignored.

### 5.5 Errors and exit codes

| Situation | stdout | stderr | Exit |
|-----------|--------|--------|------|
| Search finished: solved, not found, or unsolvable | 2 lines (section 6.2) | nothing | `0` |
| Invalid CLI arguments | nothing | message + usage | `2` |
| Invalid input (format, dimensions, not a permutation) | nothing | message | `2` |

---

## 6. Input and output format

### 6.1 Input (stdin)

```
R C
a11 a12 ... a1C
...
aR1 aR2 ... aRC
```

- Values are separated by **any whitespace**. Parse with `split()` so CRLF, tabs and extra spaces are
  tolerated.
- The `R*C` values MUST be a permutation of `0 .. R*C-1`. Anything else is invalid input.
- Trailing content after the board is ignored.

### 6.2 Output (stdout)

Always **exactly two lines**, each ending with `\n`:

| Case | Line 1 | Line 2 |
|------|--------|--------|
| Solved | `n` (solution length) | `n` letters from `{L,R,U,D}` |
| Start is already the goal | `0` | empty |
| Not solved (unsolvable, depth/memory limit, exhausted) | `-1` | empty |

Nothing else may be written to stdout.

---

## 7. Search semantics

### 7.1 Solvability

The solver MUST check solvability **before** searching. If the board is unsolvable, it prints `-1`
and an empty line immediately, and the stats `result` is `"unsolvable"`.

Rule for `R >= 2` and `C >= 2` (blank's goal at bottom-right): treat the blank as the value
`R*C`. The board is solvable **iff**
`parity(number of inversions of the full permutation) == parity(Manhattan distance of the blank from its goal cell)`.

Rule for `R == 1` or `C == 1` (a single line): tiles can never pass each other, so the board is
solvable **iff** the non-blank tiles, read in row-major order, are already `1, 2, …, R*C-1`. The
parity rule is NOT sufficient here.

### 7.2 Common rules

- The path is rebuilt from parent pointers plus the move letter stored per node. Path strings are not
  copied into nodes.
- Goal test timing:
  - **BFS, DFS, IDFS:** at **generation** (when a successor is created), and also on the start state.
  - **Best-first, A\*, SMA\*:** at **expansion** (when a node is taken from the frontier). This
    keeps A\*/SMA\* optimal.
- Priority-queue tie-breaking (informed strategies): `(f, h, insertion_counter)`. Lower `f` comes
  first, then lower `h`, then **FIFO**.

### 7.3 Per strategy

| Strategy | Frontier | Duplicate handling | Limits | Optimal |
|----------|----------|--------------------|--------|---------|
| BFS | FIFO queue | global `visited` set; a state is added when generated and generated states that are already visited are skipped | none | yes |
| DFS | explicit stack (no recursion) | **depth-aware map** `state → smallest depth seen`; a state is (re)accepted only if reached at a strictly smaller depth | `--max-depth` (nodes at the limit are not expanded) | no |
| IDFS | DLS for limits `0, 1, …, max_depth` | depth-aware map, **fresh for each iteration** | `--max-depth` | yes (shortest within limit) |
| Best-first | min-heap on `f = h` | closed set; states already closed or already in the open set are skipped | none | no |
| A\* | min-heap on `f = g + h` | `best_g` map; push if `g < best_g[state]` (re-opening allowed); stale heap entries are skipped (lazy deletion) | none | yes (admissible h) |
| SMA\* | ordered by `f`, AIMA version | stored-node count ≤ `--memory-limit`. When memory is full, drop the **shallowest leaf with the highest `f`** and store its `f` in the parent. Successors are generated one at a time. `f` values are backed up to ancestors | `--memory-limit`. A node at depth `memory_limit - 1` that isn't the goal gets `f = ∞` | yes, if the shallowest optimal solution fits in memory |

Random order (`R`): uses one `random.Random(seed)` instance per run, shuffled for each expanded
node.

---

## 8. Statistics

Collected for every run in a `SearchStats` object. Written as JSON only when `--stats PATH` is given.

| Field | Type | Definition |
|-------|------|------------|
| `strategy` | str | `bfs`, `dfs`, `idfs`, `bf`, `astar`, `sma` |
| `param` | str | order string or heuristic id |
| `rows`, `cols` | int | board size |
| `result` | str | `solved`, `not_found`, `unsolvable` |
| `solution_length` | int | length of the solution, or `-1` |
| `solution` | str | the move string (empty if none) |
| `visited_states` | int | number of nodes **created**: the start node plus every successor produced by the move generator after reverse-move pruning, **including** ones later discarded as duplicates. IDFS: summed over all iterations |
| `processed_states` | int | number of nodes **expanded** (successor generation was run on them). IDFS: summed over iterations |
| `max_depth_reached` | int | largest depth (`g`) of any created node |
| `peak_stored_states` | int | maximum, over the run, of the number of **distinct states** held in the algorithm's data structures (frontier ∪ visited/closed/depth map), each state counted once. BFS: size of `visited` (it contains the frontier). DFS/IDFS: size of the depth map. Best-first/A\*: size of the closed set plus open entries not yet closed. SMA\*: stored nodes |
| `time_ms` | float | wall time of the **search only** (excluding parsing, solvability check and I/O), `time.perf_counter`, rounded to 3 decimals |
| `max_depth_limit` | int \| null | `--max-depth` used (DFS/IDFS) |
| `memory_limit` | int \| null | `--memory-limit` used (SMA\*) |
| `seed` | int \| null | seed used for the random order |

Unsolvable boards: counters are `0` and `time_ms` is `0.0`.

---

## 9. Viewer (D2)

- **Invocation:** `python3 viewer.py PUZZLE_FILE SOLUTION_FILE`
  - `PUZZLE_FILE`: solver input format (section 6.1)
  - `SOLUTION_FILE`: solver output format (section 6.2), i.e. the saved stdout
  - Both MAY be selected from a File → Open dialog instead.
- **Technology:** `tkinter`, stdlib only.
- **Features (MUST):**
  - draw the R×C board, with the blank visibly distinct
  - **Prev / Next** step, **First / Last**
  - **jump** to any step via a slider and a numeric entry
  - show the current step `k / n` and the move letter being applied
  - **autoplay** with adjustable speed (play/pause)
  - keyboard shortcuts: ←/→ step, Home/End, Space play/pause
- **Validation:** it uses the same `fifteen.board` move semantics. An illegal move, a bad length,
  or a final state that isn't the goal is reported clearly in the UI and doesn't crash it.
  `-1` is shown as "no solution".

---

## 10. Tools (D3)

### 10.1 Generator (`tools/generate.py`)

- BFS from the goal (with reverse-move pruning **disabled** and a full visited set), producing
  **all** states whose **optimal** distance equals `d`, for `d = 1 .. D` (default board 4×4,
  `D = 7`, 413 puzzles).
- Output: one file per puzzle, `data/puzzles/{R}x{C}_{d:02d}_{k:05d}.txt`, in solver input format.

### 10.2 Verifier (`tools/verify.py`)

- `verify.py PUZZLE_FILE SOLUTION_FILE` applies the moves and checks that they are legal, that the
  stated `n` matches the string length, and that the goal is reached.
- Exit codes:
  - `0` valid: the moves reach the goal, or the solution is `-1` and the puzzle is unsolvable
  - `1` invalid: an illegal move, the goal is not reached, or `-1` is reported for a solvable puzzle
  - `2` usage error, unreadable file, or malformed puzzle/solution text (including a length mismatch)
- Used automatically by the batch runner on every solved result.

### 10.3 Batch runner (`tools/run_experiments.py`)

- Calls `solver.py` **as a subprocess through stdin/stdout** (the same way it is graded) with
  `--stats`.
- Per-run timeout: default **60 s**, configurable. A timeout is recorded with
  `result = "timeout"`.
- Default matrix:
  - `bfs`, `dfs`, `idfs` × orders **`RDUL, RDLU, DRUL, DRLU, LUDR, LURD, ULDR, ULRD`**
  - `bf`, `astar`, `sma` × heuristics **`0, 1, 2, 3`**
  - (optional) the random order `R`, repeated with several seeds
- Output CSV `results/results.csv`, one row per run, with columns:
  `puzzle, rows, cols, depth, strategy, param, result, solution_length, visited_states,
  processed_states, max_depth_reached, peak_stored_states, time_ms, verified`.
- Runs on **one machine** (preferably Linux/WSL) so timings are comparable.

### 10.4 Plots (`tools/plot.py`)

- Reads the CSV and produces, for each metric, the **mean vs. optimal depth**:
  - comparing strategies
  - within a strategy, by order or heuristic
- State counts are plotted on a log scale. Output is PNG/PDF to `report/figures/`.

---

## 11. Report (D4)

Structure: Introduction → Problem formalisation (state space, branching factor, solvability) →
Algorithms and heuristics (with admissibility notes) → Implementation → Experimental setup
(machine, Python version, puzzle set, limits) → Results (charts and tables) → Discussion →
Conclusions → References (Russell & Norvig, AIMA).

---

## 12. Milestones

The project is built in the milestones below, **in order**. Work on a milestone MUST NOT start
until the previous one is ✅ Done.

### 12.1 Milestone workflow (rules)

1. Each milestone has a **Status**:
   - ⬜ Not started
   - 🔄 In progress
   - ✅ Done
2. A milestone is **Done** only when **every** requirement in its list is met and checked
   (tests run, commands executed). Partial completion does not count.
3. When a milestone is Done, its **Requirements** block MUST be **replaced** in this file by a
   **Completion summary** containing:
   - **What was built:** the files/modules added or changed.
   - **How it works:** a short description of the design, key data structures, and the public
     functions/signatures the next milestones depend on.
   - **Decisions and deviations:** anything decided during the work that the contract didn't
     specify, or any deviation from it (deviations MUST also be logged in the Change log).
   - **How to verify:** the exact commands to run the tests or demo.
   - **Known limitations:** open issues carried forward, if any.
4. The summary should be brief (roughly 10–25 lines) but enough for the next milestone to build on
   it without rereading all the code.
5. Status changes and summaries are recorded in the Change log (section 13).

### 12.2 Milestone list

| # | Milestone | Status |
|---|-----------|--------|
| M1 | Foundations: board model, I/O, solvability, stats, CLI, verifier | ✅ Done |
| M2 | BFS + end-to-end solver + puzzle generator | ✅ Done |
| M3 | DFS + IDFS | ✅ Done |
| M4 | Heuristics + Best-first + A\* | ✅ Done |
| M5 | SMA\* | ✅ Done |
| M6 | Viewer | ✅ Done |
| M7 | Batch runner + full experiment run | ⬜ Not started |
| M8 | Plots + report + final acceptance | ⬜ Not started |

---

### M1 — Foundations

**Status:** ✅ Done (2026-11-22)

**Completion summary:**
- **What was built:**
  - `fifteen/board.py`, `fifteen/io.py`, `fifteen/solvability.py`, `fifteen/stats.py`
  - `fifteen/search/__init__.py` (registry) and `fifteen/search/common.py` (`SearchConfig`)
  - `solver.py` and `tools/verify.py`
  - `tests/` (38 tests)
  - `.gitattributes`, `.gitignore`, `README.md`
  - empty `data/puzzles/`, `results/` and `report/` (each holds a `.gitkeep`)
- **How it works:**
  - `Board(rows, cols)` holds the geometry. `board.goal` is the goal state. `board.targets[blank][move]`
    is the precomputed index the blank moves to, or `-1` if the move is illegal. Helpers:
    `board.apply(state, blank, move) -> (state, blank)` (raises `IllegalMoveError`),
    `board.apply_moves(state, moves)`, `board.legal_moves(blank)` (in `LRUD` order) and
    `board.is_goal(state)`. Module-level helpers: `find_blank(state)` and
    `format_state(board, state)`. Constants: `MOVES = "LRUD"` and `OPPOSITE`. A state is a
    `tuple[int, ...]` (alias `State`).
  - `io.py`: `parse_puzzle(text) -> (Board, State)` and `parse_solution(text) -> (n, moves)` both
    raise `InputError`. `format_solution(moves | None)` returns exactly two lines, and `None`
    gives `-1`.
  - `solvability.is_solvable(board, state)` implements section 7.1, including the single-line case.
  - `stats.SearchStats`: a dataclass with the section 8 fields, plus `set_solution(moves|None)`,
    `update_peak(n)` and `write_json(path)`. `stats.Timer` is a `perf_counter` context manager.
  - `search/common.py` defines the **strategy signature**
    `solve(board, start, config: SearchConfig, stats: SearchStats) -> Optional[str]` (returns `""` if
    the start is the goal, `None` if not found) and `SearchConfig(strategy, order, heuristic,
    max_depth, memory_limit, seed)`, plus the default constants. `search/__init__.py`:
    `STRATEGIES` maps a name to a solve function (all `None` for now), and `get_strategy(name)`
    looks one up. A later milestone registers its strategy by setting the dict entry.
  - Flow of `solver.py`:
    1. argparse with `add_help=False`; invalid arguments exit 2 with a usage message
    2. parse stdin; invalid input exits 2 with a message on stderr
    3. fill the stats metadata
    4. if the board is unsolvable: `result = "unsolvable"`, print `-1`
    5. otherwise time `solve()` (search only), print the two lines, and optionally write `--stats` JSON
    
    Unimplemented strategies print `-1` with `result = "not_found"`.
  - `tools/verify.py` uses the same modules (it adds the repo root to `sys.path`) and follows the
    exit-code rules in section 10.2.
- **Decisions and deviations:**
  - Section 7.1 now has a separate rule for single-line (1×N, N×1) boards.
  - Section 10.2 now specifies how `-1` is handled and adds exit code 2.
  - The timer and the call to `set_solution` live in `solver.py`, so strategies only update the
    counters.
  - Informed strategies get `config.order = "LRUD"`.
  - The stats `seed` field is filled only for the `R` order. `max_depth_limit` and
    `memory_limit` are filled only for the strategies they apply to.
- **How to verify:**
  - `python3 -m unittest` from the repo root, on Windows and on WSL Ubuntu 22.04 (Python 3.10.12):
    38/38 pass.
  - `./solver.py -b RDUL < puzzle.txt` works on Linux, and invalid arguments or input give exit code 2.
  - Solvability is tested against an exhaustive BFS ground truth for every permutation of the
    2×2, 2×3, 3×2, 1×2..4 and 3..4×1 boards.
- **Known limitations:** none. All strategies print `-1` until they are implemented.

---

### M2 — BFS + end-to-end solver + puzzle generator

**Status:** ✅ Done (2026-11-22)

**Completion summary:**
- **What was built:**
  - `fifteen/search/common.py`, extended with `Node`, `reconstruct_path`, `make_order` and `expand`
  - `fifteen/search/bfs.py`, registered in `fifteen/search/__init__.py`
  - `tools/generate.py`
  - `tools/__init__.py`, so tests can import the tools
  - `tests/test_bfs.py`
  - README section on the generator
- **How it works (the API later strategies reuse):**
  - `Node(state, blank, parent, move, g)` uses `__slots__`. `move` is the letter that produced the
    node (`None` for the root). `reconstruct_path(node)` follows parent pointers.
  - `make_order(order, seed) -> OrderFn`: call it **once per expansion** to get the move sequence.
    A fixed order always returns the same tuple. `"R"` returns a new permutation on each call
    from one `random.Random(seed)` per run.
  - `expand(board, state, blank, parent_move, moves)` yields `(move, child_state, child_blank)` in
    the given order. It already applies the legality check **and reverse-move pruning**, so no
    strategy needs to repeat them.
  - `bfs.solve`:
    - records the start in stats (`visited_states = 1`, peak 1) and returns `""` if the start is the goal
    - keeps a FIFO `deque` of `Node`s and a global `visited` set
    - for each popped node: `processed += 1`, then for each successor: `visited_states += 1` and
      `max_depth_reached` updated (duplicates included), and duplicates are skipped
    - adds new states to `visited` and **goal-tests at generation**
    - `peak_stored_states = len(visited)`, updated after each expansion
  - `tools/generate.py`:
    - `states_by_depth(board, max_depth)` does a full BFS from the goal (no pruning) and returns
      `{d: [states]}` in a deterministic order (`LRUD`)
    - `write_puzzles(board, max_depth, out)` deletes the old `{R}x{C}_*.txt` files and writes the
      new set
    - `puzzle_text(board, state)` returns the solver input format
    - CLI: `--rows --cols --max-depth --out` (defaults 4, 4, 7, `data/puzzles`)
- **Decisions and deviations:**
  - The section 8 definition of `peak_stored_states` was changed to count each **distinct** state
    once (frontier + visited would double-count in BFS).
  - Generated puzzles are **not committed** (`.gitignore`); run `tools/generate.py` after cloning.
  - `.gitignore` now excludes `.idea/`, `.claude/` and the venv, so the repo holds only source,
    tests, docs and final results.
- **How to verify:**
  - `python3 -m unittest`: 56/56 pass on Windows and WSL Ubuntu 22.04 (Python 3.10.12). The tests
    include:
    - BFS gives length exactly `d` on all 413 puzzles × 8 orders, each verified
    - seeded `R` order
    - start = goal
    - 2×3, 3×2, 3×4, 2×4 boards against the exact distances
    - 1×4 and 3×1 boards
    - generator counts `2, 4, 10, 24, 54, 107, 212` and the full 2×3 space (360 states)
  - `python3 tools/generate.py`, then `./solver.py -b RDUL < data/puzzles/4x4_07_00001.txt` gives
    `7` and `LLLDRRR`.
  - In WSL, a bash loop ran all 413 puzzles through the CLI and `verify.py`: 0 failures.
- **Known limitations:**
  - BFS keeps every visited state in memory, so in Python it is practical up to about depth 15–18
    on a 4×4 board.
  - On an unsolvable board BFS would exhaust the space; `solver.py` prevents this with the
    solvability check.

---

### M3 — DFS + IDFS

**Status:** ✅ Done (2026-11-22)

**Completion summary:**
- **What was built:**
  - `fifteen/search/dfs.py` and `fifteen/search/idfs.py`, both registered in
    `fifteen/search/__init__.py`
  - `tests/test_dfs_idfs.py`
  - README examples, plus a note on the slow tests
- **How it works:**
  - `dfs.depth_limited_search(board, start, limit, next_order, stats) -> (moves | None, cutoff)` is
    the shared core. The caller has already goal-tested `start`.
    - It keeps an explicit stack of `Node`s and a depth map `best: state -> smallest depth`.
    - A popped node with `best[state] < node.g` is stale and gets skipped.
    - A successor is accepted only if it is new or reached at a **strictly smaller** depth. It is
      **goal-tested at generation**.
    - Successors at depth `limit` are goal-tested but never pushed (this sets `cutoff = True`).
    - Successors are pushed in reverse, so they are **processed in the given order**.
    - `peak_stored_states = len(best)`.
  - `dfs.solve`: handles start = goal (`""`), returns `None` when `max_depth < 1`, and otherwise
    makes one call with `limit = max_depth`.
  - `idfs.solve` runs limits `1..max_depth` with a fresh map each time (limit 0 is just the goal
    test of the start).
    - It uses **one** `OrderFn`/RNG for the whole run, so a seeded `R` order is reproducible.
    - Counters are summed; the start node counts once per iteration in `visited_states`.
    - `peak_stored_states` is the largest map of any iteration.
    - It stops early when an iteration had no cutoff (the space is exhausted).
- **Decisions and deviations:**
  - Nodes at the limit are not pushed at all, instead of being pushed and then not expanded.
    The behaviour is the same and it saves memory.
  - The IDFS early stop on "no cutoff" is an addition; it only matters for tiny or unsolvable
    spaces.
  - The full default-limit DFS check is the opt-in test `FIFTEEN_SLOW=1` (it takes about 45 min),
    so the normal suite stays fast.
- **How to verify:**
  - `python3 -m unittest`: 71 pass and 1 is skipped (the slow test), on Windows and WSL Ubuntu
    22.04. The suite covers:
    - IDFS optimal on 413 × 8 orders, each verified
    - DFS with `max_depth = d` (a tight limit) finds a length-`d` solution on 413 × 8, which shows
      the depth map makes it complete
    - a limit that is too small returns `-1` for both strategies
    - an instrumented re-expansion test, plus cases where a plain visited set fails but our DFS
      succeeds
    - successor order checked with a spy on `expand`
    - start = goal, `max_depth 0`, 1×4, 3×1, 2×3, 3×4 and 2×4 boards
    - a seeded `R` order is reproducible
    - CLI checks
  - `FIFTEEN_SLOW=1 python3 -m unittest tests.test_dfs_idfs.DfsTest.test_default_limit_all_puzzles_all_orders`
    passed on Ubuntu in 2606 s: DFS with limit 20 gives a valid solution of length ≤ 20 for every
    puzzle × 8 orders.
- **Known limitations and observations (for the report):**
  - DFS with limit 20 on the depth 1–7 set, order RDUL, Python 3.14:
    - about 386k visited states on average, 2.7M at most
    - mean solution length 17.3, against 6.1 optimal
    - up to about 9 s per puzzle
    
    IDFS needs about 500 visited states on average. DFS will dominate the run time in M7.

---

### M4 — Heuristics + Best-first + A\*

**Status:** ✅ Done (2026-11-22)

**Completion summary:**
- **What was built:**
  - `fifteen/heuristics.py`
  - `fifteen/search/best_first.py` and `fifteen/search/astar.py`, both registered in
    `fifteen/search/__init__.py`
  - `tests/test_informed.py`
- **How it works:**
  - `make_heuristic(hid, board) -> Callable[[State], int]` returns a function with the board's
    tables precomputed. `HEURISTIC_NAMES = {0: zero, 1: hamming, 2: manhattan, 3: linear_conflict}`.
    - Manhattan uses a `table[tile][cell]` distance lookup.
    - Linear conflict = Manhattan + 2 × Σ over rows and columns of `removals_to_sort(line)`, where
      `line` lists the goal columns (or goal rows) of the tiles already in their goal row (or
      column), and `removals_to_sort = len − LIS`, computed with `bisect`.
    - All heuristics ignore the blank. SMA\* in M5 reuses `make_heuristic`.
  - `best_first.solve`:
    - heap of `(h, h, counter, Node)`, which gives the contract's tie-break `(f, h, FIFO)` with
      `f = h`
    - one `seen` set (closed + open), so each state is pushed at most once
    - goal test at expansion
    - `peak_stored_states = len(seen)`
  - `astar.solve`:
    - heap of `(g+h, h, counter, Node)` and a `best_g` map
    - a successor is pushed only if it improves `best_g`, which also re-opens closed states
    - a popped entry with `g > best_g[state]` is stale and skipped (lazy deletion)
    - goal test at expansion
    - `peak_stored_states = len(best_g)`
  - Both use the fixed successor order `LRUD` and the shared `expand` (reverse-move pruning
    included).
- **Decisions and deviations:**
  - No closed set in A\*: `best_g` plus lazy deletion is equivalent and simpler.
  - `heuristic=None` falls back to `h0`. This is only possible when the API is called directly;
    the CLI always passes an id.
- **How to verify:**
  - `python3 -m unittest`: 90 pass and 1 is skipped (the slow DFS test), on Windows and WSL Ubuntu
    22.04. The suite covers:
    - hand-computed values for every heuristic: row, column and double conflicts, a fully reversed
      row, the blank ignored, `h(goal) = 0` on 5 board sizes
    - admissibility and ordering `h0 ≤ h1 ≤ h2 ≤ h3 ≤ d` on the 413 puzzles, the **full** 2×3, 3×2
      and 2×2 spaces, and 3×3 up to depth 14
    - A\* optimal on 413 × h0..h3, each verified
    - A\* optimal on 2×3, 3×2, 3×3 and 3×4 boards
    - on deeper random puzzles, A\* matches BFS lengths (3×3) and h2 and h3 agree (4×4)
    - Best-first valid on 413 × h1..h3; with h0 it finishes the depth-7 set in < 60 s
    - edge cases, an exhausted 2×2 space, CLI `-a` and `-h` with every id
- **Known limitations and observations (for the report):**
  - On the depth 1–7 set, the mean number of states A\* processes at depth 7 is:

    | h0 | h1 | h2 | h3 |
    |---|---|---|---|
    | 414.1 | 8.7 | 7.3 | 7.3 |

  - Linear conflict does not beat Manhattan at these shallow depths. Its advantage appears only on
    deeper puzzles. **Recommendation for M7:** add a deeper puzzle set for the informed
    strategies.
  - Best-first with h1 gave 411/413 optimal solutions (worst length 25); with h2 and h3 all 413
    were optimal on this set.
  - With h0, Best-first behaves like BFS (FIFO tie-break) and A\* like uniform-cost search.

---

### M5 — SMA\*

**Status:** ✅ Done (2026-11-23)

**Completion summary:**
- **What was built**
  - `fifteen/search/sma_star.py` and its registry entry, `tests/test_sma_star.py`, and README usage.
- **How it works**
  - `sma_star.solve(board, start, config, stats)` uses `SearchConfig`, `make_heuristic` and
    `SearchStats`. It selects by the lowest `f`, generates one successor at a time and tests
    for the goal on selection. New moves follow `LRUD` with reverse-move pruning.
  - At capacity it discards the highest-`f`, shallowest leaf before allocating its replacement.
    The parent remembers the move and its `f`. The minimum of retained scores, forgotten scores
    and the bound for untried moves is backed up to the ancestors. Replaying a forgotten move
    rebuilds its child with `f = max(g + h, remembered_f)`.
- **Decisions and deviations**
  - The resident frontier uses `(f, h, FIFO)`. At equal bounds resident work precedes replay.
    Forgotten moves at equal bounds are replayed deepest first. Eviction breaks remaining ties
    by dropping the newest leaf.
  - Path cycles and branches that cannot reach a goal within `memory_limit - 1` moves score infinity.
- **How to verify**
  - `python3 -m unittest` passes 96 tests on Windows and WSL Ubuntu 22.04 (Python 3.10.12 on WSL),
    with the optional slow DFS test skipped. SMA\* finds verified optimal lengths for all 413 boards
    with heuristics 0–3 at both 100000 and 50 nodes. The tests count live node objects at allocation.
  - `printf '2 2\n2 0\n1 3\n' | python3 solver.py -s 0 --memory-limit 4` gives `3` and `LDR`
    on WSL Ubuntu. Repeating with `--memory-limit 3` gives `-1` and an empty line.
- **Known limitations**
  - Tight node limits can increase running time through repeated successor generation.

---

### M6 — Viewer

**Status:** ✅ Done (2026-11-23)

**Completion summary:**
- **What was built**
  - `viewer.py`, `fifteen/replay.py`, `tests/test_replay.py`, and README usage and verification commands.
- **How it works**
  - `load_replay(puzzle_file, solution_file) -> Replay` uses the shared parsers and `Board.apply`.
    It checks the goal and stores the starting board at index zero. `-1` keeps the starting board
    with a **No solution** status. Errors are shown in the viewer.
  - The Tk canvas renders the selected state on a scrollable R×C board. Buttons, slider, numeric
    entry and keyboard shortcuts share the current step. A Tk timer drives adjustable autoplay.
- **Decisions and deviations**
  - A failed open preserves the loaded replay. The numeric entry retains its cursor keys while
    editing. Playing at the last step restarts from step 0.
- **How to verify**
  - `python3 -m unittest` passes 102 tests on Windows and WSL Ubuntu 22.04, with the optional slow
    DFS test skipped. The Linux solver also passed a stdin/stdout smoke test.
  - Follow [Viewer verification](README.md#viewer-verification) to recreate the file pairs.
    Opened on Windows with Tk 8.6: 7-step 4×4 BFS, 19-step DFS, and 5-step 2×3 through File → Open.
    Checked navigation, shortcuts, autoplay at two speeds, and error messages for illegal moves,
    length mismatch, wrong final state and malformed puzzle, as well as the `-1` display.
- **Known limitations**
  - Direct jumps use one cached board state per step. Linux GUI execution was unverified because
    `python3-tk` was absent in WSL.

---

### M7 — Batch runner + full experiment run

**Status:** ⬜ Not started

**Requirements:**
- [ ] `tools/run_experiments.py` follows section 10.3:
  - subprocess calls through stdin/stdout with `--stats`
  - per-run timeout (default 60 s)
  - verification of every solved result
  - CSV with exactly the section 10.3 columns
- [ ] The runner is **resumable** (already-finished rows are skipped on restart) and configurable
      (subset of strategies/params/puzzles via CLI options), so a crash doesn't lose results.
- [ ] The full default matrix has been run on all 413 puzzles on **one machine**, and
      `results/results.csv` is complete.
- [ ] Every solved row has `verified = true`, and timeouts/failures are counted and listed.
- [ ] The machine spec, OS, Python version and date of the run are recorded in
      `results/README.md`.

---

### M8 — Plots + report + final acceptance

**Status:** ⬜ Not started

**Requirements:**
- [ ] `tools/plot.py` produces all charts from section 10.4 out of `results/results.csv` into
      `report/figures/`, regenerable with one command.
- [ ] The report follows the section 11 structure, discusses every strategy, order and heuristic,
      and all figures come from the actual CSV.
- [ ] Final acceptance:
  - all unit tests pass on Linux
  - `./solver.py` works on Linux via stdin/stdout for every strategy
  - the viewer replays saved solutions
  - `README.md` documents how to run the solver, viewer, generator, experiments and plots

---

## 13. Change log

| Date | Change |
|------|--------|
| 2026-11-22 | Initial version agreed on. |
| 2026-11-22 | Section 12 replaced by the Milestones (M1–M8) with acceptance requirements and the completion-summary workflow. |
| 2026-11-22 | Section 13 (open points) removed: the move semantics (blank moves) and the random-order notation (`R`) are final and accepted by the instructor. Change log renumbered to 13. |
| 2026-11-22 | Section 7.1: added the single-line (1×N, N×1) solvability rule (the parity rule alone gives wrong answers there). |
| 2026-11-22 | Section 10.2: verifier exit codes refined (`-1` handling, exit code 2 for malformed input). |
| 2026-11-22 | **M1 Done**: summary written. Tests 38/38 pass on Windows and WSL Ubuntu 22.04 (Python 3.10.12). |
| 2026-11-22 | `.gitignore`: repo limited to source, tests, docs and final results; `.idea/`, `.claude/` and generated puzzles excluded. |
| 2026-11-22 | Section 8: `peak_stored_states` redefined to count distinct states once, with per-strategy definitions. |
| 2026-11-22 | **M2 Done**: summary written. Tests 56/56 pass on Windows and WSL Ubuntu 22.04. |
| 2026-11-22 | **M3 Done**: summary written. Tests 71 pass (+1 slow test passed separately) on Windows and WSL Ubuntu 22.04. |
| 2026-11-22 | **M4 Done**: summary written. Tests 90 pass (+1 slow skipped) on Windows and WSL Ubuntu 22.04. |
| 2026-11-23 | **M5 Done**. Tests 96 pass (+1 slow skipped) on Windows and WSL Ubuntu 22.04. SMA\* matches all 413 optimal distances for each heuristic at both tested limits. |
| 2026-11-23 | **M6 Done**. Viewer checked in open Windows Tk windows. Tests 102 pass (+1 slow skipped) on Windows and WSL Ubuntu 22.04. |
