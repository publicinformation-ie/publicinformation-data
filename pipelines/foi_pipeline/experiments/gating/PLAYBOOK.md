# Gating playbook

Read this before running a round. All commands run from `pipelines/foi_pipeline` (FOI).

## 1. What this is

- Some FOI files are gated (`table_structure_unreliable`) or lose many rows to errors. We want to fix them without breaking files that work today.
- Work goes in rounds, one cluster of similar files per round.
- Each round tries two to four competing fixes on the cluster, on about 10 controls and on the gold files, all from cached bytes.
- A scoring table picks a winner. The user decides whether anything ships.
- Nothing in this package changes pipeline code or `steps/`.

Definitions:

- **Scope set**: files that are gated, or have `errors / (records + errors) >= 0.2` (errors counted from `extract_disclosures_canonicalize_rows/errors.json`). The ledger prints the real number.
- **Fault kinds**: `E` extractor made a wrong grid. `M` mapping assigns roles wrongly. `G` gate or scorer is wrong. `S` source has nothing to extract (parked). `V` vocabulary: the table is fine but the errors are unknown or variant values (a non-goal, parked automatically). A kind is a proposal until the user has looked at the cluster's representative file (`fault_firm`).
- **Cluster**: files with the same fault kind and a likely single fix, usually same body and template. Cluster id example: `1594-non-personal-2017-2020`.
- **Resolved** (all three, for the winning fix): the output passes the gate; cell agreement is at least 0.90 with an independent extractor family; the cluster's gold file scores at least 0.95. A file whose result is `override_bound` (an index-keyed `column_mapping` override meeting a different extractor's grid) is never counted resolved automatically. Agreement `None` (tables cannot be aligned) never counts as resolved and never as a control made worse. Thresholds live in `settings.json`.
- **Controls**: about 10 files published with 0 errors today, spread over the current extractors (`controls.json`). A fix that makes a control worse is disqualified. The 10 existing gold files are also run every round, for scoring.

## 2. Hard rules

- Never run `transform_disclosure_files` or any `process.py` run. The harness calls step functions on in-memory items only.
- Never run `extract_motions` (paid).
- Never write, move or delete anything under `steps/`. Scratch output goes to `experiments/gating/scratch/` (gitignored).
- No network, except `uv run --with docling` (package and weights). No paid OCR: `mistral_cache` reads the cache only.
- No change to pipeline code, `column_mappings.json`, thresholds or `CANDIDATE_ORDER` from a round.
- Gate values stay `max_role_contamination = 0.2`, `min_anchored_row_share = 0.8`.
- Do not stage `steps/transform_disclosure_files/output.json` if it shows as modified. Stage by explicit path.
- Nothing ships without the user's yes for that cluster.
- Fork repos, pushes and upstream PRs need the user's yes.
- Changing `settings.json` or fetching missing PDFs needs the user's yes.
- Hand back to the main (Opus) session, without improvising, if a step function needs a pipeline code change to be callable, or any result contradicts the diagnosis.
- `--calibrate` and the round CLI need the real caches (PDF bytes in `steps/verify_disclosure_files/cache/`, OCR in `steps/transform_disclosure_files/ocr_cache/`). They do not work in CI or without them.

## 3. The round, step by step

1. **Refresh the ledger.** `uv run python -m experiments.gating.ledger` (no flags). It rewrites `ledger.json` and `LEDGER.md`, and prints gated count, scope size, counts by kind and the `no_bytes` count. Manual state lives in `ledger_state.json`; never edit the generated files.
2. **Pick a cluster.** Read `LEDGER.md`: the open cluster with the most recoverable records for the least effort. Mark its files:
   `uv run python -c "from experiments.gating.ledger import set_state; set_state([<file_urls>], status='in_round')"`
   `set_state(file_urls, state_path=STATE_PATH, **fields)`; fields are `fault_kind` (E M G S V), `fault_firm`, `cluster`, `status` (`open in_round resolved parked no_bytes`), `note`.
