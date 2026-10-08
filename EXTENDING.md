# Extending the benchmark

Goal: enough cases to settle the Jev vs OpenAI comparison (2-point gap, p=0.068 at n=300).

| Target | Cases total | New cases needed | Est. cost (4 models) | Est. wall time |
|---|---|---|---|---|
| Confirm the 2-pt gap if it holds | ~400 | ~100 | $0.05 | ~10 min |
| Properly powered for a 2-pt gap (80%) | ~650 | ~350 | $0.15 | ~35 min |
| Detect a 1-pt gap (Clef vs Jev) | ~2,700 | ~2,400 | $1.05 | ~4 h |

**Decide the number before you run, and run all of it.** Stopping as soon as a p-value crosses 0.05 inflates false positives. Pick 350 and commit.

## 1. Write new cases (the part that matters)

The current 300 cases come from templates in `data/build_gold.py`: a handful of sentence patterns with numbers swapped in. Adding more rows from the same templates adds almost no information, because the models already saw every pattern. New cases must be genuinely new text.

Best sources, in order:
1. Real tickets, invoices, alerts and chat messages, anonymized.
2. Hand-written cases by someone who did not see the results.
3. Templates, only as a last resort and only with new patterns.

Rules:
- **Same question templates.** Reuse the five in `data/questions.v1.json` unchanged. New wording would make old and new results incomparable.
- **Label before running.** Write the gold label and tier (`clear`, `borderline`, `ambiguous`, `oos`) first. Never look at model output while labeling.
- **Keep the domain mix** roughly as now: support 55, invoice 45, security 45, toolcall 40, guardrail 30 per 215 unique. Mixed-signal cases go in `guardrail` with tier `ambiguous`.
- **Second labeler on borderline cases.** Disagreements keep majority gold and the `borderline` tag.
- **Unique ids** with a new prefix so they never collide: `support-v2-001`, `invoice-v2-001`, and so on.
- **Variants (optional).** The analysis computes paraphrase flips from `paraphrase_of`. Add `-para` rows for about 15% of new cases, same gold, `format_variant: "paraphrase"`.

Row format (one JSON object per line):

```json
{"id": "support-v2-001", "domain": "support", "tier": "borderline",
 "state": "<the text>", "questions_template": "support",
 "questions": { ...copy of data/questions.v1.json["support"]... },
 "gold": {"is_urgent": 1.0, "team": "billing", "frustration": 1},
 "paraphrase_of": null, "format_variant": "text"}
```

Gold types: `noul` is `0.0`/`1.0`, `choice` is the option key, `score` is the 0-based index into `criteria`. Out-of-scope rows add `"_abstain_expected": true` to gold.

Save as `data/gold.v2.jsonl` containing **only the new rows**. Leave `gold.v1.jsonl` untouched.

Sanity check before spending anything:

```sh
python3 -c "
import json,collections
rows=[json.loads(l) for l in open('data/gold.v2.jsonl')]
ids=[r['id'] for r in rows]; assert len(ids)==len(set(ids)), 'duplicate ids'
old={json.loads(l)['id'] for l in open('data/gold.v1.jsonl')}; assert not old & set(ids), 'id collision with v1'
q=json.load(open('data/questions.v1.json'))
for r in rows: assert r['questions']==q[r['questions_template']], r['id']
print(len(rows), collections.Counter((r['domain'],r['tier']) for r in rows))"
```

## 2. Run

Credentials in `.env`: `JEV_API_KEY`, `OPENAI_API_KEY`, `CLOUDFLARE_AUTH_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.

Smoke test first (5 cases, 20 calls, checks auth and schemas):

```sh
python benchmark.py --gold data/gold.v2.jsonl --limit 5 --out results/smoke-v2.jsonl
```

Full run. `--limit` must cover every row; the runner goes case by case, all four models per case, 1 call per second:

```sh
python benchmark.py --gold data/gold.v2.jsonl --limit 1000 --out results/full-v3-new.jsonl
```

If any row has `"error"` set, re-run just those pairs:

```sh
python3 -c "import json; print(' '.join(f\"{r['state_id']}:{r['provider']}\" for r in map(json.loads, open('results/full-v3-new.jsonl')) if r['error']))"
```

`backfill.py` is hard-wired to `full.jsonl`; for a v2 run either edit its two file paths or rerun the failed ids with `--ids-file`.

## 3. Analyze

`analyze.py` reads one file, so concatenate old and new:

```sh
cat results/full-v2.jsonl results/full-v3-new.jsonl > results/full-v3.jsonl
python analyze.py results/full-v3.jsonl --out results/full-v3-summary
```

Then check three things in `results/full-v3-summary.md`:
- **Pairs:** does the `jev_vs_openai` 95% range still cross zero?
- **Error rate** is 0% for every model.
- **Per-domain accuracy** of the new rows alone is in the same ballpark as v2. Run `analyze.py` on `full-v3-new.jsonl` by itself; if one model drops 10 points on new cases only, the new cases differ in kind, which is a finding in itself but should be reported as its own slice.

Optional, cheap: repeat the determinism and batching probes on 30 new cases using the existing `--repeat 3` and `batching.py`, so the stability claims cover the new material too.

## 4. Report

Update `index.html` from the new summary. Every number on the page comes from `*-summary.json` and `probes-*.md`; nothing is computed in the page. Report the combined n everywhere and keep the three verdict labels: real gap, too close to call, suggestive (small slice).
