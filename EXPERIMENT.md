# Benchmark Experiment: Jev vs OpenAI Decisions vs Clef / Clef-flash

> Design doc first, code second. No benchmark code is written until this design is approved.
> Goal: pick the right decision model for production under a **$5 cap each for OpenAI and Cloudflare** (Jev is unconstrained — cheap).

## 1. Objective

Compare 4 systems on the **same states + same questions**, measuring which gives the best
accuracy-per-dollar at acceptable latency — not which vendor benchmark looks best.

Systems under test (SUT):

| ID | Provider | Model | Endpoint | Notes |
|----|----------|-------|----------|-------|
| `jev` | Typesafe | `jev-latest` | `https://api.typesafe.ai/v1/systemone` | text-only, 64–66k ctx, existing `jev.py` |
| `openai` | OpenAI | `gpt-6-luna` | `https://api.openai.com/v1/decisions` | translated schema (predicate/choice/score), existing `openai_decisions.py` |
| `clef` | Cloudflare Workers AI | `clef` (`@cf/cloudflare/clef`) | `.../ai/run/@cf/cloudflare/clef` | 27B, multimodal, 64k ctx, existing `clef.py` |
| `flash` | Cloudflare Workers AI | `clef-flash` (`@cf/cloudflare/clef-flash`) | `.../ai/run/@cf/cloudflare/clef-flash` | 9B, fast, 64k ctx, **not yet in `clef.py` — add `model` param** |

All calls use the repo's normalized shape: `state` + `questions{id: {type: noul|choice|score, instructions, criteria}}`.
OpenAI uses the predicate/choice/score translation already in code. Clef/flash are System One-compatible (swap `model` field).
Two adapters found in pilot and frozen: (1) Clef-flash needs its own endpoint `.../ai/run/@cf/cloudflare/clef-flash`
(same path with `clef` returns 422 "Unsupported model"), payload `model` matches the path; (2) OpenAI Decisions rejects
object `state` (HTTP 400) so dict states are `json.dumps`-stringified for OpenAI only — same semantic content, noted in the
format slice. Score prediction uses argmax-probability (raw `value` scales differ per vendor).

Non-goals (v1): fine-tuning/RL, self-hosted VRAM tests, video input, large multilingual sweep, load testing to rate limits.

## 2. Vendor claims to verify (hypotheses)

- **H-cost:** Jev cheapest per token ($0.042/M in, $0 out) < flash (~$0.09/M) < clef ($0.24/M) < OpenAI Luna ($0.10/M in + $0.50/M out). But per-*correct-decision* ranking may differ.
- **H-latency (Cloudflare-reported):** flash 38.8ms med / 122.4ms p95 < clef 209.3 / 238.6 < Jev 524.1 / 536.0. Jev docs claim 70–500ms. Luna unknown on Decisions API.
- **H-accuracy (Cloudflare self-reported, 10 benches):** clef/flash win 8/10 (BFCL, ToolRet, API-Bank, Home appliances, BANKING77, CLINC150+OOS, ESCI, PhishNChips); **Jev wins When2Call (tool-vs-clarify) and BRIGHT (reasoning retrieval)**. Flash collapses on CLINC150+OOS (66.77 vs clef 97.43) — test OOS explicitly.
- **H-reliability:** Jev 0% structured-output errors "by construction"; LLM chat baselines 0.58–45.5%. Check whether OpenAI Decisions / Clef ever return incoherent probabilities or schema violations.

## 3. Dimensions (what we measure)

### 3.1 Cost (measured, not list-price)
- Per call: `input_tokens`, `output_tokens` from each response's `usage` field + computed USD using table in §5.
- Aggregates: mean/med per call, **cost per 1k decisions**, cost per 1k *questions* (batching effect).
- **Cost per correct decision** = total $ / #correct (per question type and overall). This is the primary cost-efficiency frontier plot (x=cost, y=accuracy).
- Overhead analysis: how instructions/criteria/options inflate tokens (measure tokens with vs without criteria text).
- Guardrail: running $ total per provider, projected full-run $, % of $5 budget. Abort if projection > $4.

### 3.2 Latency (client-measured)
- `latency_ms` already captured in `common.http_post_json` (perf_counter around urlopen). Keep it; add server `usage`/timestamps if present for comparison but **client latency is primary**.
- Report per SUT: n, mean, p50, p95, p99, min/max, std, timeout rate (>60s), HTTP error rate.
- Slices: by state length (short <200 chars / medium / long >2k tokens), by #questions (1 vs 3 vs 8), by time-of-day bucket. Warm-up: 2 unlogged calls per SUT before timing.
- Note Cloudflare truncation caveat: Workers AI reportedly truncates long text to ~first 2k tokens — long-state latency/accuracy slice will expose this.

