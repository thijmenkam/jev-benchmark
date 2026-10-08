"""Batching probe: same state+questions as N 1-question calls vs one N-question call.
Uses 20 support/text states (3 questions each). SUTs passed via --models.

Usage: python batching.py --models jev,openai --out results/batching-jo.jsonl
"""
import argparse, datetime, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from benchmark import call_with_retry, cost_usd, decide_dispatch  # noqa: E402
from common import load_env  # noqa: E402

load_env()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="jev,openai")
    ap.add_argument("--out", default="results/batching.jsonl")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--delay", type=float, default=0.5)
    args = ap.parse_args()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    rows = [json.loads(l) for l in open("data/gold.v1.jsonl") if l.strip()]
    cand = [r for r in rows if r["domain"] == "support" and r["format_variant"] == "text"][: args.n]
    run_id = "batch-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as out:
        for row in cand:
            qids = list(row["questions"])
            for m in models:
                # condition single: one call per question
                for qid in qids:
                    res, attempts, status, err = call_with_retry(m, row["state"], {qid: row["questions"][qid]})
                    rec = {"run_id": run_id, "condition": "single", "n_questions": 1, "qid": qid,
                           "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                           "state_id": row["id"], "domain": row["domain"], "tier": row["tier"],
                           "provider": m, "model": (res["model"] if res else m),
                           "latency_ms": (res["latency_ms"] if res else None),
                           "usage": (res["usage"] if res else None),
                           "cost_usd": (cost_usd(m, res["usage"]) if res else None),
                           "answers": (res["answers"] if res else None),
                           "gold": row["gold"], "http_status": status, "attempts": attempts, "error": err}
                    out.write(json.dumps(rec) + "\n"); out.flush()
                    print(f"{row['id']} {m} single:{qid} lat={rec['latency_ms']} err={err}", flush=True)
                    time.sleep(args.delay)
                # condition batch: all questions one call
                res, attempts, status, err = call_with_retry(m, row["state"], row["questions"])
                rec = {"run_id": run_id, "condition": "batch", "n_questions": len(qids), "qid": None,
                       "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       "state_id": row["id"], "domain": row["domain"], "tier": row["tier"],
                       "provider": m, "model": (res["model"] if res else m),
                       "latency_ms": (res["latency_ms"] if res else None),
                       "usage": (res["usage"] if res else None),
                       "cost_usd": (cost_usd(m, res["usage"]) if res else None),
                       "answers": (res["answers"] if res else None),
                       "gold": row["gold"], "http_status": status, "attempts": attempts, "error": err}
                out.write(json.dumps(rec) + "\n"); out.flush()
                print(f"{row['id']} {m} batch lat={rec['latency_ms']} err={err}", flush=True)
                time.sleep(args.delay)
    print(f"-> {args.out}")

if __name__ == "__main__":
    main()
