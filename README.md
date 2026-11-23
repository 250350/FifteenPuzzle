# Fifteen Puzzle — search strategies

Solver and viewer for the R x C sliding puzzle, with an empirical comparison of
BFS, DFS, IDFS, Best-first, A* and SMA*. The binding specification is
[CONTRACT.md](CONTRACT.md).

Requirements: Python 3.10+ (standard library only for the solver and viewer).

## Solver

```bash
python3 solver.py -b RDUL < puzzle.txt                # BFS, order R,D,U,L
python3 solver.py -d LUDR --max-depth 25 < puzzle.txt  # DFS with depth limit 25 (default 20)
python3 solver.py -i R --seed 7 < puzzle.txt           # IDFS, random order, reproducible
python3 solver.py -h 2 < puzzle.txt                    # greedy Best-first with Manhattan
python3 solver.py -a 2 --stats out.json < puzzle.txt   # A* with Manhattan, stats to JSON
python3 solver.py -s 2 --memory-limit 50 < puzzle.txt # SMA* with Manhattan and 50 nodes
python3 solver.py --help
```

Strategy flags: `-b/--bfs`, `-d/--dfs`, `-i/--idfs` take an order (a permutation
of `LRUD`, or `R` for random); `-h/--bf`, `-a/--astar`, `-s/--sma` take a
heuristic id (0 zero, 1 Hamming, 2 Manhattan, 3 linear conflict). Move letters
give the direction the blank moves.

On Linux, the executable entry point also works directly as
`./solver.py -b RDUL < puzzle.txt`.

### SMA* memory and restoration

SMA* keeps a search tree with at most `--memory-limit` nodes (default 100000),
including the root. It takes the lowest estimate `f` first. For resident
nodes ready to generate, ties use lower `h`, then FIFO. Each step generates
one successor, in `LRUD` order for new moves. A goal is accepted when selected
for expansion. At depth `limit - 1` a non-goal scores infinity, and a bound
above that depth also rules out the branch.

When memory is full, SMA* drops the leaf with the highest `f`, then the
shallowest, then the newest. It can discard the new successor itself if it
ranks worst. The leaf's parent keeps its move and backed-up `f`. The parent's
score is the minimum of the retained children's scores, the forgotten scores
and the lower bound for any untried moves. Changes propagate toward the root.

The best forgotten move can be replayed from its parent's board when its
bound is lowest. The rebuilt child starts with the larger of `g + h` and
the remembered score. At equal scores SMA* finishes resident work first,
then restores the deepest forgotten alternative first to prevent immediate
re-eviction. A solution of length `d` needs room for at least `d + 1` nodes.

## Test-puzzle generator

```bash
python3 tools/generate.py        # all 413 4x4 puzzles at optimal depths 1..7 -> data/puzzles/
python3 tools/generate.py --rows 3 --cols 3 --max-depth 10
```

Files are named `{R}x{C}_{depth:02d}_{index:05d}.txt`. They are not committed:
run the generator after cloning.

## Verifier

```bash
python3 tools/verify.py puzzle.txt solution.txt
```

## Viewer

```bash
python3 solver.py -b RDUL < puzzle.txt > solution.txt
python3 viewer.py puzzle.txt solution.txt
```

Run `python3 viewer.py` without arguments to select the puzzle and then the
saved solution through **File → Open** (`Ctrl+O`). On Ubuntu the viewer needs
`python3-tk` and a graphical session.

The initial board is step 0. Use **First**, **Prev**, **Next** and **Last**,
drag the timeline, or enter a step and press **Go** or `Enter`. `←` and `→`
move by one step, `Home` and `End` jump to the ends, and `Space` controls
autoplay. The step entry keeps its cursor shortcuts while editing. Use **Speed**
to change the playback rate. **Play** at the last step restarts from step 0.

The viewer validates the entire solution before loading the replay. Errors
appear below the controls and a failed open preserves the previously loaded
board. A solver result of `-1` displays **No solution** and the initial board.

### Viewer verification

Run these commands from the repository root in Bash to prepare the test files.

