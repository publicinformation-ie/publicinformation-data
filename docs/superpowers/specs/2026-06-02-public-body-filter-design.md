# Public Body Filter Feature Design

**Date:** 2026-06-02
**Status:** Implemented
**Spec Location:** `docs/superpowers/specs/2026-06-02-public-body-filter-design.md`

---

## Overview

### Summary

Add a `--public-body <ID>` command-line flag to the FOI pipeline that scopes
processing to a single public body, **without altering the output for any other
public body**. The flag works both at the orchestration level (`process.py`)
and for individual step `process.py` scripts.

This enables developers to:

- Reprocess a single public body after an override/fix, cascading downstream,
  while leaving all other bodies' committed output untouched.
- Test/debug a single step against one body in isolation.
- Iterate in seconds instead of running ~500 bodies through 16 steps.

### Goals

1. Add `--public-body <ID>` to `process.py` orchestration and to individual steps.
2. **Preserve all other bodies' output byte-for-byte** when targeting one body
   (this is the central requirement — see Architecture).
3. Reprocess the targeted body even if it was already processed, and cascade
   that reprocessing downstream — reusing the existing `dirty_ids` mechanism.
4. Maintain the existing output file structure (`results` / `public_bodies`
   array wrappers, `metadata`, `errors.json`, `dirty_ids.json`, status files).
5. Centralize the new CLI/filtering logic in a reusable `scripts/cli_utils.py`.
6. Support incremental migration (one step at a time, backward compatible).

### Non-Goals

1. Changing output file structure/format.
2. Changing pipeline step order or dependencies.
3. Multiple IDs, ranges, or ID files in one run (single integer only).
4. Changing existing flags (`--force`, `--from`, `--verbose`, `--stop-on-error`).
5. Replacing or removing `IncrementalWriter`, `override.json`, or the dirty
   mechanism. The flag is layered **on top of** them.

---

## Background: how the pipeline actually works

This section is the crux. The previous draft of this spec modelled steps as
stateless (`read input → filter → write output`); they are not. Getting this
right is what makes "no effect on other bodies" achievable.

### Orchestration (`process.py`)

- Reads `pipeline.json` (`steps` array) and runs each step's `process.py` in
  order as a subprocess.
- Passes `--input <prev_output>`, `--output <step_output>`, and (conditionally)
  `--force` / `--verbose`.
- Supports `--from STEP` (`dest=from_step`) to resume from a step, and
  `--stop-on-error`.
- Staleness: a step is re-run if its `output.json` is missing or older than the
  previous step's output, unless skipped.
- **`process.py` has no concept of `dirty_ids` today** — propagation happens
  purely through files on disk between steps.

### Steps and `IncrementalWriter` (`scripts/file_utils.py`)

Most processing steps (e.g. `validate_websites`, `get_foi_emails`,
`find_disclosure_*`, `transform_disclosure_files`, `normalize_disclosure_cells`,
`extract_disclosures_*`) use `IncrementalWriter`, which is **merge-based, not
overwrite-based**:

- **Without `force`**: loads existing `output.json` into `self.results`, builds
  `processed_keys` from `public_body_id`. Steps call `writer.is_processed(id)`
  and skip bodies already done. `finalize()` writes existing + newly-appended
  results. → Re-running is cheap and non-destructive.
- **With `force=True`**: starts from an **empty** `results` list and writes only
  what was processed this run. → On a filtered run this would **delete every
  other body** from `output.json`. (This is the bug in the previous draft.)
- **`override.json`**: records injected by `public_body_id`, schema-validated
  against `output_schema.json`; changed overrides mark the body **dirty**.
- **Dirty propagation**: `finalize()` writes `dirty_ids.json` next to the output.
  Downstream steps that pass `upstream_dirty_path = Path(args.input).parent /
  "dirty_ids.json"` call `_evict_upstream_dirty()`, which **removes just those
  bodies from their existing output and reprocesses them**, leaving all other
  bodies intact, then re-emits `dirty_ids.json` to cascade further downstream.

The dirty mechanism is *already* "reprocess a subset, preserve the rest, cascade
downstream." `--public-body` is essentially a CLI-driven entry point into it.

