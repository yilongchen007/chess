# Chess Experiment Record

This file stores experiment results only.
All rules/workflows are maintained in `AGENTS.md`.

## 2026-02-26 - End-to-End Sample Re-run After Schema/Prompt Fix (llama3.2:1b)

- Setup: `data/sample_game.pgn`, schema-constrained JSON output.
- Result: `Correctness=True`.
- Checks:
  - valid JSON: pass
  - key names: pass (`state_fen`, `legal_moves_san`)
  - FEN match reference: pass
  - legal move completeness/legality: pass (`32/32`, no illegal, no missing)

## 2026-02-27 - Fixed 10 Positions, Complete Legal-Moves (llama3.2:1b)

- Input set: `data/fixed_positions_10_seed20260226.jsonl`
- Summary (`fen -> complete legal moves`):
  - `json_valid_rate=0.9`
  - `schema_valid_rate=0.9`
  - `exact_match_rate=0.0`
  - `avg_illegal_per_position=10.2`
  - `avg_missing_per_position=31.9`
  - `avg_latency_sec=9.44`
  - `error_histogram={contains_illegal_moves: 9, incomplete_move_list: 9, request_error: 1}`

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
