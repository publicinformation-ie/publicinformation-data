# Guard it — implementation plan (2026-11-26)

Implements §6 step 3 of `followups-2026-11-26.md` (P3.1, P3.2, P3.3, P3.7).
No model spend; no pipeline step runs; nothing here publishes.

## Decisions taken

- **Fixtures are the six source PDFs** (1.36 MB total) committed under
  `pipelines/spc_pipeline/tests/fixtures/pdf/` in **ordinary git**, not LFS.
  LFS would break the suite in a code-only clone, and the whole point is that
  CI must always run it. A small `fixtures/meetings.json` manifest holds each
  fetch record without `pages`, plus the PDF file name and its sha256; a test
  asserts the sha, so the PDFs are pinned.
- **One session-scoped chain in `conftest.py`**: `fetched_meetings` extracts
  the pages from the committed PDFs, then `parsed_meetings`,
  `resolved_meetings` and `rendered_meetings` run the real step functions
  once. Every cache-guarded test consumes one of these instead of a
  git-ignored `output.json`.
- **P3.3 snapshot is the published Markdown**, not a duplicate fixture:
  `public/latest/spc-meetings/minutes/<committee>/<date>.md` is already
  committed, human-reviewed and byte-identical to the renderer's output
  (verified before planning). A render change therefore shows as a normal
  `public/` diff. `fixtures/render_sha256.json` is deleted.
- **P3.7 `status.py` reads `pipeline.json`** for step order (step 1 included,
  cross-pipeline path resolved from the repo root) and joins every stage and
  error to a meeting through `source_url`/`file_url` → `meeting_id` from the
  header step. A file that never reaches the header is listed by its file URL
  and the last stage it reached. Step 1 stays aggregate-only (a list of local
  authorities, not meetings).
- A test asserting "no cache-based skip remains" is not enough on its own;
  each rewritten test must actually exercise the fixture. The old
  `pytest.mark.skipif`/`pytest.skip` guards on the six cache-dependent tests
  are removed.

## Tasks

1. **Commit the fixture PDFs and manifest** — `tests/fixtures/pdf/*.pdf`,
   `tests/fixtures/meetings.json`. Generate the manifest from the current
   `fetch_spc_minutes/output.json` minus `pages`, adding `pdf` and keeping
   `sha256`. Test: each manifest sha256 equals the committed PDF's sha256,
   there are six meetings, and every page has words.

2. **Session fixture chain** — `tests/conftest.py`:
   `fetched_meetings` (extract pages), `parsed_meetings`,
   `resolved_meetings`, `rendered_meetings`. Test each stage yields six
   records and zero errors.

3. **Rewrite the cache-guarded tests**:
   - `test_fetch_spc_minutes.py::test_real_cached_pdfs_have_words` →
     `test_committed_pdfs_have_words`, driven by the manifest (no skip).
   - `test_parse_meeting_header.py` real tests → `fetched_meetings`.
   - `test_resolve_attendees.py` real test → `parsed_meetings`.
   - `test_render_spc_minutes.py` module fixture → `rendered_meetings`;
     `_records()` in the withheld test → `resolved_meetings`.
   - `test_model_sweep.py` real test → `rendered_meetings`.
   All six `skipif`/`skip` guards listed in P3.2 for git-ignored caches are
   gone. The three reference-input guards stay.

4. **Reviewable render snapshot** — delete `fixtures/render_sha256.json`;
   `test_markdown_matches_the_committed_snapshot` asserts
   `record["markdown"].encode() == public/latest/.../<date>.md` bytes for all
   six meetings.

5. **CI runs the suite** — `.github/workflows/ci.yml` adds
   `uv run pytest pipelines/spc_pipeline/tests -q`; `AGENTS.md` adds the suite
   to the Tests table and changes "three test suites" to four.

6. **`status.py`**: `steps_from_config(pipeline_dir)` reads `pipeline.json`;
   `funnel` builds `url_to_meeting` in a first pass, then maps records and
   errors; `meetings` entries carry `meeting_id` (or `file_url` when unmapped),
   `stages` (list, in pipeline order), `last_stage`, and the attributed
   `errors` list. Tests seed a real `pipeline.json`, a file-URL step and a
   meeting-id step, and assert the join, the stalled file, and error
   attribution. Keep the CLI table and exit codes.

7. **Docs and handoff** — update the `status.py` docstring, the README
   "Running" section, `AGENTS.md` status row if needed, and
   `followups-2026-11-26.md` §0/§4/§6. Record the new test counts.

8. **Verify** — 144+ SPC tests, 567+ root tests, `pyright`, docs check, and a
   run of `status.py` against the real outputs. Confirm `git status` shows
   only intended files plus the three foreign untracked paths.