```bash
mkdir -p tmp/m6
printf '4 4\n1 2 3 4\n5 6 7 8\n10 11 12 0\n9 13 14 15\n' > tmp/m6/square.txt
printf '2 3\n2 3 0\n1 4 5\n' > tmp/m6/rect.txt
python3 solver.py -b RDUL < tmp/m6/square.txt > tmp/m6/bfs.txt
python3 solver.py -d RDUL --max-depth 20 < tmp/m6/square.txt > tmp/m6/dfs.txt
python3 solver.py -b RDUL < tmp/m6/rect.txt > tmp/m6/rect-sol.txt
printf '1\nR\n' > tmp/m6/illegal.txt
printf '2\nL\n' > tmp/m6/bad-length.txt
printf '1\nL\n' > tmp/m6/wrong-goal.txt
printf -- '-1\n\n' > tmp/m6/no-solution.txt
printf '2 3\n2 3 0\n1 4 4\n' > tmp/m6/invalid-board.txt
```

```bash
python3 viewer.py tmp/m6/square.txt tmp/m6/bfs.txt          # 7 steps
python3 viewer.py tmp/m6/square.txt tmp/m6/dfs.txt          # 19 steps
python3 viewer.py                                         # File → Open: rect.txt, rect-sol.txt
python3 viewer.py tmp/m6/square.txt tmp/m6/illegal.txt
python3 viewer.py tmp/m6/square.txt tmp/m6/bad-length.txt
python3 viewer.py tmp/m6/square.txt tmp/m6/wrong-goal.txt
python3 viewer.py tmp/m6/square.txt tmp/m6/no-solution.txt
python3 viewer.py tmp/m6/invalid-board.txt tmp/m6/rect-sol.txt
```

## Tests

```bash
python3 -m unittest                      # fast suite (~15 s)
FIFTEEN_SLOW=1 python3 -m unittest       # + full DFS run with the default limit (~1 h)
```

## Experiments

```bash
python3 tools/generate.py
python3 tools/run_experiments.py
python3 tools/run_experiments.py --puzzle '4x4_01_*.txt' --param RDUL --param 2 \
  --output tmp/m7/smoke.csv
python3 tools/run_experiments.py --puzzle '4x4_01_00001.txt' --strategy bfs --param RDUL \
  --timeout 0.001 --output tmp/m7/timeout-check.csv
python3 tools/run_experiments.py --strategy sma --param 3 --timeout 30 \
  --memory-limit 50 --output tmp/m7/sma-small.csv
```

The default run covers 413 boards and 36 strategy/parameter pairs. The runner
sends each puzzle to a fresh solver process, reads its stdout and statistics,
and checks returned solutions with the verifier. Each finished row is flushed
to disk. Rerun the same command after the previous process exits to resume.
The runner keeps complete rows and discards an unterminated final write.

`--puzzle`, `--strategy` and `--param` are repeatable. Puzzle patterns match file
names in `--puzzles-dir`. Orders apply to BFS/DFS/IDFS and heuristic IDs apply
to Best-first/A*/SMA*. For order `R`, set `--seed` and use a separate output for
each seed.

Keep the `.csv.meta.json` file beside its CSV. The runner checks the selected
matrix, puzzle contents, code, environment, timeout and solver limits before
appending. A different configuration requires a different `--output`.

`timeout` records an expired deadline, `error` an execution or statistics
failure, and `invalid` a rejected solution. Those rows have empty search
metrics. Only accepted solutions have `verified=true`.

The [recorded run](results/README.md) documents the full matrix, environment,
timings and validation of `results/results.csv`.

## Plots and technical report

Install the plot dependency once with
`python3 -m pip install -r requirements-tools.txt`. Regenerate all figures
from the repository root with one command.

```bash
python3 tools/plot.py
```

The script reads `results/results.csv` and writes the strategy and parameter
comparisons for all six metrics as PNG and PDF in `report/figures/`.
All means are arithmetic means of verified, solved attempts at each optimal
depth. Each strategy point pools all of its configurations at that depth.
Each order or heuristic point uses one configuration. Length and depth are in
moves, search time is in milliseconds per attempt, and storage is in states
or SMA* nodes. Node counts and search time use log axes. Zero counts enter
the means unchanged. A zero mean on a log axis is drawn as a hollow triangle
below the smallest positive mean.

Use `--csv PATH` and `--out DIRECTORY` for a separate input or output.
The [technical report](report/report.md) includes the full figure index.
