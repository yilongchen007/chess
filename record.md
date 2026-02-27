# Chess Experiment Record

This file stores experiment results only.
All rules/workflows are maintained in `AGENTS.md`.

## 2026-02-27 - Three-Step Separated Evaluation (llama3.2:1b, 10 positions)

- Files:
  - `results/llama3.2_1b_three_step_sep_10_seed20260226.history_to_fen.summary.json`
  - `results/llama3.2_1b_three_step_sep_10_seed20260226.fen_to_legal_moves.summary.json`
  - `results/llama3.2_1b_three_step_sep_10_seed20260226.history_to_legal_moves.summary.json`
- Step 1 (`history -> FEN`):
  - `json_valid_rate=1.0`, `schema_valid_rate=1.0`
  - `fen_valid_rate=0.3`, `fen_exact_match_rate=0.0`
- Step 2 (`FEN -> legal moves`):
  - `json_valid_rate=1.0`, `schema_valid_rate=1.0`
  - `exact_match_rate=0.0`
  - `avg_illegal_per_position=12.3`, `avg_missing_per_position=34.4`
- Step 3 (`history -> legal moves`):
  - `json_valid_rate=1.0`, `schema_valid_rate=1.0`
  - `exact_match_rate=0.0`
  - `avg_illegal_per_position=17.5`, `avg_missing_per_position=36.1`
- Interpretation:
  - Step 3 is worse than Step 2.
  - State reconstruction from history introduces extra failure on top of move-rule generation.

## 2026-02-27 - Summary (Three-Step, 10 Positions)

| Task | Num Positions | JSON Valid Rate | Schema Valid Rate | Core Accuracy | Avg Illegal / Position | Avg Missing / Position | Error Signals | Avg Latency (s) |
|---|---:|---:|---:|---:|---|---:|
| `history -> FEN` | 10 | 1.0 | 1.0 | `fen_exact_match_rate = 0.0` | N/A | N/A | `invalid_fen_format: 7`, `fen_mismatch: 10` | 4.47 |
| `FEN -> legal_moves` | 10 | 1.0 | 1.0 | `exact_match_rate = 0.0` | 12.3 | 34.4 | `contains_illegal_moves: 10`, `incomplete_move_list: 10` | 5.17 |
| `history -> legal_moves` | 10 | 1.0 | 1.0 | `exact_match_rate = 0.0` | 17.5 | 36.1 | `contains_illegal_moves: 10`, `incomplete_move_list: 10` | 8.50 |

Conclusions:
- Output format compliance is strong, but task correctness is zero across all three settings.
- `history -> FEN` is the main bottleneck, indicating weak board-state reconstruction.
- Even with correct FEN input, complete legal-move enumeration still fails, so rule-complete generation is also beyond current model capability.
- `history -> legal_moves` is slower and worse than `FEN -> legal_moves`, consistent with compounded errors.
