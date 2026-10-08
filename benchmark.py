"""Benchmark runner: same states -> jev / openai / clef / clef-flash.
Logs JSONL with latency, usage, computed cost. Pilot-first, spend guardrail.

Usage:
    python benchmark.py --limit 20 --out results/pilot.jsonl
    python benchmark.py --limit 300 --out results/full.jsonl
    python benchmark.py --models jev,flash --limit 5 --out results/smoke.jsonl
"""
import argparse, datetime, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_env  # noqa: E402

load_env()
import jev as jev_mod  # noqa: E402
import openai_decisions as oai_mod  # noqa: E402
import clef as clef_mod  # noqa: E402

PRICING = {  # $ per 1M tokens; flash/openai-out to verify in pilot
    "jev": {"in": 0.042, "out": 0.0},
    "openai": {"in": 0.10, "out": 0.50},
    "clef": {"in": 0.24, "out": 0.0},
    "flash": {"in": 0.09, "out": 0.0},
}

def decide_dispatch(model_id, state, questions):
    if model_id == "jev":
        return jev_mod.decide(state, questions)
    if model_id == "openai":
        return oai_mod.decide(state, questions)
    if model_id == "clef":
        return clef_mod.decide(state, questions, model="clef")
    if model_id == "flash":
        return clef_mod.decide(state, questions, model="clef-flash")
    raise ValueError(model_id)

def cost_usd(model_id, usage):
    if not usage or "input_tokens" not in usage:
        return None
    p = PRICING[model_id]
    it = usage.get("input_tokens", 0) or 0
    ot = usage.get("output_tokens", 0) or 0
    return round(it / 1e6 * p["in"] + ot / 1e6 * p["out"], 6)

def call_with_retry(model_id, state, questions, max_retries=2):
    attempts = 0
    while True:
        attempts += 1
        try:
            res = decide_dispatch(model_id, state, questions)
            return res, attempts, 200, None
        except RuntimeError as exc:
            msg = str(exc)
            status = int(msg.split()[1].strip(":")) if msg.startswith("HTTP") else 0
            if status in (429, 500, 502, 503, 504) and attempts <= max_retries + 1 - 1 and attempts <= 3:
                time.sleep(2 * attempts)
                if attempts > max_retries:
                    return None, attempts, status, msg
                continue
            return None, attempts, status, msg
        except Exception as exc:  # network, etc.
            if attempts <= max_retries:
                time.sleep(2 * attempts)
                continue
            return None, attempts, 0, repr(exc)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default="data/gold.v1.jsonl")
    ap.add_argument("--out", default="results/run.jsonl")
    ap.add_argument("--models", default="jev,openai,clef,flash")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--ids-file", default=None, help="JSON array of state ids to run (overrides --limit)")
    ap.add_argument("--repeat", type=int, default=1, help="run the whole set N times (round number logged)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between calls")
    ap.add_argument("--max-spend", type=float, default=4.0, help="abort provider if projected spend exceeds this")
    ap.add_argument("--no-warmup", action="store_true")
    args = ap.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    with open(args.gold) as fh:
        all_rows = [json.loads(l) for l in fh if l.strip()]
    if args.ids_file:
        want = json.load(open(args.ids_file))
        rows = [r for r in all_rows if r["id"] in set(want)]
        rows.sort(key=lambda r: want.index(r["id"]))
    else:
        rows = all_rows[: args.limit]
    total_planned = len(rows) * len(models) * args.repeat
    print(f"rows={len(rows)} models={models} planned_calls={total_planned}", flush=True)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    spend = {m: 0.0 for m in models}
    done = {m: 0 for m in models}

    # warmup: 2 unlogged calls per SUT on a throwaway state
    if not args.no_warmup:
        for m in models:
            for _ in range(2):
                try:
                    decide_dispatch(m, "Warmup: checkout is slow today.", rows[0]["questions"])
                except Exception as e:
                    print(f"warmup {m} failed (continuing): {e}", flush=True)
                time.sleep(0.5)

    with open(args.out, "w") as out:
        n = 0
        for rnd in range(1, args.repeat + 1):
            for row in rows:  # round-robin per state balances time-of-day
                for m in models:
                    proj = spend[m] / max(1, done[m]) * len(rows) if done[m] else 0
                    if done[m] >= 3 and proj > args.max_spend:
                        print(f"ABORT {m}: projected ${proj:.2f} > ${args.max_spend}", flush=True)
                        continue
                    res, attempts, status, err = call_with_retry(m, row["state"], row["questions"])
                    latency = res["latency_ms"] if res else None
                    usage = res["usage"] if res else None
                    c = cost_usd(m, usage) if res else None
                    if c:
                        spend[m] += c
                    done[m] += 1
                    rec = {"run_id": run_id, "round": rnd,
                           "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                           "state_id": row["id"], "domain": row["domain"], "tier": row["tier"],
                           "format_variant": row.get("format_variant", "text"),
                           "provider": m, "model": (res["model"] if res else m),
                           "latency_ms": latency, "usage": usage, "cost_usd": c,
                           "answers": (res["answers"] if res else None),
                           "gold": row["gold"], "http_status": status, "attempts": attempts, "error": err}
                    out.write(json.dumps(rec) + "\n"); out.flush()
                    n += 1
                    print(f"[{n}/{total_planned}] r{rnd} {row['id']} {m} lat={latency} usage={usage} cost={c} err={err}", flush=True)
                    time.sleep(args.delay)
    print("spend:", {m: round(s, 4) for m, s in spend.items()}, f"-> {args.out}", flush=True)

if __name__ == "__main__":
    main()