### Three step shapes (this is why one template can't work)

Verified, the active steps fall into **three** classes, and `--public-body`
behaves differently in each:

1. **IncrementalWriter steps** (10): `resolve_website_urls`, `validate_websites`,
   `find_foi_pages`, `check_foi_pages`, `get_foi_emails`, `find_disclosure_pages`,
   `find_disclosure_files`, `transform_disclosure_files`,
   `normalize_disclosure_cells`, `extract_disclosures_detect_header_row`.
   Merge-based; "no effect on other bodies" is achieved via targeted eviction.

2. **Stateless full-rewrite transforms** (plain `write_json` of *all* records):
   `extract_disclosures_canonicalize`, `extract_disclosures_deduplicate`. These
   read `args.input`, transform every record, and overwrite the whole output in
   one shot. **Filtering their input to body 1001 would write an output
   containing only 1001 — wiping the rest.** To honour the no-effect guarantee
   they need a *merge-back* wrapper (read existing output, replace just the
   target body's records, write the union). See Step-Level Changes §(b).

3. **Aggregators that ignore `--input`** and read hard-coded sibling outputs:
   `export_status` (reads `find_public_bodies` + each step's output, also writes
   `public/` files), `generate_topics` (reads
   `extract_disclosures_canonicalize/output.json`, writes a *topics* structure),
   `db_upload` (reads `export_status`, `find_disclosure_files`,
   `extract_disclosures_deduplicate`, `generate_topics`). And
   `find_public_bodies` is a custom scraper (its own shape). For these, scoping
   means filtering the hard-coded reads; output is derived/best-effort. See §(c).

### Top-level key per step (verified)

- `find_public_bodies` → `public_bodies` (custom writer, **not**
  `IncrementalWriter`).
- `export_status` → `public_bodies`.
- All `IncrementalWriter` steps → `results`.

`filter_by_public_body` must therefore handle both keys.

---

## Proposed Design

### Core principle

A `--public-body 1001` run is defined as:

> **Filter the input to body 1001, evict body 1001 (and only 1001) from this
> step's existing output, reprocess it, merge it back, and mark it dirty so
> downstream steps do the same.** Never use `--force` to achieve this.

This keeps every other body's output untouched at every step, and propagates the
single-body reprocessing through the whole chain via the existing `dirty_ids`
cascade.

### Architecture overview

```
process.py --public-body 1001
   │  validate 1001 exists in find_public_bodies/output.json
   ▼
 for each step (respecting --from):
   ├─ pass --public-body 1001  (NOT --force)
   ▼
 step process.py
   ├─ read input
   ├─ filter_by_public_body(input, 1001)      # only 1001 considered
   ├─ IncrementalWriter(..., target_public_body=1001)
   │      → evicts 1001 from existing output (so it WILL be reprocessed)
   │      → keeps all other bodies in self.results
   ├─ process() appends reprocessed 1001
   └─ finalize() writes {others... , 1001}, plus dirty_ids.json=[1001]
```

### Common CLI library — `foi_pipeline/scripts/cli_utils.py`

```python
def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add --input, --output, --force, --verbose, --public-body to a step parser."""
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--public-body", type=int, default=None, dest="public_body",
                        help="Scope processing to this public body ID only")


def filter_by_public_body(data: dict, public_body_id: int | None) -> dict:
    """Return a shallow copy of `data` with its record array filtered to
    public_body_id. Handles both 'results' and 'public_bodies' keys. If
    public_body_id is None, returns `data` unchanged. Other top-level keys
    (e.g. metadata) are preserved."""


def validate_public_body(pipeline_dir: Path, public_body_id: int) -> bool:
    """True if public_body_id is present in find_public_bodies/output.json
    (under the 'public_bodies' key)."""


def merge_replacing_body(existing: list, new: list, public_body_id: int) -> list:
    """For §(b) stateless transforms: return `existing` with all records for
    public_body_id removed, then `new` appended. Preserves every other body."""
```

Notes:
- `add_common_args` defines the *full* common set so steps can drop their
  duplicated `--input/--output/--force/--verbose` blocks. Steps with extra args
  add them after calling `add_common_args`.
- `filter_by_public_body` must not mutate its input and must preserve whichever
  array key is present.

### `IncrementalWriter` change — targeted eviction

Add an optional `target_public_body` (or generalised `evict_keys: set`) argument
that reuses the existing eviction path:

```python
class IncrementalWriter:
    def __init__(self, output_path, step_name, key_field="public_body_id",
                 force=False, override_path=None, upstream_dirty_path=None,
                 target_public_body=None):   # NEW
        ...
        # after loading existing results / processed_keys:
        if target_public_body is not None:
            self._evict_keys({target_public_body})   # same logic as _evict_upstream_dirty
```

`_evict_keys` factors out the body of `_evict_upstream_dirty` (remove from
`results`, drop from `processed_keys`, add to `dirty_body_ids`). The targeted
body is thus guaranteed to be reprocessed this run, and `finalize()` already
writes it into `dirty_ids.json`, so downstream steps cascade for free.

This is preferred over inventing a new "replace filtered keys" path because it
reuses tested logic and the existing dirty cascade.

### Orchestration changes (`process.py`)

```python
parser.add_argument("--public-body", type=int, default=None, dest="public_body",
                    help="Scope all steps to this public body ID only")
```

**Validation** (always possible because `find_public_bodies/output.json`
normally exists and contains every body):

```python
if args.public_body is not None:
    bodies_path = pipeline_dir / "steps" / "find_public_bodies" / "output.json"
    if not bodies_path.exists():
        sys.exit("Error: --public-body requires find_public_bodies/output.json; "
                 "run find_public_bodies first.")
    bodies = read_json(bodies_path).get("public_bodies", [])
    if not any(b.get("public_body_id") == args.public_body for b in bodies):
        sys.exit(f"Error: public body {args.public_body} not found in "
                 f"find_public_bodies/output.json")
```

**Passthrough** — append the flag, and **never force on its behalf**:

```python
if args.public_body is not None:
    cmd += ["--public-body", str(args.public_body)]
```

`--force` is only appended when the user explicitly passes `--force`. Combining
`--public-body` with `--force` is allowed but documented as destructive (see
Error Handling): with `force=True` the writer starts empty and the run will
reduce that step's output to the single body. The flags are orthogonal; we do
not silently inject `--force`.

### Step-level changes

#### §(a) IncrementalWriter steps (the common case)

Insert filtering between read and process, and pass `target_public_body`:

```python
from scripts.cli_utils import add_common_args, filter_by_public_body

def main():
    parser = argparse.ArgumentParser(description="...")
    add_common_args(parser)          # replaces the 4 duplicated add_argument lines
    args = parser.parse_args()

    input_data = read_json(args.input)
    if args.public_body is not None:
        input_data = filter_by_public_body(input_data, args.public_body)
        if not (input_data.get("results") or input_data.get("public_bodies")):
            print(f"No input record for public_body_id={args.public_body}",
                  file=sys.stderr)
            sys.exit(0)

    writer = IncrementalWriter(
        output_path, STEP_NAME,
        force=args.force,
        override_path=override_path,
        upstream_dirty_path=...,                 # unchanged where already present
        target_public_body=args.public_body,     # NEW
    )
    process(input_data, step_dir, writer, verbose=args.verbose)
    writer.finalize()
    write_status(step_dir, ...)
```

The diff per step is genuinely small (swap arg block for `add_common_args`, add
the filter block, add one kwarg) **because we keep `IncrementalWriter`**. We do
NOT introduce a generic stateless template — that would drop resumability,
override support, dirty tracking, `errors.json`, and `write_status`.

#### §(b) Stateless full-rewrite transforms (`canonicalize`, `deduplicate`)

These have no `IncrementalWriter` and no resumability — they overwrite the whole
output. To preserve other bodies when scoped, wrap the write with a merge-back:

```python
results = transform(filter_by_public_body(input_data, args.public_body))  # only 1001

if args.public_body is not None and not args.force and Path(args.output).exists():
    existing = read_json(args.output).get("results", [])
    existing = [r for r in existing if r.get("public_body_id") != args.public_body]
    results = existing + results          # replace just 1001, keep the rest
write_json(args.output, {"metadata": {...}, "results": results})
```

Add a small helper to `cli_utils.py` (e.g. `merge_replacing_body(existing,
new, public_body_id)`) so this is identical across both transform steps and
unit-tested once. Caveat: `deduplicate` may dedupe *across* bodies; if its
semantics aren't per-body-independent, scoping is unsafe and it should warn +
require a full run. Confirm during its migration PR.

#### `find_public_bodies` (custom writer, source of truth)

It does not use `IncrementalWriter` and emits the `public_bodies` key. Behaviour:

- `--public-body 1001` **without** `--force`, output exists → read existing,
  `filter_by_public_body` to 1001, but **write back the full set with only 1001's
  record replaced** is unnecessary here (scraped data is static); instead, when
  scoping, leave `output.json` untouched and simply confirm 1001 exists. The
  downstream steps do the actual per-body work. (Rationale: rewriting
  find_public_bodies to a single body would violate Goal 2 for this file.)
- `--public-body 1001` with `--force` → re-scrape all, keep all, then proceed.
  We do not reduce the file to one body.
- If 1001 absent → error, exit 1.

This is a deliberate change from the previous draft, which proposed shrinking
`find_public_bodies/output.json` to one body — that violated the "no effect on
other bodies" requirement at the source.

#### §(c) Aggregators: `export_status`, `generate_topics`, `db_upload`

- `export_status`: aggregates `find_public_bodies` + each step's output and also
  writes `public/` files. When scoped, filter each read by `public_body_id`; but
  because it regenerates published artifacts, treat scoped output as
  derived/best-effort and document that a full run is needed before publish.
- `generate_topics`: when `--public-body` is set, filter the hard-coded read of
  `extract_disclosures_canonicalize/output.json` before computing topics. Output
  is a topics structure, so "no effect on other bodies" is best-effort; document
  that topic outputs are derived and should be regenerated fully before publish.
- `db_upload`: `--public-body` filters each hard-coded read by `public_body_id`
  so only that body is upserted. Must use idempotent upsert (verify current
  behaviour); otherwise emit an info message and skip when scoped.

---

## Data Model

Output structure is unchanged. Filtering and eviction only change *which*
records appear, and the targeted body is the only one that changes between runs.

```jsonc
// before: results = [1001, 1002, 1003]
// run with --public-body 1002 (no --force):
//   - 1001, 1003 preserved exactly (untouched)
//   - 1002 evicted, reprocessed, merged back
//   - dirty_ids.json = [1002]
// after:  results = [1001, 1003, 1002]  (order may differ; 1001/1003 unchanged)
```

`filter_by_public_body` examples:

```python
filter_by_public_body({"results": [{"public_body_id":1001},{"public_body_id":1002}]}, 1001)
# -> {"results": [{"public_body_id":1001}]}   (+ any metadata preserved)

filter_by_public_body({"public_bodies": [...]}, 1001)   # same, public_bodies key
filter_by_public_body(data, None)                       # -> data unchanged
filter_by_public_body({"results":[{"public_body_id":1001}]}, 9999)  # -> {"results":[]}
```

---

## Error Handling

| Scenario | Behavior | Exit |
|----------|----------|------|
| `--public-body` non-integer | argparse error | 2 |
| Body not in `find_public_bodies/output.json` | stderr error | 1 |
| `find_public_bodies/output.json` missing | stderr error, ask to run it first | 1 |
| Filtered input has no record for the body (step level) | stderr info, clean exit | 0 |
| `generate_topics`/`db_upload` scoped | filter hard-coded reads; info if not filterable | 0 |
| `--public-body` **with** `--force` | allowed but **reduces that step's output to the single body**; warn on stderr | 0 |

The `--force` + `--public-body` warning is important: the two are orthogonal,
and the destructive interaction must be surfaced, not hidden.

---

## Testing Strategy

### Unit tests — `foi_pipeline/tests/test_cli_utils.py`

- `filter_by_public_body`: results key, public_bodies key, `None` passthrough,
  no-match empty, metadata preserved, input not mutated.
- `validate_public_body`: present / absent / missing-file.
- `merge_replacing_body`: target removed from existing then new appended; other
  bodies preserved exactly; empty `existing`; empty `new`.

### Unit tests — `IncrementalWriter` (extend existing writer tests)

- `target_public_body` evicts only that key from existing results, preserves the
  rest, adds it to `dirty_body_ids`, and `finalize()` writes it to
  `dirty_ids.json`.
- `target_public_body` with `force=True` documents the destructive reduction.

### Integration tests — `foi_pipeline/tests/`

- **No-effect guarantee (the key test):** seed a step's `output.json` with three
  bodies; run the step with `--public-body 1002`; assert bodies 1001 and 1003
  are byte-for-byte unchanged and only 1002 differs; assert `dirty_ids.json ==
  [1002]`.
- **Cascade:** run two consecutive dirty-aware steps with `--public-body 1002`;
  assert the second step evicts and reprocesses only 1002 via the first step's
  `dirty_ids.json`.
- **Orchestration validation failure:** `process.py --public-body 9999` → exit 1.
- **`--from` + `--public-body`:** only the targeted body flows through remaining
  steps; earlier outputs untouched.

### Manual checklist

- [ ] `process.py --public-body 1001` (no force) — others unchanged, 1001 refreshed
- [ ] Single step standalone with `--public-body 1001`
- [ ] `--from validate_websites --public-body 1001`
- [ ] `--public-body 1001 --force` shows destructive warning
- [ ] non-existent / non-integer ID errors
- [ ] `generate_topics` / `db_upload` scoped behaviour

---

## Migration Path

### Phase 1 — Library + writer (PR #1)
- Create `scripts/cli_utils.py` (`add_common_args`, `filter_by_public_body`,
  `validate_public_body`).
- Add `target_public_body` to `IncrementalWriter`, factoring `_evict_keys` out of
  `_evict_upstream_dirty`.
- Unit tests for both. Backward compatible (additive).

### Phase 2 — Orchestration (PR #2)
- Add `--public-body` to `process.py`: validation + passthrough (no auto-force).
- Integration test for validation + passthrough. Backward compatible.

### Phase 3 — Steps, incrementally (one PR each)
Recommended order follows `pipeline.json` and the dirty cascade so each migrated
step can be tested end-to-end against the one above it:

1. `find_public_bodies` (validation source; confirm-only behaviour)
2. `resolve_website_urls`
3. `validate_websites`
4. `find_foi_pages`
5. `check_foi_pages`
6. `get_foi_emails`
7. `find_disclosure_pages`
8. `find_disclosure_files`
9. `transform_disclosure_files`
10. `normalize_disclosure_cells`
11. `extract_disclosures_detect_header_row`
12. `extract_disclosures_canonicalize`
13. `extract_disclosures_deduplicate`
14. `export_status`
15. `generate_topics` (hard-coded read; best-effort)
16. `db_upload` (hard-coded reads; idempotent upsert or skip)

Per step: swap the arg block for `add_common_args`, then apply the handling for
that step's shape — §(a) evict-target, §(b) merge-back, or §(c) filter-reads —
and add the no-effect integration test. Check the inventory table for which §
applies before starting each PR.

> Note: `steps/extract_disclosures/` exists on disk but is **not** in
> `pipeline.json` (legacy). Skip it unless reinstated.

### Phase 4 — Docs
- `foi_pipeline/AGENTS.md`, `steps/README.md`, per-step `README.md`.
- Mark this spec implemented.

---

## File Changes Summary

| File | Action | Risk | Notes |
|------|--------|------|-------|
| `scripts/cli_utils.py` | Create | Low | pure functions (`add_common_args`, `filter_by_public_body`, `validate_public_body`, `merge_replacing_body`), well unit-tested |
| `scripts/file_utils.py` | Modify | **Medium** | `IncrementalWriter.target_public_body` + `_evict_keys` refactor; touches shared resumability/dirty code |
| `process.py` | Modify | Low | additive flag + validation |
| `steps/find_public_bodies/process.py` | Modify | Low–Med | custom writer; confirm-only when scoped |
| 10× IncrementalWriter steps (§a) | Modify | Low | mechanical filter + `target_public_body` kwarg each |
| `extract_disclosures_canonicalize`, `extract_disclosures_deduplicate` (§b) | Modify | **Medium** | merge-back wrapper; dedup may be cross-body |
| `export_status`, `generate_topics`, `db_upload` (§c) | Modify | Med | filter hard-coded reads; derived/best-effort output |

Risk is **not** uniformly "Low" as the previous draft claimed — the
`file_utils.py` change is the highest-leverage and highest-risk edit because all
resumability and dirty propagation flows through it.

---

## Commands Reference (after implementation)

```bash
cd foi_pipeline

# Reprocess one body through the whole pipeline, leaving all others intact:
python process.py --public-body 1001

# Resume from a step for one body:
python process.py --from validate_websites --public-body 1001

# Run a single step against one body, to a scratch output:
PYTHONPATH=. python steps/get_foi_emails/process.py \
  --input steps/check_foi_pages/output.json \
  --output /tmp/test_output.json \
  --public-body 1001

# Destructive: reduce a step's output to one body (rarely wanted):
python process.py --public-body 1001 --force   # warns on stderr
```

---

## Design Decisions

| Question | Resolution |
|----------|------------|
| How to preserve other bodies? | Merge-based `IncrementalWriter` **without** `--force`; never overwrite. |
| How to *reprocess* the target? | Targeted eviction via `target_public_body`, reusing the dirty/`_evict_upstream_dirty` path. |
| Cascade downstream? | Yes, automatically via existing `dirty_ids.json` propagation. |
| Filter at step or orchestration level? | Step level, so single steps are runnable; orchestration validates + passes through. |
| `--public-body` + `--force`? | Orthogonal; allowed but destructive (reduces to one body); warn, don't auto-inject force. |
| Steps that ignore `--input` (`generate_topics`, `db_upload`)? | Filter their hard-coded reads; document derived/best-effort output. |
| `find_public_bodies` when scoped? | Confirm body exists; do **not** shrink its output to one body. |
| Output structure changed? | No. |
| Multiple IDs / ranges? | No, single integer. |
| New CLI library? | Yes — `scripts/cli_utils.py`. |
| Replace `IncrementalWriter` with a generic template? | **No** — that was the previous draft's core mistake. |

---

## Appendix: Verified Step Inventory

| Step | Top-level key | Writer | Reads `--input`? | Dirty-aware? |
|------|---------------|--------|------------------|--------------|
| Step | Top-level key | Writer / shape | Reads `--input`? | `--public-body` handling |
|------|---------------|----------------|------------------|--------------------------|
| find_public_bodies | public_bodies | custom scraper | n/a | confirm-only (§find_public_bodies) |
| resolve_website_urls | results | Incremental | yes | evict target (§a) |
| validate_websites | results | Incremental (override only) | yes | evict target (§a) |
| find_foi_pages | results | Incremental + dirty | yes | evict target (§a) |
| check_foi_pages | results | Incremental + dirty | yes | evict target (§a) |
| get_foi_emails | results | Incremental + dirty | yes | evict target (§a) |
| find_disclosure_pages | results | Incremental + dirty | yes | evict target (§a) |
| find_disclosure_files | results | Incremental + dirty | yes | evict target (§a) |
| transform_disclosure_files | results | Incremental + dirty | yes | evict target (§a) |
| normalize_disclosure_cells | results | Incremental + dirty | yes | evict target (§a) |
| extract_disclosures_detect_header_row | results | Incremental + dirty | yes | evict target (§a) |
| extract_disclosures_canonicalize | results | **plain write_json** | yes | merge-back (§b) |
| extract_disclosures_deduplicate | results | **plain write_json** | yes | merge-back (§b); verify cross-body dedup |
| export_status | public_bodies | aggregator (multi-read) + `public/` | partial | filter reads; derived (§c) |
| generate_topics | results (topics) | plain write | **no** (reads canonicalize) | filter read; derived (§c) |
| db_upload | n/a | DB upsert (multi-read) | **no** | filter reads; idempotent or skip (§c) |

This three-way split is the reason a single generic step template is impossible
(and why the previous draft's template was unsafe).
