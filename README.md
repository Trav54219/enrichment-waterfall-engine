# enrichment-waterfall-engine

A small Python engine that fills lead fields (email, phone, title, company size, tech stack) by trying providers in cost order, with fallbacks, the way a Clay-style enrichment waterfall works.

**Read this first**
- All providers are **deterministic mocks**. No API calls, no keys, no network.
- All data is **synthetic** (invented names, `.example` domains).
- **Nothing is connected to Clay or any vendor.** Provider names and prices are made up. Costs are in abstract "credits".
- Numbers below come from running this repo's code on the synthetic list. They show how the engine behaves, not how any real vendor performs.

## What it does
- **Waterfall per field**: ordered `Step(provider, when=...)` lists; the first result at or above the confidence threshold stops the chain (early stop), otherwise the best result seen is kept.
- **Per-field confidence**, provider attribution, and a trace of every step tried.
- **Conditional branching**: a step can require a predicate, e.g. run the premium provider only if earlier ones came up empty and the row is ICP-fit (size band + GTM function), or run phone only after an email was found.
- **Cost accounting**: cost per filled field, per row, per ordering. Providers charge only on a hit.
- **Budget caps**: per-row and total; a step that could exceed the cap is skipped and logged.
- **Retries** on transient provider errors (failed attempts are never charged; a given-up call is not cached).
- **Cache + idempotency keys**: key = hash(provider, field, entity). Misses are cached too. Company-level fields (size, tech) are keyed by domain, so five people at one company cost one lookup. Cache can persist to JSON, so re-running a list costs 0.
- **Normalization and dedupe**: domains (`https://WWW.Acme.com/x` to `acme.com`), names (`SMITH, jane` to `Jane Smith`), titles to seniority and function (`Sr. VP of Sales` to `vp` / `sales`). Duplicates collapse on domain + name.
- **CSV export** and a **markdown cost/coverage report** comparing orderings.

## Run
```
python3 -m pytest -q
python3 -m waterfall.cli --n 300 --seed 7 --out out
```
Outputs `out/enriched_<ordering>.csv` and `out/report.md` (committed sample from the run below).

## Result on the synthetic list (300 leads + injected duplicates, seed 7)
| ordering | rows | total cost | cost/row | cost/filled field | fields filled |
|---|---|---|---|---|---|
| cheap_first | 295 | 238.80 | 0.8095 | 0.1724 | 1385 |
| premium_first | 295 | 313.69 | 1.0634 | 0.2265 | 1385 |
| conditional_icp | 295 | 96.35 | 0.3266 | 0.0836 | 1153 |

- `cheap_first` and `premium_first` reach the same fill rate; cheap-first is about 24% cheaper but its filled values have lower average confidence (email 0.878 vs 0.934), because it stops at the first value over 0.8.
- `conditional_icp` is cheapest per field but fills less (email 77%, phone 24% vs 98% / 79%) because non-ICP rows deliberately skip paid tiers. That is a coverage-for-cost trade, not a free win.
- With these mock hit rates and prices only. Change `providers.py` to model your own.

## Layout
`waterfall/normalize.py` normalization, `providers.py` mocks, `engine.py` waterfall, `plans.py` orderings, `synth.py` synthetic leads, `report.py` CSV and report, `cli.py` runner, `tests/` pytest suite.
