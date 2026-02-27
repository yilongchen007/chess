import argparse
import json
import random
from pathlib import Path

import chess.pgn


def build_candidate(
    game_index: int,
    ply: int,
    board: chess.Board,
    uci_history: list[str],
    headers: dict[str, str],
) -> dict:
    legal_moves_san = sorted(board.san(m) for m in board.legal_moves)
    return {
        "game_index": game_index,
        "ply": ply,
        "fen": board.fen(),
        "turn": "white" if board.turn else "black",
        "uci_history": list(uci_history),
        "headers": headers,
        "legal_moves_san": legal_moves_san,
    }


def sample_positions(
    pgn_path: Path,
    output_jsonl: Path,
    output_meta: Path,
    sample_size: int,
    seed: int,
    min_ply: int,
    max_ply: int,
    min_legal_moves: int,
) -> None:
    rng = random.Random(seed)
    sampled: list[dict] = []
    seen_candidates = 0
    game_count = 0
    step_min = 1
    step_max = 5
    keep_every_n = rng.randint(step_min, step_max)
    offset = rng.randint(0, keep_every_n - 1)

    with pgn_path.open("r", encoding="utf-8", errors="ignore") as f:
        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            game_count += 1
            board = game.board()
            headers = {
                "Event": game.headers.get("Event", ""),
                "Site": game.headers.get("Site", ""),
                "Date": game.headers.get("Date", ""),
                "White": game.headers.get("White", ""),
                "Black": game.headers.get("Black", ""),
                "Result": game.headers.get("Result", ""),
            }

            uci_history: list[str] = []
            for ply, move in enumerate(game.mainline_moves(), start=1):
                board.push(move)
                uci_history.append(move.uci())
                if ply < min_ply or ply > max_ply:
                    continue
                if board.is_game_over():
                    continue
                if board.legal_moves.count() < min_legal_moves:
                    continue
                if (seen_candidates + offset) % keep_every_n != 0:
                    seen_candidates += 1
                    continue

                candidate = build_candidate(
                    game_index=game_count,
                    ply=ply,
                    board=board,
                    uci_history=uci_history,
                    headers=headers,
                )
                seen_candidates += 1
                sampled.append(candidate)
                if len(sampled) >= sample_size:
                    break

            if len(sampled) >= sample_size:
                break

    sampled.sort(key=lambda x: (x["game_index"], x["ply"]))

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with output_jsonl.open("w", encoding="utf-8") as f:
        for row in sampled:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    meta = {
        "pgn_path": str(pgn_path),
        "sample_size": sample_size,
        "seed": seed,
        "min_ply": min_ply,
        "max_ply": max_ply,
        "min_legal_moves": min_legal_moves,
        "selection_strategy": "deterministic_stride_until_k",
        "keep_every_n": keep_every_n,
        "offset": offset,
        "games_scanned": game_count,
        "candidates_seen": seen_candidates,
        "rows_written": len(sampled),
    }
    with output_meta.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(json.dumps(meta, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pgn",
        type=Path,
        default=Path("data/lichess_db_standard_rated_2015-03.pgn"),
    )
    parser.add_argument(
        "--out-jsonl",
        type=Path,
        default=Path("data/fixed_positions_10_seed20260226.jsonl"),
    )
    parser.add_argument(
        "--out-meta",
        type=Path,
        default=Path("data/fixed_positions_10_seed20260226.meta.json"),
    )
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260226)
    parser.add_argument("--min-ply", type=int, default=20)
    parser.add_argument("--max-ply", type=int, default=80)
    parser.add_argument("--min-legal-moves", type=int, default=10)
    args = parser.parse_args()

    sample_positions(
        pgn_path=args.pgn,
        output_jsonl=args.out_jsonl,
        output_meta=args.out_meta,
        sample_size=args.sample_size,
        seed=args.seed,
        min_ply=args.min_ply,
        max_ply=args.max_ply,
        min_legal_moves=args.min_legal_moves,
    )


if __name__ == "__main__":
    main()
