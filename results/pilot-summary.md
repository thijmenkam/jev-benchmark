# Benchmark summary (pilot.jsonl, n=80 calls)

> Plain-language first. Each number gets a one-sentence translation (EXPERIMENT.md Appendix A).
> Verdicts: **clear win / roughly tied / too close to call**.

## In one paragraph
Overall % questions right: **clef 79.0%**, **flash 86.0%**, **jev 87.7%**, **openai 80.7%**.
In plain English: out of 100 questions, jev gets 87.7 right — the highest here. Cost per 1k states ranges clef $0.0892, flash $0.0335, jev $0.0185, openai $0.044. Cheapest-per-call is not automatically cheapest-per-correct-answer (see table).

## Accuracy — did it get the right answer?
| model | overall | noul | choice (macro-F1) | score (MAE / within-1) | exact-match/state |
|---|---|---|---|---|---|
| clef | 79.0% | 80.0% (F1 0.8) | 75.0% (F1 0.75) | 82.3% (MAE 0.176, ±1 1.0) | 60.0% |
| flash | 86.0% | 85.0% (F1 0.8) | 90.0% (F1 0.9133) | 82.3% (MAE 0.176, ±1 1.0) | 65.0% |
| jev | 87.7% | 95.0% (F1 0.9412) | 85.0% (F1 0.8971) | 82.3% (MAE 0.176, ±1 1.0) | 65.0% |
| openai | 80.7% | 95.0% (F1 0.9412) | 65.0% (F1 0.6042) | 82.3% (MAE 0.176, ±1 1.0) | 45.0% |

In plain English: **overall** = of 100 questions how many right. **Exact-match** = whole ticket perfect (all questions right) — stricter. **MAE** = average levels off on 1–4 scales (lower better). **Within-1** = right or one level off.

## Trust — can you believe '90% sure'?
| model | ECE (gap) | Brier | 90%+-but-wrong | conf right vs wrong | acc at 80% automation |
|---|---|---|---|---|---|
| clef | 0.088 | 0.1263 | 1.8% of all Qs | 0.895 vs 0.69 | 88.9% |
| flash | 0.1357 | 0.1223 | 5.3% of all Qs | 0.863 vs 0.764 | 88.9% |
| jev | 0.0484 | 0.0918 | 1.8% of all Qs | 0.886 vs 0.717 | 91.1% |
| openai | 0.0977 | 0.126 | 3.5% of all Qs | 0.935 vs 0.753 | 86.7% |

In plain English: **ECE** = when it says 90% sure on 100 cases, how far from 90 right is it (lower better; 0.03 = honest, 0.15 = bluffing). **90%-but-wrong** = dangerous mistakes. **Acc at 80% automation** = if you auto-act on the 80% most confident and hand the rest to humans, how right is the auto part.

## Speed, cost, stability
| model | typical (p50) | bad-day (p95) | error rate | $/1k states | $/correct answer |
|---|---|---|---|---|---|
| clef | 389.9ms | 1062.3ms | 0.0% | $0.0892 | $4e-05 |
| flash | 331.8ms | 519.6ms | 0.0% | $0.0335 | $1e-05 |
| jev | 287.9ms | 475.9ms | 0.0% | $0.0185 | $1e-05 |
| openai | 212.2ms | 1553.4ms | 0.0% | $0.044 | $2e-05 |

In plain English: **typical** = half of calls faster than this. **Bad-day (p95)** = 19 of 20 calls faster — size your timeout here. **$/correct** picks the value winner: a cheap model that is often wrong loses.

## Is the gap real or luck? (n≈57 questions)
- **clef_vs_flash**: gap -7.0 pts, 95% range [-17.5, +3.5] → **too close to call**. Head-to-head disagreements: 3 vs 7 (McNemar p=0.3438). Agree 82.5% of the time.
- **clef_vs_jev**: gap -8.8 pts, 95% range [-21.1, +1.8] → **too close to call**. Head-to-head disagreements: 3 vs 8 (McNemar p=0.2266). Agree 80.7% of the time.
- **clef_vs_openai**: gap -1.8 pts, 95% range [-14.0, +10.5] → **too close to call**. Head-to-head disagreements: 5 vs 6 (McNemar p=1.0). Agree 80.7% of the time.
- **flash_vs_jev**: gap -1.8 pts, 95% range [-12.3, +8.8] → **too close to call**. Head-to-head disagreements: 4 vs 5 (McNemar p=1.0). Agree 84.2% of the time.
- **flash_vs_openai**: gap +5.3 pts, 95% range [-7.0, +17.5] → **too close to call**. Head-to-head disagreements: 9 vs 6 (McNemar p=0.6072). Agree 73.7% of the time.
- **jev_vs_openai**: gap +7.0 pts, 95% range [-1.8, +15.8] → **too close to call**. Head-to-head disagreements: 5 vs 1 (McNemar p=0.2188). Agree 89.5% of the time.

In plain English: the range is 'after re-shuffling 2,000 times, the gap fell here 95% of the time.' If it crosses zero, call it a tie — you need more data.

## Slices (where do gaps widen?)
- **clef** by tier: ambiguous 66.7% (n=3); borderline 86.7% (n=15); clear 76.9% (n=39)
- **flash** by tier: ambiguous 66.7% (n=3); borderline 80.0% (n=15); clear 89.7% (n=39)
- **jev** by tier: ambiguous 66.7% (n=3); borderline 73.3% (n=15); clear 94.9% (n=39)
- **openai** by tier: ambiguous 100.0% (n=3); borderline 73.3% (n=15); clear 82.0% (n=39)

In plain English: expect clear cases to score highest; if borderline/ambiguous collapses for one model, don't use it for hard cases.
- **clef** by domain: guardrail 66.7% (n=3); invoice 100.0% (n=15); security 91.7% (n=12); support 81.0% (n=21); toolcall 0.0% (n=6)
- **flash** by domain: guardrail 66.7% (n=3); invoice 86.7% (n=15); security 91.7% (n=12); support 81.0% (n=21); toolcall 100.0% (n=6)
- **jev** by domain: guardrail 66.7% (n=3); invoice 86.7% (n=15); security 91.7% (n=12); support 85.7% (n=21); toolcall 100.0% (n=6)
- **openai** by domain: guardrail 100.0% (n=3); invoice 73.3% (n=15); security 91.7% (n=12); support 85.7% (n=21); toolcall 50.0% (n=6)
- OOS abstention (said 'not sure' <60% on nonsense inputs — higher better): clef 0%, flash 0%, jev 0%, openai 0%.
- Paraphrase flips (same ticket reworded, answer changed — lower better): clef 0.0% (n=0), flash 0.0% (n=0), jev 0.0% (n=0), openai 0.0% (n=0).
