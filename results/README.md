# M7 experiment results

## Measurement environment

- One Windows host running Ubuntu 22.04.5 LTS under WSL 2 with Linux kernel
  `6.6.87.2-microsoft-standard-WSL2` (x86-64) and CPython 3.10.12.
- Intel Core i5-13600KF. WSL reported 20 logical CPUs and approximately 15 GiB
  of visible memory. The runner launched one solver subprocess at a time.
- The run started on 2026-11-23 at 16:23:21 and ended at 16:55:28 (UTC+01:00).
  Solver code and input files were staged on the native WSL filesystem, with
  the CSV written to the repository's `results/` directory.
- The default matrix used 413 generated 4×4 boards at optimal depths 1–7.
  DFS/IDFS used a depth limit of 20, SMA* used a 100000-node limit, and the
  per-attempt timeout was 60 s. All move orders were fixed.

## Results

| Strategy | Attempts | Solved and verified | Sum of search times (s) |
|---|---:|---:|---:|
| BFS | 3304 | 3304 | 0.833 |
| DFS | 3304 | 3304 | 1366.915 |
| IDFS | 3304 | 3304 | 1.571 |
| Best-first | 1652 | 1652 | 0.393 |
| A* | 1652 | 1652 | 0.400 |
| SMA* | 1652 | 1652 | 1.850 |
| **Total** | **14868** | **14868** | **1371.961** |

The counts for `not_found`, `unsolvable`, `timeout`, `error` and `invalid`
are all zero. The verifier accepted every solution. An independent CSV check
confirmed the exact 14-column schema and exact set of 14868 keys
`(puzzle, strategy, param)`, with zero missing or duplicate attempts.

The logged wall interval was **32 min 7 s**. The sum of `time_ms` records only
the timed searches. The difference was approximately **9 min 15 s** and
includes process startup, parsing, solvability checks, I/O, verifier work and
durable writes. The log does not give a timing breakdown for these operations
or timestamps for individual attempts.

| Slowest puzzle | Strategy | Order | Search time (s) |
|---|---|---|---:|
| `4x4_07_00077.txt` | DFS | `ULDR` | 3.911 |
| `4x4_07_00077.txt` | DFS | `LUDR` | 3.905 |
| `4x4_07_00159.txt` | DFS | `ULRD` | 3.796 |
| `4x4_07_00159.txt` | DFS | `LURD` | 3.617 |

The benchmark continued after the monitoring session was interrupted. The log
records subsequent progress through 14868 and a normal end. No attempts
needed to be resumed in the full run. The separate preflight resumed from
five complete rows after termination, repaired an unterminated final write
and ended with all 72 expected keys. The preflight also exercised all six
strategies and a forced timeout.

The CSV SHA-256 is
`90e88f8710414ffa92670e83ec1c9210e07c819eb86c9033386d7323da2691c3`.

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
