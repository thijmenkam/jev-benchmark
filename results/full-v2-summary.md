# Benchmark summary (full-v2.jsonl, n=1200 calls)

> Plain-language first. Each number gets a one-sentence translation (EXPERIMENT.md Appendix A).
> Verdicts: **clear win / roughly tied / too close to call**.

## In one paragraph
Overall % questions right: **clef 84.7%**, **flash 82.4%**, **jev 85.6%**, **openai 87.6%**.
In plain English: out of 100 questions, openai gets 87.6 right — the highest here. Cost per 1k states ranges clef $0.2245, flash $0.0842, jev $0.0423, openai $0.0822. Cheapest-per-call is not automatically cheapest-per-correct-answer (see table).

## Accuracy — did it get the right answer?
| model | overall | noul | choice (macro-F1) | score (MAE / within-1) | exact-match/state |
|---|---|---|---|---|---|
| clef | 84.7% | 90.7% (F1 0.9054) | 83.7% (F1 0.8807) | 78.5% (MAE 0.215, ±1 1.0) | 65.7% |
| flash | 82.4% | 88.3% (F1 0.8736) | 86.7% (F1 0.9081) | 69.8% (MAE 0.302, ±1 1.0) | 59.3% |
| jev | 85.6% | 94.3% (F1 0.9457) | 82.0% (F1 0.8569) | 79.3% (MAE 0.227, ±1 0.9793) | 61.3% |
| openai | 87.6% | 92.0% (F1 0.9216) | 84.0% (F1 0.8094) | 86.8% (MAE 0.14, ±1 0.9917) | 65.3% |

In plain English: **overall** = of 100 questions how many right. **Exact-match** = whole ticket perfect (all questions right) — stricter. **MAE** = average levels off on 1–4 scales (lower better). **Within-1** = right or one level off.

## Trust — can you believe '90% sure'?
| model | ECE (gap) | Brier | 90%+-but-wrong | conf right vs wrong | acc at 80% automation |
|---|---|---|---|---|---|
| clef | 0.0365 | 0.1068 | 2.5% of all Qs | 0.895 vs 0.719 | 90.2% |
| flash | 0.0671 | 0.1218 | 2.4% of all Qs | 0.88 vs 0.722 | 89.8% |
| jev | 0.0377 | 0.102 | 2.6% of all Qs | 0.895 vs 0.717 | 91.4% |
| openai | 0.0308 | 0.0932 | 3.4% of all Qs | 0.915 vs 0.752 | 93.0% |

In plain English: **ECE** = when it says 90% sure on 100 cases, how far from 90 right is it (lower better; 0.03 = honest, 0.15 = bluffing). **90%-but-wrong** = dangerous mistakes. **Acc at 80% automation** = if you auto-act on the 80% most confident and hand the rest to humans, how right is the auto part.

## Speed, cost, stability
| model | typical (p50) | bad-day (p95) | error rate | $/1k states | $/correct answer |
|---|---|---|---|---|---|
| clef | 459.9ms | 3459.7ms | 0.0% | $0.2245 | $9e-05 |
| flash | 325.2ms | 1015.3ms | 0.0% | $0.0842 | $4e-05 |
| jev | 272.4ms | 339.6ms | 0.0% | $0.0423 | $2e-05 |
| openai | 192.3ms | 451.4ms | 0.0% | $0.0822 | $3e-05 |

In plain English: **typical** = half of calls faster than this. **Bad-day (p95)** = 19 of 20 calls faster — size your timeout here. **$/correct** picks the value winner: a cheap model that is often wrong loses.

## Is the gap real or luck? (n≈842 questions)
- **clef_vs_flash**: gap +2.3 pts, 95% range [+0.4, +4.2] → **real gap**. Head-to-head disagreements: 48 vs 29 (McNemar p=0.0395). Agree 90.9% of the time.
- **clef_vs_jev**: gap -1.0 pts, 95% range [-3.0, +1.0] → **too close to call**. Head-to-head disagreements: 33 vs 41 (McNemar p=0.416). Agree 91.2% of the time.
- **clef_vs_openai**: gap -3.0 pts, 95% range [-5.5, -0.5] → **real gap**. Head-to-head disagreements: 53 vs 78 (McNemar p=0.0356). Agree 84.4% of the time.
- **flash_vs_jev**: gap -3.2 pts, 95% range [-5.8, -0.6] → **real gap**. Head-to-head disagreements: 48 vs 75 (McNemar p=0.0187). Agree 85.4% of the time.
- **flash_vs_openai**: gap -5.2 pts, 95% range [-8.2, -2.4] → **real gap**. Head-to-head disagreements: 62 vs 106 (McNemar p=0.0009). Agree 80.0% of the time.
- **jev_vs_openai**: gap -2.0 pts, 95% range [-4.0, +0.1] → **too close to call**. Head-to-head disagreements: 30 vs 47 (McNemar p=0.0675). Agree 90.9% of the time.

In plain English: the range is 'after re-shuffling 2,000 times, the gap fell here 95% of the time.' If it crosses zero, call it a tie — you need more data.

## Slices (where do gaps widen?)
- **clef** by tier: ambiguous 68.6% (n=105); borderline 90.6% (n=203); clear 84.4% (n=495); oos 100.0% (n=39)
- **flash** by tier: ambiguous 63.8% (n=105); borderline 85.2% (n=203); clear 85.0% (n=495); oos 84.6% (n=39)
- **jev** by tier: ambiguous 81.9% (n=105); borderline 81.3% (n=203); clear 87.1% (n=495); oos 100.0% (n=39)
- **openai** by tier: ambiguous 91.4% (n=105); borderline 78.8% (n=203); clear 89.5% (n=495); oos 100.0% (n=39)

In plain English: expect clear cases to score highest; if borderline/ambiguous collapses for one model, don't use it for hard cases.
- **clef** by domain: guardrail 74.2% (n=120); invoice 91.3% (n=183); security 88.5% (n=192); support 81.8% (n=231); toolcall 84.5% (n=116)
- **flash** by domain: guardrail 66.7% (n=120); invoice 83.1% (n=183); security 87.5% (n=192); support 79.7% (n=231); toolcall 94.8% (n=116)
- **jev** by domain: guardrail 86.7% (n=120); invoice 79.8% (n=183); security 89.1% (n=192); support 87.5% (n=231); toolcall 84.5% (n=116)
- **openai** by domain: guardrail 95.0% (n=120); invoice 83.1% (n=183); security 90.1% (n=192); support 87.9% (n=231); toolcall 82.8% (n=116)
- OOS abstention (said 'not sure' <60% on nonsense inputs — higher better): clef 0%, flash 25.6%, jev 0%, openai 0%.
- Paraphrase flips (same ticket reworded, answer changed — lower better): clef 12.9% (n=85), flash 11.8% (n=85), jev 12.9% (n=85), openai 16.5% (n=85).
