"""Analyze repeats + batching probes -> results/probes-jo.md (stdlib only).
Usage: python analyze_probes.py results/repeats-jo.jsonl results/batching-jo.jsonl --out results/probes-jo
"""
import argparse, json, os, statistics
from collections import defaultdict
from analyze import parse_answer  # noqa: E402

def top_of(qtype, ans, gold):
    pred, ok, conf, info = parse_answer(qtype, ans, gold)
    return pred, ok, conf

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repeats"); ap.add_argument("batching"); ap.add_argument("--out", default="results/probes-jo")
    args = ap.parse_args()
    R = [json.loads(l) for l in open(args.repeats) if l.strip()]
    B = [json.loads(l) for l in open(args.batching) if l.strip()]
    L = [f"# Probe results ({os.path.basename(args.repeats)}, {os.path.basename(args.batching)})", ""]
    # ---- repeats: determinism ----
    L.append("## Determinism — 'ask the same thing 3 times, same answer?'")
    L.append("| model | questions | identical all 3 rounds | noul prob spread (mean std) | round accuracies |")
    L.append("|---|---|---|---|---|")
    for p in sorted(set(r["provider"] for r in R)):
        by_q = defaultdict(list)
        for r in R:
            if r["provider"] != p or not r.get("answers"): continue
            for qid, ans in r["answers"].items():
                if qid.startswith("_"): continue
                pred, ok, conf = top_of(ans.get("type", "noul"), ans, (r["gold"] or {}).get(qid))
                by_q[(r["state_id"], qid)].append({"round": r.get("round"), "pred": pred, "ok": ok, "conf": conf})
        n = len(by_q)
        ident = sum(1 for v in by_q.values() if len(set(str(x["pred"]) for x in v)) == 1)
        # noul prob spread: need p(true); approx from conf+pred
        spreads = []
        for (sid, qid), v in by_q.items():
            if len(v) == 3 and all(isinstance(x["pred"], float) for x in v):
                ps = [x["conf"] if x["pred"] == 1.0 else 1 - x["conf"] for x in v]
                spreads.append(statistics.pstdev(ps))
        acc_r = []
        for rnd in (1, 2, 3):
            oks = [x["ok"] for v in by_q.values() for x in v if x["round"] == rnd]
            acc_r.append(round(sum(oks) / len(oks), 3) if oks else None)
        L.append(f"| {p} | {n} | {ident/n:.1%} | { (round(sum(spreads)/len(spreads),4) if spreads else '—')} | {acc_r} |")
    L.append("")
    L.append("In plain English: **identical all 3 rounds** = of 100 questions, how many gave the same top answer every time. "
             "High 90s = deterministic scorer; low = sampling involved, so don't cache blindly. **Round accuracies** show whether quality drifts run to run.")
    L.append("")
    # ---- batching ----
    L.append("## Batching — '3 separate calls vs 1 call with 3 questions?'")
    L.append("| model | tokens single (sum of 3) | tokens batch (1 call) | saving | latency 3×sum vs 1 call | acc single | acc batch | same answer |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for p in sorted(set(r["provider"] for r in B)):
        singles = [r for r in B if r["provider"] == p and r["condition"] == "single"]
        batch = [r for r in B if r["provider"] == p and r["condition"] == "batch"]
        tok_s = sum((r["usage"] or {}).get("input_tokens", 0) for r in singles if r["usage"])
        tok_b = sum((r["usage"] or {}).get("input_tokens", 0) for r in batch if r["usage"])
        lat_s = sum(r["latency_ms"] for r in singles if r["latency_ms"])
        lat_b = sum(r["latency_ms"] for r in batch if r["latency_ms"])
        # accuracy
        def acc(recs):
            tot = ok = 0
            for r in recs:
                if not r.get("answers"): continue
                for qid, ans in r["answers"].items():
                    _, o, _ = top_of(ans.get("type", "noul"), ans, (r["gold"] or {}).get(qid))
                    tot += 1; ok += o
            return ok / tot if tot else None, tot
        a_s, n_s = acc(singles); a_b, n_b = acc(batch)
        # stability: single top vs batch top per (state, qid)
        single_top = {(r["state_id"], q): top_of(v.get("type", "noul"), v, (r["gold"] or {}).get(q))[0]
                      for r in singles if r.get("answers") for q, v in r["answers"].items()}
        match = tot2 = 0
        for r in batch:
            if not r.get("answers"): continue
            for q, v in r["answers"].items():
                if (r["state_id"], q) in single_top:
                    tot2 += 1
                    if str(single_top[(r["state_id"], q)]) == str(top_of(v.get("type", "noul"), v, (r["gold"] or {}).get(q))[0]):
                        match += 1
        n_states = len(set(r["state_id"] for r in batch))
        L.append(f"| {p} | {tok_s/n_states:.0f}/state | {tok_b/n_states:.0f}/state | {(1-tok_b/tok_s):.0%} fewer | "
                 f"{lat_s/n_states:.0f}ms vs {lat_b/n_states:.0f}ms | {a_s:.1%} (n={n_s}) | {a_b:.1%} (n={n_b}) | {match/tot2:.1%} |")
    L.append("")
    L.append("In plain English: **saving** = how much input you avoid by asking together (shared state text sent once). "
             "**Same answer** = does batching change the verdict vs asking separately — if low, batch freely; if the answers wobble, shard. "
             "Accuracy columns say whether batching costs quality.")
    md = "\n".join(L) + "\n"
    open(args.out + ".md", "w").write(md)
    print(md)

if __name__ == "__main__":
    main()
