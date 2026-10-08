"""Analyze benchmark JSONL -> summary.json + summary.md (stdlib only).
Plain-language translations per EXPERIMENT.md Appendix A.

Usage: python analyze.py results/pilot.jsonl --out results/pilot-summary
"""
import argparse, json, math, os, random
from collections import defaultdict

random.seed(42)

def pct(x): return round(100 * x, 1)

def auc_mannwhitney(y, s):
    pos = [v for a, v in zip(y, s) if a == 1]; neg = [v for a, v in zip(y, s) if a == 0]
    if not pos or not neg: return None
    wins = ties = 0
    for p in pos:
        for n in neg:
            if p > n: wins += 1
            elif p == n: ties += 0.5
    return wins / (len(pos) * len(neg)) + ties / (len(pos) * len(neg)) * 0  # ties counted in wins already

def auc(y, s):
    pos = sorted(v for a, v in zip(y, s) if a == 1); neg = sorted(v for a, v in zip(y, s) if a == 0)
    if not pos or not neg: return None
    # rank-based
    allv = sorted([(v, a) for a, v in zip(y, s)])
    ranks, i = {}, 1
    j = 0
    rank_sum_pos = 0
    while j < len(allv):
        k = j
        while k < len(allv) and allv[k][0] == allv[j][0]: k += 1
        avg_rank = (i + i + (k - j) - 1) / 2
        for t in range(j, k):
            if allv[t][1] == 1: rank_sum_pos += avg_rank
        i += (k - j); j = k
    n1, n0 = len(pos), len(neg)
    return (rank_sum_pos - n1 * (n1 + 1) / 2) / (n1 * n0)

def ece_calc(confs, corrects, bins=10):
    n = len(confs)
    if n == 0: return None
    e = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(confs) if (c > lo and c <= hi) or (b == 0 and c == 0)]
        if not idx: continue
        acc = sum(corrects[i] for i in idx) / len(idx)
        conf = sum(confs[i] for i in idx) / len(idx)
        e += abs(acc - conf) * len(idx) / n
    return round(e, 4)

def qwk(y_true, y_pred, n_levels):
    # quadratic weighted kappa
    import itertools
    O = [[0]*n_levels for _ in range(n_levels)]
    for t, p in zip(y_true, y_pred):
        O[t][p] += 1
    N = sum(sum(r) for r in O)
    hist_t = [sum(O[i][j] for j in range(n_levels)) for i in range(n_levels)]
    hist_p = [sum(O[i][j] for i in range(n_levels)) for j in range(n_levels)]
    num = den = 0.0
    for i, j in itertools.product(range(n_levels), repeat=2):
        w = ((i - j) ** 2) / ((n_levels - 1) ** 2) if n_levels > 1 else 0
        E = hist_t[i] * hist_p[j] / N if N else 0
        num += w * O[i][j] / N if N else 0
        den += w * E / N if N else 0
    return 1 - num / den if den else None

def spearman(x, y):
    def rankdata(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0]*len(v); i = 0
        while i < len(order):
            j = i
            while j < len(order) and v[order[j]] == v[order[i]]: j += 1
            for k in range(i, j): r[order[k]] = (i + j + 1) / 2
            i = j
        return r
    if len(x) < 3: return None
    rx, ry = rankdata(x), rankdata(y)
    mx, my = sum(rx)/len(rx), sum(ry)/len(ry)
    num = sum((a-mx)*(b-my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a-mx)**2 for a in rx) * sum((b-my)**2 for b in ry))
    return round(num/den, 3) if den else None

def binom_p(n, k):
    # two-sided exact binomial p for p=0.5, observing >= max(k, n-k)
    if n == 0: return 1.0
    hi = max(k, n - k)
    p = sum(math.comb(n, i) for i in range(hi, n + 1)) / 2 ** n
    return round(min(1.0, 2 * p if hi != n / 2 else p), 4)