### 3.3 Accuracy — split by aspect (all need gold labels)
Core 3 question types, evaluated separately + jointly:
- **noul (binary):** accuracy, F1, AUC (from `noul` probability), ECE/Brier.
- **choice (routing/classification):** accuracy, macro-F1, per-class precision/recall, mean correct-class probability.
- **score (ordinal):** MAE, within-±1 accuracy, quadratic-weighted kappa, Spearman vs gold rank.
- **Joint:** exact-match on all questions per state (strict), average correctness.

Beyond raw correctness:
- **Calibration:** reliability diagrams + ECE (10 bins), Brier score, mean confidence on correct vs incorrect, overconfidence rate (conf≥0.9 & wrong). Decision models live/die by "number you can branch on."
- **Selective prediction / threshold utility:** accuracy-at-coverage curve (defer if max-prob < τ for τ in 0.5..0.95), AUC of that curve, accuracy at 80% coverage. Answers: "which model can safely auto-act more?"
- **Robustness:**
  - *Paraphrase invariance:* ~15% of states duplicated with rewording, same gold → flip rate per SUT.
  - *OOS / abstention:* include 10–15% out-of-scope states (gold = none-of-above / low confidence expected) → does flash really collapse like CLINC150+OOS suggests? Metric: % flagged low-confidence (<0.5) + AUROC OOS-vs-in-scope via entropy/max-prob.
  - *Ambiguity tiers:* label each case clear / borderline / ambiguous at dataset build; report accuracy per tier. Expect gaps to widen on borderline.
  - *Format/length:* same semantic state as prose vs JSON (structured record/chat log) + long state (>2k tokens) → accuracy delta. Exposes Clef truncation vs Jev/OpenAI handling.
  - *Instruction sensitivity (cheap spot-check):* 1 question reworded 2 ways on 20 states → stability.
- **Agreement / error analysis:** pairwise agreement matrix, Cohen's κ, % cases where all agree / 3-vs-1 splits, confusion pairs (which two classes get mixed). Tells us if models are interchangeable or complementary (ensemble value).

### 3.4 More (cheap, high-signal — included in v1)
- **Reliability / schema validity:** % responses with missing keys, unparsable body, probabilities not summing to ~1, unknown `choice` value, `score` out of range, extra/missing question ids. Count as errors even if HTTP 200.
- **Determinism / repeatability:** re-run 30 states 3× per SUT → % identical top-answer, std of probabilities. Flags sampling vs scoring architectures.
- **Batching efficiency:** same 8 questions as 8×1-question calls vs 1×8-question call (on 20 states, 1 SUT each to save $) → tokens, $, latency, accuracy delta. Informs prod sharding.
- **Failure taxonomy:** log every HTTP≥400, timeout, truncated response with state-id + SUT for the appendix.

