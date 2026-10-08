"""Backfill failed (state, provider) pairs into results/backfill.jsonl.
Usage: python backfill.py  (pairs hardcoded from full-run errors, or pass state:provider args)
Then: python merge_backfill.py -> results/full-v2.jsonl (error rows replaced).
"""
import datetime, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from benchmark import call_with_retry, cost_usd  # noqa: E402

PAIRS = [("support-011", "flash"), ("toolcall-029", "clef"),
         ("toolcall-029", "flash"), ("support-033", "clef"), ("support-033", "flash")]

def main():
    pairs = PAIRS
    if len(sys.argv) > 1:
        pairs = [tuple(a.split(":")) for a in sys.argv[1:]]
    gold = {}
    for line in open("data/gold.v1.jsonl"):
        r = json.loads(line)
        gold[r["id"]] = r
    run_id = "backfill-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs("results", exist_ok=True)
    ok = fail = 0
    with open("results/backfill.jsonl", "w") as out:
        for sid, prov in pairs:
            row = gold[sid]
            res, attempts, status, err = call_with_retry(prov, row["state"], row["questions"])
            rec = {"run_id": run_id, "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "state_id": sid, "domain": row["domain"], "tier": row["tier"],
                   "format_variant": row.get("format_variant", "text"),
                   "provider": prov, "model": (res["model"] if res else prov),
                   "latency_ms": (res["latency_ms"] if res else None),
                   "usage": (res["usage"] if res else None),
                   "cost_usd": (cost_usd(prov, res["usage"]) if res else None),
                   "answers": (res["answers"] if res else None),
                   "gold": row["gold"], "http_status": status, "attempts": attempts, "error": err}
            out.write(json.dumps(rec) + "\n"); out.flush()
            print(f"{sid} {prov} lat={rec['latency_ms']} err={err}", flush=True)
            ok, fail = ok + (err is None), fail + (err is not None)
            time.sleep(1.0)
    print(f"backfill: {ok} ok, {fail} failed")
    # merge: drop error rows from full.jsonl, append backfill successes
    base = [json.loads(l) for l in open("results/full.jsonl")]
    fixed = {(json.loads(l)["state_id"], json.loads(l)["provider"]): json.loads(l)
             for l in open("results/backfill.jsonl") if not json.loads(l)["error"]}
    out_rows = [r for r in base if not (r["error"] and (r["state_id"], r["provider"]) in fixed)]
    seen = {(r["state_id"], r["provider"]) for r in out_rows}
    out_rows += [v for k, v in fixed.items() if k not in seen]
    # keep unfilled error rows as-is (still in out_rows)
    with open("results/full-v2.jsonl", "w") as fh:
        for r in out_rows:
            fh.write(json.dumps(r) + "\n")
    remaining = sum(1 for r in out_rows if r["error"])
    print(f"wrote results/full-v2.jsonl ({len(out_rows)} rows, {remaining} still errored)")

if __name__ == "__main__":
    main()
