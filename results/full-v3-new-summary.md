# Benchmark summary (full-v3-new.jsonl, n=1516 calls)

> Plain-language first. Each number gets a one-sentence translation (EXPERIMENT.md Appendix A).
> Verdicts: **clear win / roughly tied / too close to call**.

## In one paragraph
Overall % questions right: **clef 69.0%**, **flash 65.6%**, **jev 65.4%**, **openai 69.1%**.
In plain English: out of 100 questions, openai gets 69.1 right — the highest here. Cost per 1k states ranges clef $0.0912, flash $0.0342, jev $0.0189, openai $0.0444. Cheapest-per-call is not automatically cheapest-per-correct-answer (see table).

## Accuracy — did it get the right answer?
| model | overall | noul | choice (macro-F1) | score (MAE / within-1) | exact-match/state |
|---|---|---|---|---|---|
| clef | 69.0% | 71.5% (F1 0.6766) | 69.9% (F1 0.5749) | 64.8% (MAE 0.503, ±1 0.8684) | 42.5% |
| flash | 65.6% | 70.2% (F1 0.6544) | 68.3% (F1 0.5434) | 56.6% (MAE 0.556, ±1 0.9112) | 33.2% |
| jev | 65.4% | 71.8% (F1 0.6708) | 67.5% (F1 0.5282) | 54.9% (MAE 0.592, ±1 0.9046) | 32.5% |
| openai | 69.1% | 72.3% (F1 0.6557) | 69.9% (F1 0.5296) | 64.1% (MAE 0.474, ±1 0.9211) | 38.8% |

In plain English: **overall** = of 100 questions how many right. **Exact-match** = whole ticket perfect (all questions right) — stricter. **MAE** = average levels off on 1–4 scales (lower better). **Within-1** = right or one level off.

## Trust — can you believe '90% sure'?
| model | ECE (gap) | Brier | 90%+-but-wrong | conf right vs wrong | acc at 80% automation |
|---|---|---|---|---|---|
| clef | 0.1269 | 0.2099 | 8.8% of all Qs | 0.855 vs 0.732 | 74.6% |
| flash | 0.1257 | 0.2181 | 3.5% of all Qs | 0.819 vs 0.701 | 70.1% |
| jev | 0.1512 | 0.216 | 8.0% of all Qs | 0.853 vs 0.715 | 72.6% |
| openai | 0.1681 | 0.2206 | 10.0% of all Qs | 0.885 vs 0.782 | 74.3% |

In plain English: **ECE** = when it says 90% sure on 100 cases, how far from 90 right is it (lower better; 0.03 = honest, 0.15 = bluffing). **90%-but-wrong** = dangerous mistakes. **Acc at 80% automation** = if you auto-act on the 80% most confident and hand the rest to humans, how right is the auto part.

## Speed, cost, stability
| model | typical (p50) | bad-day (p95) | error rate | $/1k states | $/correct answer |
|---|---|---|---|---|---|
| clef | 398.1ms | 927.1ms | 0.0% | $0.0912 | $5e-05 |
| flash | 307.2ms | 892.2ms | 0.0% | $0.0342 | $2e-05 |
| jev | 272.3ms | 333.5ms | 0.0% | $0.0189 | $1e-05 |
| openai | 210.6ms | 3596.9ms | 0.0% | $0.0444 | $2e-05 |

In plain English: **typical** = half of calls faster than this. **Bad-day (p95)** = 19 of 20 calls faster — size your timeout here. **$/correct** picks the value winner: a cheap model that is often wrong loses.

## Is the gap real or luck? (n≈1062 questions)
- **clef_vs_flash**: gap +3.4 pts, 95% range [+1.0, +5.8] → **real gap**. Head-to-head disagreements: 105 vs 69 (McNemar p=0.0078). Agree 83.6% of the time.
- **clef_vs_jev**: gap +3.6 pts, 95% range [+0.9, +6.2] → **real gap**. Head-to-head disagreements: 126 vs 88 (McNemar p=0.0113). Agree 79.8% of the time.
- **clef_vs_openai**: gap -0.1 pts, 95% range [-2.9, +2.6] → **too close to call**. Head-to-head disagreements: 111 vs 112 (McNemar p=1.0). Agree 79.0% of the time.
- **flash_vs_jev**: gap +0.2 pts, 95% range [-2.4, +2.8] → **too close to call**. Head-to-head disagreements: 103 vs 101 (McNemar p=0.9442). Agree 80.8% of the time.
- **flash_vs_openai**: gap -3.5 pts, 95% range [-6.4, -0.7] → **real gap**. Head-to-head disagreements: 96 vs 133 (McNemar p=0.0172). Agree 78.4% of the time.
- **jev_vs_openai**: gap -3.7 pts, 95% range [-6.0, -1.3] → **real gap**. Head-to-head disagreements: 57 vs 96 (McNemar p=0.002). Agree 85.6% of the time.

In plain English: the range is 'after re-shuffling 2,000 times, the gap fell here 95% of the time.' If it crosses zero, call it a tie — you need more data.

## Slices (where do gaps widen?)
- **clef** by tier: ambiguous 53.1% (n=111); borderline 52.9% (n=310); clear 76.4% (n=551); oos 98.9% (n=90)
- **flash** by tier: ambiguous 52.2% (n=111); borderline 51.0% (n=310); clear 74.4% (n=551); oos 78.9% (n=90)
- **jev** by tier: ambiguous 65.8% (n=111); borderline 54.8% (n=310); clear 67.9% (n=551); oos 86.7% (n=90)
- **openai** by tier: ambiguous 63.1% (n=111); borderline 64.8% (n=310); clear 69.2% (n=551); oos 91.1% (n=90)

In plain English: expect clear cases to score highest; if borderline/ambiguous collapses for one model, don't use it for hard cases.
- **clef** by domain: guardrail 72.8% (n=180); invoice 82.3% (n=186); security 53.5% (n=243); support 75.9% (n=303); toolcall 59.3% (n=150)
- **flash** by domain: guardrail 63.9% (n=180); invoice 78.5% (n=186); security 54.7% (n=243); support 72.9% (n=303); toolcall 54.7% (n=150)
- **jev** by domain: guardrail 75.6% (n=180); invoice 74.2% (n=186); security 47.7% (n=243); support 73.9% (n=303); toolcall 54.0% (n=150)
- **openai** by domain: guardrail 76.7% (n=180); invoice 76.3% (n=186); security 57.6% (n=243); support 78.9% (n=303); toolcall 50.0% (n=150)
- OOS abstention (said 'not sure' <60% on nonsense inputs — higher better): clef 3.3%, flash 14.4%, jev 3.3%, openai 6.7%.
- Paraphrase flips (same ticket reworded, answer changed — lower better): clef 18.4% (n=49), flash 8.2% (n=49), jev 18.4% (n=49), openai 24.5% (n=49).