Explicitly deferred (cost/complexity): images (clef/OpenAI support them, Jev doesn't — would be unfair + pricey; optional 10-image pilot only if budget remains), multilingual, adversarial jailbreaks, sustained QPS/rate-limit probing, self-hosted VRAM.

## 4. Dataset design (small, labeled, frozen)

Target **N=300 states** total (plus ~45 paraphrase duplicates + ~30 repeats = ~375 calls × 4 SUTs ≈ 1500 calls). Well under $1 (see §5). Pilot on 20 first.

Domains (mirroring prod + vendor benches), ~60 each:
1. Support triage (urgency noul + team choice[3] + frustration score[3]) — matches `DEFAULT_QUESTIONS`.
2. Invoice/billing extraction routing (choice[in 4] + noul[needs-human] + score[completeness 4]).
3. Security incident severity (noul[urgent] + choice[team 3] + score[severity 4]).
4. Tool-call vs clarify — When2Call-like (noul[should-call-tool] + choice[action 3]).
5. OOS/ambiguous guardrail set (choice + OOS gold; score with borderline gold + tier tag).

Each row: `{id, domain, state (text; + json_variant for subset), questions (reuse 5 fixed templates, 1–4 questions each), gold {qid: label}, tier (clear/borderline/ambiguous/oos), paraphrase_of (nullable)}`.
Gold labels: hand-labeled by us, 2nd-pass review on disagreements; borderline cases keep majority gold + tier tag (accuracy reported per tier, not discarded).
Freeze as `data/gold.v1.jsonl` + `data/questions.v1.json` with SHA + count script. No test-set peeking for prompt tuning beyond the 20-state pilot.

Question-count discipline: default 3 questions/call (like current demo). Batching sub-experiment uses a fixed 8-question template on 20 states only.

## 5. Budget math ($5 caps)

List prices (verify in pilot from `usage` + billing dashboards):

| SUT | Input $/1M | Output $/1M | Source |
|-----|-----------|------------|--------|
| Jev | 0.042 | 0.0 | typesafe.ai / jev-api.com |
| Clef | 0.24 | 0 (verify — no output rate published) | Cloudflare docs / unit pricing field |
| Clef-flash | **0.09 (to verify — CloudPrice/OpenRouter; some pages say 0.24 for both)** | 0 (verify) | verify via billing after pilot |
| OpenAI gpt-6-luna | 0.10 (std; flex 0.05, cached 0.01) | 0.50 | OpenAI docs 2026-09 |

Measured pilot tokens/call (assumed ~400 in / ~65 out from demo shape; **replace with pilot means**):
- Per 1k 3-question calls ≈ Jev $0.017, flash $0.036, clef $0.096, OpenAI ≈ $0.04+$0.03=$0.07.
- Full run 375 calls/SUT ≈ Jev $0.006, flash $0.014, clef $0.036, OpenAI $0.026. **Total ≈ $0.08.** Even 5× overrun or long states stay <$1.
- Headroom: $5 buys ≈ 70k OpenAI calls / 50k clef calls / 130k flash calls at demo length. We deliberately use <2k calls and spend the savings on repeats/slices, not N.
- Guardrails: (a) 20-call pilot per SUT → compute real mean tokens → re-project; (b) running spend logged per call, abort at $4 projected; (c) no retries except 429/5xx with backoff (max 2), retries logged as cost; (d) images excluded from v1.

## 6. Protocol

1. **Pilot (80 calls):** 20 states × 4 SUTs, sequential, 1 QPS, 2 warm-ups/SUT unlogged. Verify: auth, schema translation (esp. OpenAI score legend mapping + Clef `result` envelope), `usage` presence, flash pricing, truncation behavior. Freeze dataset + code after pilot.
2. **Full run:** fixed order per state shuffled once (seed 42), SUTs run state-by-state round-robin to balance time-of-day; 1 QPS per provider; 60s timeout; max 2 retries on 429/5xx only; log `{state_id, sut, latency_ms, usage, answers, raw, http_status, attempt, ts}` as JSONL.
3. **Repeats:** 30-state subset × 3 runs/SUT (interleaved, next day if possible for latency variance).
4. **Batching probe:** 20 states × (8×1 vs 1×8) on Jev + one of clef/flash + OpenAI (120 extra calls, still cents).
5. **No tuning on test:** instruction wording frozen after pilot; any rewording experiment uses a disjoint 20-state slice and is reported as its own slice.

## 7. Analysis & reporting

- Per-SUT tables: accuracy/F1/AUC/ECE/Brier/MAE/κ per question type + selective-prediction AUC + reliability-error rate + latency p50/p95 + $/1k + $/correct.
- Plots: (1) cost-vs-accuracy frontier (per correct), (2) latency p50/p95 bars, (3) reliability diagrams, (4) accuracy-at-coverage curves, (5) accuracy by tier/domain/length/format, (6) agreement heatmap.
- Stats: paired bootstrap 95% CIs for accuracy deltas, McNemar for noul/choice wins, Wilcoxon for latency; report n everywhere; call out where N is too small to conclude (esp. OOS slice).
- **Plain-language rule (for non-statisticians): every number in the final report gets a one-sentence translation — see Appendix A. No naked statistics. Verdicts use only: `clear win` / `roughly tied` / `too close to call (need more data)`.**
- Recommendation format: "use X when ___, Y when ___" + threshold suggestions per SUT (e.g., auto-act if conf≥τ) + migration note (Clef is Jev-API-compatible per Cloudflare — confirm field-for-field in pilot).
- Artifacts: `results/*.jsonl`, `results/summary.md`, figures, `EXPERIMENT.md` (this file) + dataset SHA. Repro: seed, package versions, model strings returned by APIs (`data.get("model")`), dates.

## 8. Risks / threats to validity

- Cloudflare's published wins are self-run, unreproduced; our N=300 is directionally useful, not a leaderboard.
- OpenAI Decisions billing may differ from chat-token list prices — measured `usage` + dashboard decides.
- Clef flash pricing ambiguous ($0.09 vs $0.24) — pilot resolves; analysis uses measured $.
- Truncation (~2k tokens) and image billing could surprise — long-state slice + no images in v1 contains this.
- Gold labels are ours (bias) — mitigate with tier tags, paraphrases, and reporting per-tier rather than single accuracy.
- Time-of-day / noisy-neighbor latency — mitigate with round-robin + repeats.
- **Cloudflare free tier: 10k neurons/day quota (HTTP 429, code 4006). Hit at the tail of the full run (5/1200 calls failed).
  Repeats/batching probes must run after daily reset; paid plan removes the cap. Counts as an operational finding, not just a hiccup.**
- **OOS accuracy is misleading by design: gold labels there are best-fit, so "100% OOS accuracy" means the model confidently
  classified nonsense. Judge OOS rows by abstention rate (conf<0.6), not accuracy.**

## 9. Next steps (need approval)

- [ ] Approve N=300 + slices, or cut to N=150 if labeling bandwidth is short (still fine on budget; wider CIs).
- [ ] Approve domains (drop/swap any) + OOS share (10–15%).
- [ ] Confirm flash pricing source of truth (billing dashboard vs docs).
- [ ] Green-light Phase 1: freeze `data/gold.v1.jsonl` (20-state pilot subset first), then build runner (no analysis code until pilot validates `usage`/schemas).

## Appendix A. Plain-language guide (how to read the final report)

Audience: smart colleagues, no stats background. Rule: each metric is reported as
**number + "what this means in one sentence" + verdict**. Template:

> **Metric = X.** In plain English: … . Verdict: clear win / roughly tied / too close to call.

### A.1 Correctness — "did it get the right answer?"

| Metric | In plain English | How to read it | Example sentence |
|--------|------------------|----------------|------------------|
| Accuracy (% correct) | Out of 100 cases, how many it got right. | Higher = better. 90% beats 80%. | "Jev got 86/100 right, Clef got 81/100 — Jev is slightly ahead." |
| F1 / macro-F1 | Accuracy adjusted for cheating: a model that always answers "billing" gets punished. Macro-F1 averages fairly across rare and common classes. | Higher = better. Use when classes are imbalanced. | "Both are ~85% accurate, but flash has lower macro-F1 — it ignores the rare 'sales' class." |
| Precision / recall (per class) | Precision: "when it says X, how often is it right?" Recall: "of all real X cases, how many did it catch?" | Higher = better. Low recall = misses cases; low precision = false alarms. | "Clef catches 95% of urgent tickets (recall) but cries wolf 20% of the time (precision)." |
| AUC (noul only) | If you ranked all cases by the model's urgency score, how well urgent floats to the top. 50% = coin flip, 100% = perfect ranking. | Higher = better, independent of threshold. | "AUC 0.92 means the urgency score ranks well — you can tune the threshold safely." |
| MAE (score questions) | On average, how many levels off was it? MAE 0.3 = usually right, sometimes 1 level off. | Lower = better. | "MAE 0.4 means typically less than half a severity level off." |
| Within-±1 accuracy | How often was it exactly right or just one level off. | Higher = better. Forgiving metric for 4-level scales. | "99% within-1 means it almost never jumps from 'minor' to 'critical'." |
| Kappa / Spearman (score) | Did it get the *ordering* right beyond luck (kappa) and does higher model score track higher true severity (Spearman). | Higher = better. Near 0 = no signal. | "High Spearman means when the model says 'more severe', it's usually right." |

### A.2 Confidence — "can you trust the number it gives you?"

| Metric | In plain English | How to read it | Example sentence |
|--------|------------------|----------------|------------------|
| Calibration / ECE | When it says "90% sure" on 100 cases, is it right ~90 times? ECE = average gap. ECE 2% = well calibrated; 15% = lying to you. | Lower = better. | "ECE 3% means you can take its 90% at face value; ECE 15% means don't." |
| Brier score | One number combining "was it right?" + "was it honest about doubt?" | Lower = better. | "Lower Brier = fewer confident mistakes." |
| Reliability diagram | Plot of "said X% sure" (x-axis) vs "actually right Y% of the time" (y-axis). Perfect = diagonal. Dots above diagonal = under-confident; below = overconfident. | Look for closeness to diagonal. | "Clef's dots sit below the line at the right — when it says 95%, believe ~80%." |
| Overconfidence rate (% conf≥0.9 & wrong) | How often it says "I'm certain" and is wrong. The dangerous mistake. | Lower = better. | "2% vs 9% confident-but-wrong — that's the difference between safe auto-act and needing human review." |
| Mean confidence correct vs incorrect | Average confidence on right answers vs wrong ones. Good models are humble when wrong. | Big gap = good (e.g., 0.92 vs 0.61). Small gap = can't tell. | "Jev averages 0.90 when right, 0.62 when wrong — its doubt means something." |

### A.3 Selective prediction — "how much can we automate?"

| Metric | In plain English | How to read it | Example sentence |
|--------|------------------|----------------|------------------|
| Accuracy-at-coverage (e.g., 80%) | "If we auto-act on the 80% most confident cases and send the rest to a human, how accurate is the auto part?" | Higher = better. Report at 80% + curve. | "At 80% automation, Jev's auto-decisions are 96% right; flash is 91% right." |
| Coverage at 95% accuracy | "How much can we automate while staying 95% accurate?" | Higher coverage = better. | "Clef can automate 70% of tickets at 95% accuracy; Luna only 45%." |

### A.4 Speed, cost, stability — "what does it cost to run?"

| Metric | In plain English | How to read it | Example sentence |
|--------|------------------|----------------|------------------|
| p50 / median latency | The typical wait. Half of calls are faster, half slower. | Lower = better. | "Typical answer in 210ms — fast enough for a live UI." |
| p95 latency | The bad-day wait: 95 of 100 calls are faster than this. What your timeout/SLA must cover. | Lower + close to p50 = predictable. | "p95 of 900ms means 1 in 20 users waits almost a second." |
| Cost per 1k decisions | Dollars to answer 1,000 cases (3 questions each). | Lower = better. | "$0.07 per 1k means 100k tickets cost ~$7 in model fees." |
| Cost per correct decision | Dollars per *right* answer. A cheap-but-wrong model loses here. | Lower = better. This picks the value winner. | "Flash is cheapest per call but needs more human fixes — Jev is cheapest per correct call." |
| Flip rate (paraphrase/repeat) | If we reword the same ticket (or ask twice), how often does the answer change? | Lower = better. High = moody. | "8% flip rate means 8 in 100 reworded tickets get a different team." |
| Agreement / Cohen's κ | How often two models give the same answer (κ corrects for chance agreement). | High = interchangeable; low = they make different mistakes. | "Jev and Clef agree 88% of the time — swapping them rarely changes outcomes." |

### A.5 "Is the difference real?" — stats, translated

We only have ~300 cases, so small gaps could be luck. Three checks, each reported in English:

- **Bootstrap 95% CI (accuracy gaps):** "We re-shuffled the results 10,000 times. Jev beats Clef by 2–8 points in 95% of shuffles." If the range crosses 0 (e.g., −2 to +5), verdict = **too close to call**.
- **McNemar (yes/no, routing wins):** "Counting only cases where they disagreed: Jev was right on 25, Clef on 12 — that's a real edge, not luck (p≈0.03)." If split ~15 vs 13 → **roughly tied**.
- **Wilcoxon (latency):** "Comparing the same ticket head-to-head, flash was faster on 280/300 tickets — clearly faster." Reports median gap in ms, not just p-values.

Reporting rule: always show **n** ("based on 300 cases"), never claim a winner when CIs overlap zero, and downgrade small-slice claims (e.g., OOS n≈40) to "suggestive, needs more data."

### A.6 Example verdict box (what the final report will look like)

> **Routing (choice), n=300.** Jev 86% correct, Clef 84%, flash 78%, Luna 82%.
> In plain English: Jev and Clef are neck-and-neck; flash trails by ~8 points (about 24 extra mistakes per 300 tickets).
> Luck check: Jev-vs-Clef gap (−1 to +5) crosses zero → **roughly tied**. Flash-vs-Clef gap (−10 to −3) doesn't → **clear loss for flash**.
> Money: $0.017 vs $0.096 per 1k — Jev is ~5× cheaper per call *and* more accurate → **Jev is the value winner for routing**.
> Trust: when Jev says ≥90%, it's right 91% of the time; flash only 78% → **only Jev can auto-route at 90%+ threshold**.
