import argparse
import json
import time
import urllib.request
from pathlib import Path


def call_ollama(ollama_url: str, payload: dict, timeout: int = 60) -> str:
    req = urllib.request.Request(
        ollama_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["message"]["content"]


def payload_history_to_fen(model: str, uci_history: list[str]) -> dict:
    schema = {
        "type": "object",
        "properties": {"state_fen": {"type": "string"}},
        "required": ["state_fen"],
        "additionalProperties": False,
    }
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a chess state reconstruction assistant. "
                    "Given a move history in UCI, return the resulting board state as FEN."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Move history (UCI list): "
                    f"{json.dumps(uci_history)}\n"
                    "Return JSON only."
                ),
            },
        ],
        "format": schema,
        "options": {"temperature": 0},
        "stream": False,
    }


def payload_fen_to_legal(model: str, fen: str) -> dict:
    schema = {
        "type": "object",
        "properties": {"legal_moves_san": {"type": "array", "items": {"type": "string"}}},
        "required": ["legal_moves_san"],
        "additionalProperties": False,
    }
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a chess rules assistant. "
                    "Given a FEN, output the COMPLETE legal SAN move list."
                ),
            },
            {"role": "user", "content": f'FEN: "{fen}"\nReturn JSON only.'},
        ],
        "format": schema,
        "options": {"temperature": 0},
        "stream": False,
    }


def payload_history_to_legal(model: str, uci_history: list[str]) -> dict:
    schema = {
        "type": "object",
        "properties": {"legal_moves_san": {"type": "array", "items": {"type": "string"}}},
        "required": ["legal_moves_san"],
        "additionalProperties": False,
    }
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a chess assistant. "
                    "Given move history in UCI, reconstruct the current position and "
                    "output the COMPLETE legal SAN move list."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Move history (UCI list): "
                    f"{json.dumps(uci_history)}\n"
                    "Return JSON only."
                ),
            },
        ],
        "format": schema,
        "options": {"temperature": 0},
        "stream": False,
    }


def eval_history_to_fen(raw: str, ref_fen: str) -> dict:
    out = {
        "json_valid": False,
        "schema_valid": False,
        "fen_valid": False,
        "fen_exact_match": False,
        "error_types": [],
    }
    try:
        obj = json.loads(raw)
        out["json_valid"] = True
    except Exception:
        out["error_types"].append("json_format_error")
        return out
    if not isinstance(obj, dict) or set(obj.keys()) != {"state_fen"}:
        out["error_types"].append("schema_or_keys_error")
        return out
    pred_fen = obj.get("state_fen")
    if not isinstance(pred_fen, str):
        out["error_types"].append("invalid_fen_type")
        return out
    out["schema_valid"] = True
    parts = pred_fen.split(" ")
    if len(parts) == 6 and parts[0].count("/") == 7:
        out["fen_valid"] = True
    else:
        out["error_types"].append("invalid_fen_format")
    out["fen_exact_match"] = pred_fen == ref_fen
    if not out["fen_exact_match"]:
        out["error_types"].append("fen_mismatch")
    return out


def eval_fen_to_legal(raw: str, ref_moves: list[str]) -> dict:
    out = {
        "json_valid": False,
        "schema_valid": False,
        "pred_count": 0,
        "illegal_count": 0,
        "missing_count": 0,
        "exact_match": False,
        "error_types": [],
    }
    try:
        obj = json.loads(raw)
        out["json_valid"] = True
    except Exception:
        out["error_types"].append("json_format_error")
        return out
    if not isinstance(obj, dict) or set(obj.keys()) != {"legal_moves_san"}:
        out["error_types"].append("schema_or_keys_error")
        return out
    pred = obj.get("legal_moves_san")
    if not isinstance(pred, list) or not all(isinstance(x, str) for x in pred):
        out["error_types"].append("invalid_legal_moves_type")
        return out
    out["schema_valid"] = True
    ref_set = set(ref_moves)
    pred_set = set(pred)
    illegal = pred_set - ref_set
    missing = ref_set - pred_set
    out["pred_count"] = len(pred_set)
    out["illegal_count"] = len(illegal)
    out["missing_count"] = len(missing)
    out["exact_match"] = len(illegal) == 0 and len(missing) == 0
    if illegal:
        out["error_types"].append("contains_illegal_moves")
    if missing:
        out["error_types"].append("incomplete_move_list")
    return out


