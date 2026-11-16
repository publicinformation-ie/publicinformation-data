# Gating harness

Tries competing fixes for gated or high-error FOI files, on cached bytes only, and picks a winner. It never runs pipeline steps or writes under `steps/`. How to run a round: [PLAYBOOK.md](PLAYBOOK.md). Design: `docs/superpowers/specs/2026-11-15-foi-gating-resolution-strategy-design.md`. Run everything from `pipelines/foi_pipeline`.

| file | does |
|---|---|
| `paths.py` | constants, cached PDF lookup (`pdf_bytes`), loaders |
| `scope.py` | per-file stats, scope set, fault proposal |
| `ledger.py` | builds `ledger.json` and `LEDGER.md`; `set_state` writes `ledger_state.json` |
| `downstream.py` | real step chain on in-memory items; reproduction check |
| `fixes.py` | `Fix`, `register`, built-ins (`current`, `force:<name>`, `docling`) |
| `extract_cache.py` | extraction cache per (fix, content sha), in `cache/` |
| `run_docling.py` | docling runner (the only file importing docling) |
| `compare.py` | agreement, gold scoring, `--calibrate` |
| `round.py` | runs a round, score table, winner rule, control picker |
| `gold_tools.py` | page images, gold from bounds, cells to check, gold status |
| `review_page.py` | static HTML for a round |
| `serve.py` | stdlib LAN server, saves verdicts |
| `settings.json` | `agreement_min` 0.90, `gold_min` 0.95 |
| `docling_pages/`, `ledger_state.json`, `ledger.json`, `LEDGER.md`, `controls.json` | kept in git |
| `cache/`, `scratch/` | gitignored |

Commands:

```
uv run python -m experiments.gating.ledger
uv run python -m experiments.gating.downstream --urls-file F
uv run --with docling python experiments/gating/run_docling.py --urls-file F
uv run python -m experiments.gating.compare --calibrate
uv run python -m experiments.gating.round --round-dir D --cluster ID --fixes current,docling
uv run python -m experiments.gating.gold_tools render --url U --out DIR
uv run python -m experiments.gating.gold_tools build --url U --bounds B.json   # overwrites gold
uv run python -m experiments.gating.serve --round-dir D                        # only when the user says so
```

`--calibrate` and the round CLI need the real caches. The server listens on the LAN. Tests: `uv run pytest tests/experiments -q`.