3. **Make the round folder** `experiments/YYYY-MM-DD-gating-round-NN-<slug>/` (under FOI).
4. **Write the hypothesis** in its `README.md`: one paragraph naming the fault kind, from the page image (`gold_tools render`) and each extractor's output. Then list the fixes, `current` first always, docling for `E` clusters.
5. **Optional `fixes.py`** in the round folder, loaded with `--fixes-module` (or automatically by `review_page.build`). See section 4.
6. **Docling pass** for the cluster, controls and gold files not yet in `docling_pages/` (5 to 60 s each, so a first pass of 25 files can take 25 minutes). The URLs file has one file URL per line:
   `uv run --with docling python experiments/gating/run_docling.py --urls-file urls.txt`
   `--seed-from-bakeoff` (no docling needed) seeds from the bake-off results. Output is `docling_pages/<content-sha>.json`, kept in git.
7. **Run the round.**
   `uv run python -m experiments.gating.round --round-dir experiments/<round folder> --cluster <cluster-id> --fixes current,force:pdfplumber,docling [--fixes-module experiments/<round folder>/fixes.py] [--cluster-gold <sha>]`
   It reads cluster files from `ledger.json`, controls from `controls.json`, and gold files from the bake-off sample. It writes `results.json` and `TABLE.md` in the round folder and prints the winner. Per file status is recorded (`no_table`, `error`, `not_extracted`) and the round carries on; the fix row shows the counts. No file should stay `not_extracted` once docling has run.
8. **Gold** for one representative file (the sha is the content sha, shown in the ledger):
   - Render pages: `uv run python -m experiments.gating.gold_tools render --url <file_url> --out <dir> [--dpi 110]`. Prints the image paths.
   - Draft bounds (see the Haiku prompt in section 5) into a `bounds.json`:
     `{"dpi": 110, "columns": ["col a", ...], "pages": [{"page": 1, "x": [x0, x1, ...], "y": [y0, y1, ...], "skip_rows": [0]}]}`. `x` and `y` are pixel lines at that dpi; `skip_rows` are row indexes (header rows) to leave out. The text comes only from the PDF text layer.
   - Build: `uv run python -m experiments.gating.gold_tools build --url <file_url> --bounds bounds.json`. It writes `<bakeoff>/gold/<content-sha>.json` and marks it `provisional` in `gold_status.json`. It also writes cell positions to `gating/gold_cells/<content-sha>.json` (used by the review page crops). **It refuses (FileExistsError) if the gold file already exists; `--force` overwrites it and resets it to `provisional`. Never use `--force` on a sha that already has a checked gold file without the user's say-so.**
   - Cells to check: `gold_tools.cells_to_check(gold, fix_rows, n_random=10, seed="")` returns the cells where gold and the extractors disagree plus 10 random cells. The review page does this for you.
   - Rerun step 7 with `--cluster-gold <sha>`.
9. **Build the review page.**
   `uv run python -c "from pathlib import Path; from experiments.gating import review_page as r; print(r.build(Path('<round dir>'), representative_url='<url>', cluster_gold_sha='<sha>'))"`
   `build(round_dir, representative_url=None, cluster_gold_sha=None)` needs `results.json` and writes `review/` (also `gold.html` when a gold sha is given).
