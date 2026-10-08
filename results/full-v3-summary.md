# Benchmark summary (full-v3.jsonl, n=2716 calls)

> Plain-language first. Each number gets a one-sentence translation (EXPERIMENT.md Appendix A).
> Verdicts: **clear win / roughly tied / too close to call**.

## In one paragraph
Overall % questions right: **clef 75.9%**, **flash 73.1%**, **jev 74.4%**, **openai 77.3%**.
In plain English: out of 100 questions, openai gets 77.3 right — the highest here. Cost per 1k states ranges clef $0.1501, flash $0.0563, jev $0.0292, openai $0.0611. Cheapest-per-call is not automatically cheapest-per-correct-answer (see table).

## Accuracy — did it get the right answer?
| model | overall | noul | choice (macro-F1) | score (MAE / within-1) | exact-match/state |
|---|---|---|---|---|---|
| clef | 75.9% | 80.0% (F1 0.7841) | 76.0% (F1 0.7795) | 70.9% (MAE 0.375, ±1 0.9267) | 52.7% |
| flash | 73.1% | 78.2% (F1 0.755) | 76.4% (F1 0.7963) | 62.5% (MAE 0.443, ±1 0.9505) | 44.8% |
| jev | 74.4% | 81.7% (F1 0.8056) | 73.9% (F1 0.7458) | 65.8% (MAE 0.43, ±1 0.9377) | 45.2% |
| openai | 77.3% | 81.0% (F1 0.7889) | 76.1% (F1 0.7208) | 74.2% (MAE 0.326, ±1 0.9524) | 50.5% |

In plain English: **overall** = of 100 questions how many right. **Exact-match** = whole ticket perfect (all questions right) — stricter. **MAE** = average levels off on 1–4 scales (lower better). **Within-1** = right or one level off.

## Trust — can you believe '90% sure'?
| model | ECE (gap) | Brier | 90%+-but-wrong | conf right vs wrong | acc at 80% automation |
|---|---|---|---|---|---|
| clef | 0.0803 | 0.1643 | 6.0% of all Qs | 0.875 vs 0.729 | 81.8% |
| flash | 0.0922 | 0.1755 | 3.0% of all Qs | 0.85 vs 0.707 | 78.4% |
| jev | 0.09 | 0.1656 | 5.6% of all Qs | 0.874 vs 0.716 | 81.8% |
| openai | 0.1009 | 0.1643 | 7.1% of all Qs | 0.9 vs 0.775 | 83.2% |

In plain English: **ECE** = when it says 90% sure on 100 cases, how far from 90 right is it (lower better; 0.03 = honest, 0.15 = bluffing). **90%-but-wrong** = dangerous mistakes. **Acc at 80% automation** = if you auto-act on the 80% most confident and hand the rest to humans, how right is the auto part.

## Speed, cost, stability
| model | typical (p50) | bad-day (p95) | error rate | $/1k states | $/correct answer |
|---|---|---|---|---|---|
| clef | 413.1ms | 2495.6ms | 0.0% | $0.1501 | $7e-05 |
| flash | 313.8ms | 926.3ms | 0.0% | $0.0563 | $3e-05 |
| jev | 272.3ms | 337.3ms | 0.0% | $0.0292 | $1e-05 |
| openai | 205.1ms | 2900.4ms | 0.0% | $0.0611 | $3e-05 |

In plain English: **typical** = half of calls faster than this. **Bad-day (p95)** = 19 of 20 calls faster — size your timeout here. **$/correct** picks the value winner: a cheap model that is often wrong loses.

## Is the gap real or luck? (n≈1904 questions)
- **clef_vs_flash**: gap +2.9 pts, 95% range [+1.4, +4.5] → **real gap**. Head-to-head disagreements: 153 vs 98 (McNemar p=0.0006). Agree 86.8% of the time.
- **clef_vs_jev**: gap +1.6 pts, 95% range [-0.2, +3.4] → **too close to call**. Head-to-head disagreements: 159 vs 129 (McNemar p=0.0873). Agree 84.9% of the time.
- **clef_vs_openai**: gap -1.4 pts, 95% range [-3.3, +0.5] → **too close to call**. Head-to-head disagreements: 164 vs 190 (McNemar p=0.1839). Agree 81.4% of the time.
- **flash_vs_jev**: gap -1.3 pts, 95% range [-3.2, +0.5] → **too close to call**. Head-to-head disagreements: 151 vs 176 (McNemar p=0.1844). Agree 82.8% of the time.
- **flash_vs_openai**: gap -4.3 pts, 95% range [-6.2, -2.2] → **real gap**. Head-to-head disagreements: 158 vs 239 (McNemar p=0.0001). Agree 79.1% of the time.
- **jev_vs_openai**: gap -2.9 pts, 95% range [-4.5, -1.4] → **real gap**. Head-to-head disagreements: 87 vs 143 (McNemar p=0.0003). Agree 87.9% of the time.

In plain English: the range is 'after re-shuffling 2,000 times, the gap fell here 95% of the time.' If it crosses zero, call it a tie — you need more data.

## Slices (where do gaps widen?)
- **clef** by tier: ambiguous 60.7% (n=216); borderline 67.8% (n=513); clear 80.2% (n=1046); oos 99.2% (n=129)
- **flash** by tier: ambiguous 57.9% (n=216); borderline 64.5% (n=513); clear 79.5% (n=1046); oos 80.6% (n=129)
- **jev** by tier: ambiguous 73.6% (n=216); borderline 65.3% (n=513); clear 77.0% (n=1046); oos 90.7% (n=129)
- **openai** by tier: ambiguous 76.8% (n=216); borderline 70.4% (n=513); clear 78.8% (n=1046); oos 93.8% (n=129)

In plain English: expect clear cases to score highest; if borderline/ambiguous collapses for one model, don't use it for hard cases.
- **clef** by domain: guardrail 73.3% (n=300); invoice 86.7% (n=369); security 69.0% (n=435); support 78.5% (n=534); toolcall 70.3% (n=266)
- **flash** by domain: guardrail 65.0% (n=300); invoice 80.8% (n=369); security 69.2% (n=435); support 75.8% (n=534); toolcall 72.2% (n=266)
- **jev** by domain: guardrail 80.0% (n=300); invoice 77.0% (n=369); security 66.0% (n=435); support 79.8% (n=534); toolcall 67.3% (n=266)
- **openai** by domain: guardrail 84.0% (n=300); invoice 79.7% (n=369); security 72.0% (n=435); support 82.8% (n=534); toolcall 64.3% (n=266)
- OOS abstention (said 'not sure' <60% on nonsense inputs — higher better): clef 2.3%, flash 17.8%, jev 2.3%, openai 4.7%.
- Paraphrase flips (same ticket reworded, answer changed — lower better): clef 14.9% (n=134), flash 10.4% (n=134), jev 14.9% (n=134), openai 19.4% (n=134).
