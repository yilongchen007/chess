# AGENTS.md (chess)

## Project Goal

Localize LLM chess failures by comparing three input representations on the same sampled positions.

- Sample `300-500` **midgame** positions from public games.
- For each position, extract with `python-chess`:
  - move history,
  - FEN board state,
  - legal move list.
- Evaluate the same LLM in:
1. `action-level`: choose from legal moves.
2. `state-level`: given FEN, output a legal move.
3. `sequence-level`: given history only, reconstruct state and output next move.

Use cross-setting differences to isolate failures in:
- state reconstruction,
- rule inference,
- decision selection.

## Data Source (Default)

- Default PGN file for this project:
`/shares/mxq6904/yilongchen/chess/data/lichess_db_standard_rated_2015-03.pgn`
- Do not switch data source unless explicitly requested.

## Scope and Editing Rules

- Make changes only inside `/shares/mxq6904/yilongchen/chess`.
- Keep edits minimal and reproducible.
- Do not modify sibling projects or system paths.

## Run and Environment (from README)

- Prefer Poetry environment for all commands.
- Before installing any package, first confirm Poetry env is active/available:
  - `poetry env info`
  - `poetry run python -V`
- Install packages via Poetry when possible:
  - `poetry add <package>`
  - avoid global/system `pip install` unless explicitly requested.
- Baseline setup: `poetry install --no-root`
- Basic example: `poetry run python pgn_to_fen_example.py`
- Ollama example:
  - `poetry run python ollama_chess_agent_example.py`
- Local Ollama should use project-local paths:
  - `HOME=/shares/mxq6904/yilongchen/chess`
  - `OLLAMA_MODELS=/shares/mxq6904/yilongchen/chess/.ollama/models`
  - `OLLAMA_HOST=127.0.0.1:11434`

## GPU Workflow (try this first)

- If GPU is needed, first try:
  - `salloc --partition=job --gres=gpu:1 --mem=16G -t 05:00:00`
  - `srun --jobid=<ALLOCATED_JOB_ID> --pty bash`
- Replace `<ALLOCATED_JOB_ID>` with the actual job id returned by `salloc`.

## Evaluation Minimum

- Keep model/decoding config consistent across 3 settings.
- Validate move legality with `python-chess`.
- Report at least:
  - legal move rate,
  - exact-match to played move (if relevant),
  - per-setting summary metrics.
- Save outputs in machine-readable format (`csv` or `json`) with seed/config metadata.

## Results Management

- Under `results/`, create one dedicated subfolder per experiment run.
- Folder naming should encode run identity (example: `model_task_size_seed_date`).
- Do not mix outputs from different runs in the same folder.
- Save all artifacts for that run in its own folder (raw `.jsonl`, summaries, logs if any).