10. **Serve, only when the user says so.** Tell the user the page is ready and what it asks: the fault name for the representative, the disputed and random gold cells, ship yes or no.
    `uv run python -m experiments.gating.serve --round-dir <round dir> [--host H] [--port 8765]`
    - It listens on the LAN by default (the machine's LAN address, port 8765). Give the user the URL it prints.
    - `POST /verdict` needs `Content-Type: application/json` and a body `{"key", "text", "tags"}`. A mismatched `Origin` gets 403. Paths outside the round get 404.
    - Verdicts are saved to `<round dir>/verdicts.json` as `{key: {text, tags, saved_at}}`. The ship answer is under key `__ship__`.
    - Stop it when the user is done.
11. **Read `verdicts.json`.** Apply gold corrections to the gold file, then `gold_tools.mark_gold_checked(sha)` (sets `checked` in `gold_status.json`), then rerun step 7. If the user's fault name differs from the hypothesis, the user's reading wins: revise the fixes and rerun once.
12. **Record the decision** in the round README: the table, the winner, records recoverable (a number), controls made worse for the winner (must be 0 for a global fix; compare with `experiments/2026-11-14-pdf-extractor-bakeoff/before_after.py`), and the recommendation. A docling, fork or gate win is a recommendation only (section 6).
13. **Update the ledger.** `set_state(file_urls, fault_kind='E', fault_firm=True, status='open', note='<round folder>')` (status `resolved` only after something ships, `parked` per the stop rules). Then run step 1 again to rebuild.
14. **Index row** in `experiments/README.md`, then commit with explicit paths.

To check the stored outputs can be reproduced for a set of files (step functions on in-memory items): `uv run python -m experiments.gating.downstream --urls-file urls.txt [--steps-dir D] [--config-dir D] [--variant V]`. It reports mismatches; expect none.

`uv run python -m experiments.gating.compare --calibrate` runs every fix on the gold files and writes `calibration.md` with a suggested agreement threshold. Round 0 only. A change to 0.90 needs the user's yes.

## 4. Writing a fix

A `Fix` is `Fix(name, kind, extract=None, rows_from=None, family=None, gate=None, scope="routed", base="current", version="1")`. `kind` is one of `baseline config params candidate wrapper fork gate` (cheapest first, the winner rule breaks ties in that order). `extract(data: bytes, url: str)` returns a list of rows, or `None` for no table. Register it with `register(Fix(...))`; names must be unique. Raise `fixes.NotExtracted` if the output has not been produced yet. Put round fixes in the round's `fixes.py`; no change to `src/lib` or `steps/`.

Header of a round `fixes.py`:

```python
from experiments.gating.fixes import Fix, register
from steps.transform_disclosure_files import candidates
```

- **config** (route an existing extractor): built in as `force:<name>` for every candidate name, e.g. `--fixes current,force:pdfplumber`. Nothing to write.
- **params** (extractor settings):
  ```python
  def _snap8(data, url):
      c = candidates._pdfplumber("pdfplumber_snap8", data, {"snap_tolerance": 8})
      return c.rows if c else None
  register(Fix(name="pdfplumber-snap8", kind="params", extract=_snap8, family="pdfplumber"))
  ```
- **candidate** (a new extractor): `docling` is the built-in one (reads `docling_pages/`). A new one is an `extract` that reads or computes rows from `data`, with its own `family`:
  ```python
  register(Fix(name="mycand", kind="candidate", extract=_my_extract, family="mycand"))
  ```
- **wrapper** (a change on top of a library, in this repo): same shape, `extract` calls the library and fixes the grid, for example merges split columns:
  ```python
  def _merged(data, url):
      c = candidates._pdfplumber("pdfplumber", data, {})
      return merge_split_cols(c.rows) if c else None
  register(Fix(name="pdfplumber+merge-cols", kind="wrapper", extract=_merged, family="pdfplumber"))
  ```
- **fork** (patched library): name it `<library>+<patch-slug>`. First try parameters, then a wrapper. Only then: save a minimal reproduction in the round folder, check upstream issues for an existing fix, patch, pin the fork by commit in an optional dependency group. It must beat the unpatched library on gold with zero controls made worse. Whether to offer the patch upstream is the user's call.
  ```python
  register(Fix(name="pdfplumber+join-words", kind="fork", extract=_forked, family="pdfplumber"))
  ```
- **gate** (the scorer is wrong, hypothesis only): reuse the current extraction and swap the gate. `gate` is a `Gate`: `(rows, role_map_or_None) -> (StructureScore, failed_checks)`, kept in the round folder.
  ```python
  register(Fix(name="gate-dates", kind="gate", rows_from="current", gate=my_gate, scope="global"))
  ```
  A gate fix changes the answer for every file, so `scope="global"` is required in practice, and it needs a full before/after over all bodies.

## 5. Model direction

| model | does | does not |
|---|---|---|
| Opus (main session) | reviews clusters, diagnosis, picks the fixes to compete, reads library source and writes patches, reads the table, ship recommendation | bulk file reading, running rounds |
| Sonnet (subagent) | maintains the harness, implements a fix as a candidate, runs a round, writes routing and tests when shipping | decides which fixes to try, decides to ship |
| Haiku (subagent) | drafts gold bounds from page images, tallies, ledger updates, link and file checks | anything where a wrong answer is not caught by a later check |

Rules: every prompt is self-contained. Sonnet hands back to Opus when a result contradicts the diagnosis. Haiku output is always checked by a score or by the user. No model runs paid OCR or ships without the user's yes.

### Prompt: Sonnet, run a round

```
Run gating round NN for cluster <cluster-id>. Work in /Volumes/ext/dev/publicinformation/publicinformation-data/pipelines/foi_pipeline. Read experiments/gating/PLAYBOOK.md sections 1 to 3 first.
Round folder: experiments/<YYYY-MM-DD>-gating-round-NN-<slug>/ (its README.md has the hypothesis).
Fixes to run: <comma list, e.g. current,force:pdfplumber,docling>. Round fixes module (if any): <round folder>/fixes.py. Cluster gold sha (if any): <sha>.
Definitions. Resolved: the file passes the gate, agrees at 0.90 or more with an independent extractor family, and the cluster gold scores 0.95 or more. Controls: the files in experiments/gating/controls.json; a fix that makes any worse is disqualified.
Steps: if docling output is missing for the cluster, controls or gold files, run docling for them (uv run --with docling python experiments/gating/run_docling.py --urls-file F). Then run:
uv run python -m experiments.gating.round --round-dir <round folder> --cluster <cluster-id> --fixes <list> [--fixes-module ...] [--cluster-gold <sha>]
Output files: <round folder>/results.json and <round folder>/TABLE.md. No file should be left not_extracted.
Do not run any process.py step or extract_motions, write under steps/, use the network (other than docling) or ship anything. If any result contradicts the diagnosis, stop and report.
Report back in under 200 words: winner, the TABLE.md rows, controls changed, files not resolved and why, anything surprising.
```

### Prompt: Haiku, draft gold bounds

```
Draft gold bounds for the PDF with content sha <sha> (file URL <url>).
Page images (already rendered): <dir>/page-1.png ... Look at each image.
Write <path>/bounds.json with exactly this shape:
{"dpi": 110, "columns": ["<header 1>", ...], "pages": [{"page": 1, "x": [pixel x of each column line, left to right, including both outer edges], "y": [pixel y of each row line, top to bottom, including both outer edges], "skip_rows": [indexes of rows to leave out, such as the header]}]}
Pixels are in the rendered image at that dpi. One entry in "pages" per table page. Give column and row LINES, not cell contents. Do not write any cell text: the text comes only from the PDF text layer and is cut out by the bounds. Do not run gold_tools build. Reply with the file path and a note of any page you were unsure about.
```

### Prompt: Haiku, update the ledger from verdicts

```
Read <round folder>/verdicts.json. Keys are file URLs or other ids; each value has text, tags and saved_at. The key __ship__ is the ship answer.
For each file URL with a verdict, work out the fault kind (E extractor, M mapping, G gate, S source) from the text and tags, or write "unclear". Output a table: file URL, fault kind, one-line reason. Do not edit any file. Reply with the table and the __ship__ text word for word. The caller will run set_state from your table.
```

## 6. Stop rules and shipping

- Park a cluster after two rounds without a winner, or when it needs new code for fewer than about 30 records. Keep the diagnosis in the ledger note.
- Pause the whole strategy when the open files together recover less than about 1% of corpus records. The user decides whether to go on.
- Winner rule: zero controls made worse; then highest gold accuracy; then agreement; then the cheaper fix type.

Shipping (only on the user's yes for that cluster):

- Default: explicit routing per file. The `pdf_extractor` key in `column_mappings.json`, keyed by `file_url` and validated against `CANDIDATE_ORDER`. One generated entry per file. Run the change over every file the routing matches and compare before and after (`experiments/2026-11-14-pdf-extractor-bakeoff/before_after.py --bodies`). Add tests for the routing.
- A docling or fork win cannot ship through config alone, since the override only accepts names in `CANDIDATE_ORDER`. The proposal is to ship it as a cache-backed candidate, as `mistral_cache` works. Until the user confirms that, such a round ends with a recommendation and the measured numbers, not a ship.
- A gate (`G`) fix touches every file, so it always needs a full before/after over all bodies and a control check.
- A change to the global candidate order is only proposed when three or more clusters picked the same extractor and a full-corpus run shows no control made worse.
