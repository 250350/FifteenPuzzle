# Fifteen Puzzle — search strategies

Solver and viewer for the R x C sliding puzzle, with an empirical comparison of
BFS, DFS, IDFS, Best-first, A* and SMA*. The binding specification is
[CONTRACT.md](CONTRACT.md).

Requirements: Python 3.10+ (standard library only for the solver and viewer).

## Solver

```bash
python3 solver.py -b RDUL < puzzle.txt              # BFS, order R,D,U,L
python3 solver.py -a 2 --stats out.json < puzzle.txt  # A* with Manhattan, stats to JSON
python3 solver.py --help
```

Strategy flags: `-b/--bfs`, `-d/--dfs`, `-i/--idfs` take an order (a permutation
of `LRUD`, or `R` for random); `-h/--bf`, `-a/--astar`, `-s/--sma` take a
heuristic id (0 zero, 1 Hamming, 2 Manhattan, 3 linear conflict). Move letters
give the direction the blank moves.

## Verifier

```bash
python3 tools/verify.py puzzle.txt solution.txt
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

_Viewer, generator, experiments and plots: documented as their milestones land._
