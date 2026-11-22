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
python3 solver.py -a 2 --stats out.json < puzzle.txt   # A* with Manhattan, stats to JSON
python3 solver.py --help
```

Strategy flags: `-b/--bfs`, `-d/--dfs`, `-i/--idfs` take an order (a permutation
of `LRUD`, or `R` for random); `-h/--bf`, `-a/--astar`, `-s/--sma` take a
heuristic id (0 zero, 1 Hamming, 2 Manhattan, 3 linear conflict). Move letters
give the direction the blank moves.

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

## Tests

```bash
python3 -m unittest                      # fast suite (~15 s)
FIFTEEN_SLOW=1 python3 -m unittest       # + full DFS run with the default limit (~1 h)
```

_Viewer, experiments and plots: documented as their milestones land._