def run(input_jsonl: Path, model: str, ollama_url: str, out_dir: Path, tag: str) -> None:
    rows = [json.loads(x) for x in input_jsonl.read_text(encoding="utf-8").splitlines() if x.strip()]
    run_dir = out_dir / tag
    run_dir.mkdir(parents=True, exist_ok=True)

    h2f_jsonl = run_dir / "history_to_fen.jsonl"
    h2f_summary = run_dir / "history_to_fen.summary.json"
    f2m_jsonl = run_dir / "fen_to_legal_moves.jsonl"
    f2m_summary = run_dir / "fen_to_legal_moves.summary.json"
    h2m_jsonl = run_dir / "history_to_legal_moves.jsonl"
    h2m_summary = run_dir / "history_to_legal_moves.summary.json"

    n = len(rows)

    h_json_valid = h_schema_valid = h_fen_valid = h_fen_match = 0
    h_latency_sum = 0.0
    h_err: dict[str, int] = {}

    m_json_valid = m_schema_valid = m_exact_match = 0
    m_illegal = 0
    m_missing = 0
    m_latency_sum = 0.0
    m_err: dict[str, int] = {}
    hm_json_valid = hm_schema_valid = hm_exact_match = 0
    hm_illegal = 0
    hm_missing = 0
    hm_latency_sum = 0.0
    hm_err: dict[str, int] = {}

    with (
        h2f_jsonl.open("w", encoding="utf-8") as fh,
        f2m_jsonl.open("w", encoding="utf-8") as fm,
        h2m_jsonl.open("w", encoding="utf-8") as fhm,
    ):
        for i, row in enumerate(rows, start=1):
            # Step 1: history -> fen
            h_raw = ""
            h_request_error = None
            t0 = time.time()
            try:
                h_raw = call_ollama(ollama_url, payload_history_to_fen(model, row["uci_history"]), timeout=60)
                h_eval = eval_history_to_fen(h_raw, row["fen"])
            except Exception as exc:
                h_request_error = str(exc)
                h_eval = {
                    "json_valid": False,
                    "schema_valid": False,
                    "fen_valid": False,
                    "fen_exact_match": False,
                    "error_types": ["request_error"],
                }
            h_latency = round(time.time() - t0, 4)
            h_latency_sum += h_latency
            fh.write(
                json.dumps(
                    {
                        "idx": i,
                        "game_index": row["game_index"],
                        "ply": row["ply"],
                        "uci_history": row["uci_history"],
                        "reference_fen": row["fen"],
                        "raw_output": h_raw,
                        "eval": h_eval,
                        "request_error": h_request_error,
                        "latency_sec": h_latency,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            fh.flush()

            h_json_valid += int(h_eval["json_valid"])
            h_schema_valid += int(h_eval["schema_valid"])
            h_fen_valid += int(h_eval["fen_valid"])
            h_fen_match += int(h_eval["fen_exact_match"])
            for e in h_eval["error_types"]:
                h_err[e] = h_err.get(e, 0) + 1

            # Step 2: fen -> legal moves (isolated: use reference fen)
            m_raw = ""
            m_request_error = None
            t1 = time.time()
            try:
                m_raw = call_ollama(ollama_url, payload_fen_to_legal(model, row["fen"]), timeout=60)
                m_eval = eval_fen_to_legal(m_raw, row["legal_moves_san"])
            except Exception as exc:
                m_request_error = str(exc)
                m_eval = {
                    "json_valid": False,
                    "schema_valid": False,
                    "pred_count": 0,
                    "illegal_count": 0,
                    "missing_count": 0,
                    "exact_match": False,
                    "error_types": ["request_error"],
                }
            m_latency = round(time.time() - t1, 4)
            m_latency_sum += m_latency
            fm.write(
                json.dumps(
                    {
                        "idx": i,
                        "game_index": row["game_index"],
                        "ply": row["ply"],
                        "fen": row["fen"],
                        "reference_legal_moves_san": row["legal_moves_san"],
                        "raw_output": m_raw,
                        "eval": m_eval,
                        "request_error": m_request_error,
                        "latency_sec": m_latency,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            fm.flush()

            m_json_valid += int(m_eval["json_valid"])
            m_schema_valid += int(m_eval["schema_valid"])
            m_exact_match += int(m_eval["exact_match"])
            m_illegal += m_eval["illegal_count"]
            m_missing += m_eval["missing_count"]
            for e in m_eval["error_types"]:
                m_err[e] = m_err.get(e, 0) + 1

            # Step 3: history -> legal moves (direct)
            hm_raw = ""
            hm_request_error = None
            t2 = time.time()
            try:
                hm_raw = call_ollama(
                    ollama_url,
                    payload_history_to_legal(model, row["uci_history"]),
                    timeout=60,
                )
                hm_eval = eval_fen_to_legal(hm_raw, row["legal_moves_san"])
            except Exception as exc:
                hm_request_error = str(exc)
                hm_eval = {
                    "json_valid": False,
                    "schema_valid": False,
                    "pred_count": 0,
                    "illegal_count": 0,
                    "missing_count": 0,
                    "exact_match": False,
                    "error_types": ["request_error"],
                }
            hm_latency = round(time.time() - t2, 4)
            hm_latency_sum += hm_latency
            fhm.write(
                json.dumps(
                    {
                        "idx": i,
                        "game_index": row["game_index"],
                        "ply": row["ply"],
                        "uci_history": row["uci_history"],
                        "reference_fen": row["fen"],
                        "reference_legal_moves_san": row["legal_moves_san"],
                        "raw_output": hm_raw,
                        "eval": hm_eval,
                        "request_error": hm_request_error,
                        "latency_sec": hm_latency,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            fhm.flush()

            hm_json_valid += int(hm_eval["json_valid"])
            hm_schema_valid += int(hm_eval["schema_valid"])
            hm_exact_match += int(hm_eval["exact_match"])
            hm_illegal += hm_eval["illegal_count"]
            hm_missing += hm_eval["missing_count"]
            for e in hm_eval["error_types"]:
                hm_err[e] = hm_err.get(e, 0) + 1

            print(f"progress {i}/{n}", flush=True)

    h_summary_obj = {
        "task": "history_to_fen",
        "input_jsonl": str(input_jsonl),
        "model": model,
        "ollama_url": ollama_url,
        "num_positions": n,
        "json_valid_rate": h_json_valid / n if n else 0.0,
        "schema_valid_rate": h_schema_valid / n if n else 0.0,
        "fen_valid_rate": h_fen_valid / n if n else 0.0,
        "fen_exact_match_rate": h_fen_match / n if n else 0.0,
        "avg_latency_sec": h_latency_sum / n if n else 0.0,
        "error_histogram": h_err,
        "result_jsonl": str(h2f_jsonl),
    }
    m_summary_obj = {
        "task": "fen_to_legal_moves",
        "input_jsonl": str(input_jsonl),
        "model": model,
        "ollama_url": ollama_url,
        "num_positions": n,
        "json_valid_rate": m_json_valid / n if n else 0.0,
        "schema_valid_rate": m_schema_valid / n if n else 0.0,
        "exact_match_rate": m_exact_match / n if n else 0.0,
        "avg_illegal_per_position": m_illegal / n if n else 0.0,
        "avg_missing_per_position": m_missing / n if n else 0.0,
        "avg_latency_sec": m_latency_sum / n if n else 0.0,
        "error_histogram": m_err,
        "result_jsonl": str(f2m_jsonl),
    }
    hm_summary_obj = {
        "task": "history_to_legal_moves",
        "input_jsonl": str(input_jsonl),
        "model": model,
        "ollama_url": ollama_url,
        "num_positions": n,
        "json_valid_rate": hm_json_valid / n if n else 0.0,
        "schema_valid_rate": hm_schema_valid / n if n else 0.0,
        "exact_match_rate": hm_exact_match / n if n else 0.0,
        "avg_illegal_per_position": hm_illegal / n if n else 0.0,
        "avg_missing_per_position": hm_missing / n if n else 0.0,
        "avg_latency_sec": hm_latency_sum / n if n else 0.0,
        "error_histogram": hm_err,
        "result_jsonl": str(h2m_jsonl),
    }

    h2f_summary.write_text(json.dumps(h_summary_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    f2m_summary.write_text(json.dumps(m_summary_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    h2m_summary.write_text(json.dumps(hm_summary_obj, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(h_summary_obj, ensure_ascii=False), flush=True)
    print(json.dumps(m_summary_obj, ensure_ascii=False), flush=True)
    print(json.dumps(hm_summary_obj, ensure_ascii=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=Path("data/fixed_positions_10_seed20260226.jsonl"),
    )
    parser.add_argument("--model", default="llama3.2:1b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--out-dir", type=Path, default=Path("results"))
    parser.add_argument("--tag", default="llama3.2_1b_two_step_sep_10_seed20260226")
    args = parser.parse_args()

    run(
        input_jsonl=args.input_jsonl,
        model=args.model,
        ollama_url=args.ollama_url,
        out_dir=args.out_dir,
        tag=args.tag,
    )


if __name__ == "__main__":
    main()
