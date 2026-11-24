# M7 experiment results

These results were measured after the 2026-11-24 move-convention change
(CONTRACT.md, section 4): a move letter names the direction in which a tile
slides into the blank. They replace the 2026-11-23 run, which used the earlier
blank-direction letters. The 413 puzzle files are byte-identical in both runs
(same `puzzles_sha256` in the metadata).

## Measurement environment

- One Windows laptop running Ubuntu 22.04.5 LTS under WSL 2 with Linux kernel
  `6.6.87.1-microsoft-standard-WSL2` (x86-64) and CPython 3.10.12.
- Intel Core i9-8950HK (2.90 GHz). WSL reported 12 logical CPUs and
  approximately 15 GiB of visible memory. The runner launched one solver
  subprocess at a time.
- The run started on 2026-11-24 at 15:10:27 and ended at 16:56:04 (UTC+01:00).
  Solver code and input files were staged on the native WSL filesystem, with
  the CSV written to the repository's `tmp/m7/` directory and then copied to
  `results/` together with its metadata.
- The default matrix used 413 generated 4×4 boards at optimal depths 1–7.
  DFS/IDFS used a depth limit of 20, SMA* used a 100000-node limit, and the
  per-attempt timeout was 60 s. All move orders were fixed.

## Results

| Strategy | Attempts | Solved and verified | Sum of search times (s) |
|---|---:|---:|---:|
| BFS | 3304 | 3304 | 3.495 |
| DFS | 3304 | 3304 | 4674.233 |
| IDFS | 3304 | 3304 | 6.335 |
| Best-first | 1652 | 1652 | 1.729 |
| A* | 1652 | 1652 | 1.686 |
| SMA* | 1652 | 1652 | 8.075 |
| **Total** | **14868** | **14868** | **4695.553** |

The counts for `not_found`, `unsolvable`, `timeout`, `error` and `invalid`
are all zero. The verifier accepted every solution. An independent CSV check
confirmed the exact 14-column schema and exact set of 14868 keys
`(puzzle, strategy, param)`, with zero missing or duplicate attempts.

The logged wall interval was **1 h 45 min 37 s**. The sum of `time_ms` records
only the timed searches. The difference was approximately **27 min 21 s** and
includes process startup, parsing, solvability checks, I/O, verifier work and
durable writes. The log does not give a timing breakdown for these operations
or timestamps for individual attempts.

| Slowest puzzle | Strategy | Order | Search time (s) |
|---|---|---|---:|
| `4x4_07_00077.txt` | DFS | `RDUL` | 12.079 |
| `4x4_07_00159.txt` | DFS | `DRLU` | 11.727 |
| `4x4_07_00159.txt` | DFS | `RDLU` | 11.538 |
| `4x4_07_00077.txt` | DFS | `DRUL` | 11.472 |

### Comparison with the earlier run

- **Counts:** for BFS, DFS and IDFS every count is the same as in the
  2026-11-23 run once the order labels are mirrored (`L↔R`, `U↔D`). For
  example, today's `RDUL` reproduces the earlier `LUDR`. The eight tested
  orders map onto each other, so the order table keeps the same values under
  new labels.
- **Informed searches:** Best-first, A* and SMA* expand successors in the
  fixed letter order `LRUD`, which now names different physical moves. This
  changes tie-breaking, so their node counts differ slightly from the earlier
  run.
- **Search times:** these are about 3.4× longer than the earlier run on an
  Intel Core i5-13600KF. That is consistent with the slower 2018 laptop CPU.
  Timings are comparable within one run only.

The CSV SHA-256 is
`d65e9062403fef81b38f253ae7c19c5389c267317abb024f461b03061b3f5458`.

## Read or reproduce the results

Keep [results.csv](results.csv) and [its metadata](results.csv.meta.json)
together for resume. Use a separate output when repeating the measurement.
Run from the repository root on Linux to reproduce the same staging layout.

```bash
python3 tools/generate.py
repo_root=$PWD
native_workdir=$(mktemp -d)
cp -a solver.py fifteen tools data "$native_workdir/"
(
  cd "$native_workdir"
  python3 tools/run_experiments.py --output "$repo_root/tmp/m7/repeat.csv"
)
```
