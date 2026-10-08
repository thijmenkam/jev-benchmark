# Probe results (repeats-all.jsonl, batching-all.jsonl)

## Determinism — 'ask the same thing 3 times, same answer?'
| model | questions | identical all 3 rounds | noul prob spread (mean std) | round accuracies |
|---|---|---|---|---|
| clef | 83 | 100.0% | 0.0 | [0.892, 0.892, 0.892] |
| flash | 83 | 100.0% | 0.0 | [0.855, 0.855, 0.855] |
| jev | 83 | 97.6% | 0.0031 | [0.855, 0.88, 0.88] |
| openai | 83 | 100.0% | 0.0 | [0.831, 0.831, 0.831] |

In plain English: **identical all 3 rounds** = of 100 questions, how many gave the same top answer every time. High 90s = deterministic scorer; low = sampling involved, so don't cache blindly. **Round accuracies** show whether quality drifts run to run.

## Batching — '3 separate calls vs 1 call with 3 questions?'
| model | tokens single (sum of 3) | tokens batch (1 call) | saving | latency 3×sum vs 1 call | acc single | acc batch | same answer |
|---|---|---|---|---|---|---|---|---|
| flash | 628/state | 392/state | 38% fewer | 1132ms vs 384ms | 80.0% (n=60) | 78.3% (n=60) | 98.3% |
| jev | 1091/state | 458/state | 58% fewer | 861ms vs 270ms | 86.7% (n=60) | 86.7% (n=60) | 100.0% |
| openai | 590/state | 475/state | 20% fewer | 1291ms vs 220ms | 86.7% (n=60) | 86.7% (n=60) | 100.0% |

In plain English: **saving** = how much input you avoid by asking together (shared state text sent once). **Same answer** = does batching change the verdict vs asking separately — if low, batch freely; if the answers wobble, shard. Accuracy columns say whether batching costs quality.