def parse_answer(qtype, ans, gold):
    """Return (pred_label, correct_bool, confidence_maxprob, prob_true_or_argmax_info)."""
    if ans is None or not isinstance(ans, dict): return None, False, 0.0, {}
    if qtype == "noul":
        p = ans.get("value", ans.get("probability", 0.5))
        try: p = float(p)
        except: p = 0.5
        pred = 1.0 if p >= 0.5 else 0.0
        g = float(gold)
        return pred, (pred == g), max(p, 1 - p), {"p": p}
    if qtype == "choice":
        pred = ans.get("value")
        probs = ans.get("probabilities", {}) or {}
        conf = max([float(v) for v in probs.values()] or [0.0])
        return pred, (str(pred) == str(gold)), conf, {"probs": probs}
    if qtype == "score":
        probs = ans.get("probabilities", {}) or {}
        try:
            argmax = max(probs.items(), key=lambda kv: float(kv[1]))[0] if probs else str(ans.get("value"))
            pred_idx = int(float(argmax))
        except: pred_idx = None
        try: g_idx = int(float(gold))
        except: g_idx = None
        conf = max([float(v) for v in probs.values()] or [0.0])
        ok = (pred_idx == g_idx)
        return pred_idx, ok, conf, {"pred_idx": pred_idx}
    return None, False, 0.0, {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default="results/summary")
    args = ap.parse_args()
    recs = [json.loads(l) for l in open(args.input) if l.strip()]
    providers = sorted(set(r["provider"] for r in recs))
    # per-question records
    Q = defaultdict(list)  # prov -> list of dicts
    for r in recs:
        if not r.get("answers"): continue
        for qid, ans in r["answers"].items():
            if qid.startswith("_"): continue
            gold = (r["gold"] or {}).get(qid)
            if gold is None: continue
            t = (ans or {}).get("type", "noul")
            pred, ok, conf, info = parse_answer(t, ans, gold)
            Q[r["provider"]].append({"state_id": r["state_id"], "qid": qid, "type": t,
                                     "gold": gold, "pred": pred, "ok": ok, "conf": conf,
                                     "lat": r.get("latency_ms"), "tier": r.get("tier"),
                                     "domain": r.get("domain"), "variant": r.get("format_variant")})
    stats = {}
    for p in providers:
        qs = Q[p]
        by_type = defaultdict(list)
        for q in qs: by_type[q["type"]].append(q)
        s = {"n_questions": len(qs), "n_states": len(set(q["state_id"] for q in qs))}
        s["accuracy"] = round(sum(q["ok"] for q in qs) / len(qs), 4) if qs else None
        # noul
        nq = [q for q in qs if q["type"] == "noul"]
        if nq:
            y = [int(float(q["gold"])) for q in nq]
            phat = []
            for q in nq:
                # recover p(true) from conf+pred
                phat.append(q["conf"] if float(q["pred"]) == 1.0 else 1 - q["conf"])
            tp = sum(1 for q in nq if q["ok"] and int(float(q["gold"])) == 1)
            fp = sum(1 for q in nq if not q["ok"] and int(float(q["pred"])) == 1)
            fn = sum(1 for q in nq if not q["ok"] and int(float(q["pred"])) == 0)
            prec = tp / (tp + fp) if tp + fp else 0
            rec = tp / (tp + fn) if tp + fn else 0
            f1 = 2*prec*rec/(prec+rec) if prec+rec else 0
            brier = sum((a-b)**2 for a, b in zip(y, phat))/len(y)
            s["noul"] = {"n": len(nq), "acc": round(sum(q["ok"] for q in nq)/len(nq),4),
                         "f1": round(f1,4), "auc": (round(auc(y,phat),4) if auc(y,phat) is not None else None),
                         "brier": round(brier,4), "ece": ece_calc(phat, [q["ok"] for q in nq])}
        ch = [q for q in qs if q["type"] == "choice"]
        if ch:
            labels = sorted(set([str(q["gold"]) for q in ch] + [str(q["pred"]) for q in ch]))
            f1s = []
            for lab in labels:
                tp = sum(1 for q in ch if str(q["pred"])==lab and str(q["gold"])==lab)
                fp = sum(1 for q in ch if str(q["pred"])==lab and str(q["gold"])!=lab)
                fn = sum(1 for q in ch if str(q["pred"])!=lab and str(q["gold"])==lab)
                pr = tp/(tp+fp) if tp+fp else 0; rc = tp/(tp+fn) if tp+fn else 0
                f1s.append(2*pr*rc/(pr+rc) if pr+rc else 0)
            s["choice"] = {"n": len(ch), "acc": round(sum(q["ok"] for q in ch)/len(ch),4),
                           "macro_f1": round(sum(f1s)/len(f1s),4) if f1s else 0}
        sc = [q for q in qs if q["type"] == "score"]
        if sc:
            errs = [abs(int(float(q["pred"]))-int(float(q["gold"]))) if q["pred"] is not None else None for q in sc]
            errs = [e for e in errs if e is not None]
            yt = [int(float(q["gold"])) for q in sc if q["pred"] is not None]
            yp = [int(float(q["pred"])) for q in sc if q["pred"] is not None]
            nl = max(yt+yp)+1 if yt else 0
            s["score"] = {"n": len(sc), "acc": round(sum(q["ok"] for q in sc)/len(sc),4),
                          "mae": round(sum(errs)/len(errs),3) if errs else None,
                          "within1": round(sum(1 for e in errs if e<=1)/len(errs),4) if errs else None,
                          "qwk": (round(qwk(yt,yp,nl),3) if nl and len(yt)>=3 else None),
                          "spearman": spearman(yp, yt)}
        # calibration overall
        confs = [q["conf"] for q in qs]; oks = [q["ok"] for q in qs]
        s["ece_all"] = ece_calc(confs, oks)
        s["brier_all"] = round(sum((c - (1 if o else 0))**2 for c, o in zip(confs, oks))/len(qs),4) if qs else None
        s["overconf90"] = round(sum(1 for q in qs if q["conf"]>=0.9 and not q["ok"])/len(qs),4) if qs else None
        s["meanconf_ok"] = round(sum(q["conf"] for q in qs if q["ok"])/max(1,sum(q["ok"] for q in qs)),3)
        s["meanconf_bad"] = round(sum(q["conf"] for q in qs if not q["ok"])/max(1,sum(1 for q in qs if not q["ok"])),3)
        # selective: accuracy at 80% coverage (most confident 80% of questions)
        order = sorted(qs, key=lambda q: -q["conf"])
        k = max(1, int(0.8*len(order)))
        top = order[:k]
        s["acc_at_80cov"] = round(sum(q["ok"] for q in top)/len(top),4) if top else None
        # by tier/domain
        for key in ("tier", "domain", "variant"):
            d = defaultdict(list)
            for q in qs: d[str(q[key])].append(q)
            s["by_"+key] = {kk: {"n": len(vv), "acc": round(sum(q["ok"] for q in vv)/len(vv),4)} for kk, vv in sorted(d.items())}
        # joint exact match per state
        per_state = defaultdict(list)
        for q in qs: per_state[q["state_id"]].append(q["ok"])
        s["exact_match"] = round(sum(1 for v in per_state.values() if all(v))/len(per_state),4) if per_state else None
        # latency/cost/errors from raw recs
        raw = [r for r in recs if r["provider"]==p]
        lats = sorted(r["latency_ms"] for r in raw if r.get("latency_ms") is not None)
        def qtl(a, q):
            if not a: return None
            i = min(len(a)-1, int(q*len(a)))
            return round(sorted(a)[i],1)
        s["latency"] = {"n": len(lats), "mean": round(sum(lats)/len(lats),1) if lats else None,
                        "p50": qtl(lats,.5), "p95": qtl(lats,.95),
                        "err_rate": round(sum(1 for r in raw if r.get("error"))/len(raw),4) if raw else None}
        costs = [r["cost_usd"] for r in raw if r.get("cost_usd")]
        tot = sum(costs)
        s["cost"] = {"total_usd": round(tot,5), "per_1k_states": round(tot/max(1,len(raw))*1000,4),
                     "per_correct_q": round(tot/max(1,sum(q["ok"] for q in qs)),5)}
        toks = [((r.get("usage") or {}).get("input_tokens"), (r.get("usage") or {}).get("output_tokens")) for r in raw]
        toks = [t for t in toks if t[0] is not None]
        s["tokens"] = {"mean_in": round(sum(t[0] for t in toks)/len(toks),1) if toks else None,
                       "mean_out": round(sum(t[1] or 0 for t in toks)/len(toks),2) if toks else None}
        # OOS abstention
        oos = [q for q in qs if q["tier"]=="oos"]
        s["oos_abstain60"] = round(sum(1 for q in oos if q["conf"]<0.6)/len(oos),3) if oos else None
        stats[p] = s

    # pairwise: accuracy gaps with bootstrap CI (paired by state-question), McNemar, agreement
    qids = sorted(set((q["state_id"], q["qid"]) for qs in Q.values() for q in qs))
    ok_by = {p: {(q["state_id"], q["qid"]): q["ok"] for q in Q[p]} for p in providers}
    pairs = {}
    for i in range(len(providers)):
        for j in range(i+1, len(providers)):
            a, b = providers[i], providers[j]
            common = [k for k in qids if k in ok_by[a] and k in ok_by[b]]
            da = sum(1 for k in common if ok_by[a][k] and not ok_by[b][k])
            db = sum(1 for k in common if ok_by[b][k] and not ok_by[a][k])
            gap = (sum(ok_by[a][k] for k in common)-sum(ok_by[b][k] for k in common))/len(common) if common else 0
            # bootstrap
            import random as _r
            gaps = []
            for _ in range(2000):
                samp = [_r.choice(common) for _ in common]
                g = (sum(ok_by[a][k] for k in samp)-sum(ok_by[b][k] for k in samp))/len(samp)
                gaps.append(g)
            gaps.sort()
            ci = (round(gaps[50],3), round(gaps[1950],3))
            agree = sum(1 for k in common if ok_by[a][k]==ok_by[b][k])/len(common) if common else None
            pairs[f"{a}_vs_{b}"] = {"n": len(common), "gap": round(gap,3),
                "ci95": list(ci), "mcnemar_p": binom_p(da+db, da),
                "disagree_a_right": da, "disagree_b_right": db,
                "agree_rate": round(agree,3) if agree is not None else None}
    # paraphrase flips
    flips = {}
    for p in providers:
        by_state = {}
        for q in Q[p]: by_state.setdefault(q["state_id"], {})[q["qid"]] = q["pred"]
        # need mapping paraphrase->original from gold file? use state_id suffix
        n = fl = 0
        for sid, preds in by_state.items():
            if "-para" in sid or "-json" in sid or "-long" in sid:
                orig = sid.replace("-para","").replace("-json","").replace("-long","")
                if orig in by_state:
                    n += 1
                    if any(str(by_state[orig].get(k))!=str(v) for k,v in preds.items()): fl += 1
        flips[p] = {"n_pairs": n, "flip_rate": round(fl/max(1,n),3)}

    out = {"providers": stats, "pairs": pairs, "flips": flips, "n_records": len(recs)}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(out, open(args.out+".json","w"), indent=2)

    # markdown with plain language
    L = [f"# Benchmark summary ({os.path.basename(args.input)}, n={len(recs)} calls)",
         "", "> Plain-language first. Each number gets a one-sentence translation (EXPERIMENT.md Appendix A).",
         "> Verdicts: **clear win / roughly tied / too close to call**.", ""]
    L.append("## In one paragraph")
    accs = {p: stats[p]["accuracy"] for p in providers}
    best = max(accs, key=lambda k: accs[k] or 0)
    L.append(f"Overall % questions right: " + ", ".join(f"**{p} {pct(accs[p])}%**" for p in providers) + ".")
    L.append(f"In plain English: out of 100 questions, {best} gets {pct(accs[best])} right — the highest here. "
             f"Cost per 1k states ranges " + ", ".join(f"{p} ${stats[p]['cost']['per_1k_states']}" for p in providers) + ". "
             "Cheapest-per-call is not automatically cheapest-per-correct-answer (see table).")
    L.append("")
    L.append("## Accuracy — did it get the right answer?")
    L.append("| model | overall | noul | choice (macro-F1) | score (MAE / within-1) | exact-match/state |")
    L.append("|---|---|---|---|---|---|")
    for p in providers:
        s = stats[p]
        L.append(f"| {p} | {pct(s['accuracy'])}% | {(pct(s.get('noul',{}).get('acc',0)) if s.get('noul') else '—')}% (F1 {s.get('noul',{}).get('f1','—')}) "
                 f"| {(pct(s.get('choice',{}).get('acc',0)) if s.get('choice') else '—')}% (F1 {s.get('choice',{}).get('macro_f1','—')}) "
                 f"| {(pct(s.get('score',{}).get('acc',0)) if s.get('score') else '—')}% (MAE {s.get('score',{}).get('mae','—')}, ±1 {s.get('score',{}).get('within1','—')}) "
                 f"| {pct(s['exact_match'])}% |")
    L.append("")
    L.append("In plain English: **overall** = of 100 questions how many right. **Exact-match** = whole ticket perfect (all questions right) — stricter. **MAE** = average levels off on 1–4 scales (lower better). **Within-1** = right or one level off.")
    L.append("")
    L.append("## Trust — can you believe '90% sure'?")
    L.append("| model | ECE (gap) | Brier | 90%+-but-wrong | conf right vs wrong | acc at 80% automation |")
    L.append("|---|---|---|---|---|---|")
    for p in providers:
        s = stats[p]
        L.append(f"| {p} | {s['ece_all']} | {s['brier_all']} | {pct(s['overconf90'])}% of all Qs | {s['meanconf_ok']} vs {s['meanconf_bad']} | {pct(s['acc_at_80cov'])}% |")
    L.append("")
    L.append("In plain English: **ECE** = when it says 90% sure on 100 cases, how far from 90 right is it (lower better; 0.03 = honest, 0.15 = bluffing). **90%-but-wrong** = dangerous mistakes. **Acc at 80% automation** = if you auto-act on the 80% most confident and hand the rest to humans, how right is the auto part.")
    L.append("")
    L.append("## Speed, cost, stability")
    L.append("| model | typical (p50) | bad-day (p95) | error rate | $/1k states | $/correct answer |")
    L.append("|---|---|---|---|---|---|")
    for p in providers:
        s = stats[p]
        L.append(f"| {p} | {s['latency']['p50']}ms | {s['latency']['p95']}ms | {pct(s['latency']['err_rate'])}% | ${s['cost']['per_1k_states']} | ${s['cost']['per_correct_q']} |")
    L.append("")
    L.append("In plain English: **typical** = half of calls faster than this. **Bad-day (p95)** = 19 of 20 calls faster — size your timeout here. **$/correct** picks the value winner: a cheap model that is often wrong loses.")
    L.append("")
    L.append("## Is the gap real or luck? (n≈%d questions)" % len(qids))
    for k, v in pairs.items():
        lo, hi = v["ci95"]
        verdict = "too close to call" if lo <= 0 <= hi else "real gap"
        L.append(f"- **{k}**: gap {v['gap']*100:+.1f} pts, 95% range [{lo*100:+.1f}, {hi*100:+.1f}] → **{verdict}**. "
                 f"Head-to-head disagreements: {v['disagree_a_right']} vs {v['disagree_b_right']} (McNemar p={v['mcnemar_p']}). "
                 f"Agree {pct(v['agree_rate'])}% of the time.")
    L.append("")
    L.append("In plain English: the range is 'after re-shuffling 2,000 times, the gap fell here 95% of the time.' If it crosses zero, call it a tie — you need more data.")
    L.append("")
    L.append("## Slices (where do gaps widen?)")
    for p in providers:
        s = stats[p]
        L.append(f"- **{p}** by tier: " + "; ".join(f"{k} {pct(v['acc'])}% (n={v['n']})" for k, v in s["by_tier"].items()))
    L.append("")
    L.append("In plain English: expect clear cases to score highest; if borderline/ambiguous collapses for one model, don't use it for hard cases.")
    for p in providers:
        s = stats[p]
        L.append(f"- **{p}** by domain: " + "; ".join(f"{k} {pct(v['acc'])}% (n={v['n']})" for k, v in s["by_domain"].items()))
    L.append(f"- OOS abstention (said 'not sure' <60% on nonsense inputs — higher better): " +
             ", ".join(f"{p} {pct(stats[p]['oos_abstain60'] or 0)}%" for p in providers) + ".")
    L.append(f"- Paraphrase flips (same ticket reworded, answer changed — lower better): " +
             ", ".join(f"{p} {pct(flips[p]['flip_rate'])}% (n={flips[p]['n_pairs']})" for p in providers) + ".")
    md = "\n".join(L) + "\n"
    open(args.out+".md","w").write(md)
    print(md)

if __name__ == "__main__":
    main()
