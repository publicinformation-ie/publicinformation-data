# Fail-closed sweep — implementation plan (2026-11-26)

Implements §6 step 2 of `followups-2026-11-26.md`. No model spend:
extraction must replay from cache. Do not push; pushing publishes.

## Decisions taken

- **Dataset version:** bump `1.0.0` → `1.1.0` (additive: `item_key` added to
  `decisions.csv`, `proposer_unresolved`/`seconder_unresolved` added;
  `item_id` dropped). `v1.0.0/` stays as the historical release.
- **P3.6 grounding:** a proposer/seconder must be printed in the item text and
  present at the meeting; otherwise the attribution is withheld and flagged.
  When attendance is withheld, the presence check is skipped.
- **P3.6 minutes approval:** discard only when *every* token in the quote is
  approval/minutes language. A compound decision is kept.
- **COFOG levels:** reject division codes (never class or group). A group code
  must be justified: `04.5` by at least two transport subdomains, any other
  group by at least two child class codes in the same item.
- **P2.3:** keep the per-page text-extent bands (real headers sit at ~11% of
  the page height, so absolute page-height bands would stop removing them);
  treat a line repeated on every page of a 2-page PDF as furniture; fail closed
  on a removed line that is not the running header or a recognisable Meath
  footer.
- **P2.6:** a missing or mismatched sidecar re-downloads. A changed remote PDF
  at the same URL remains undetected (out of scope; noted in the step README).

## Tasks

1. **P2.2 initials fallback** — `steps/resolve_attendees/resolving.py`.
   If the meeting prints a name for `(XX)` that does not resolve, return an
   error; use the register only when the meeting prints nothing.
   Tests in `tests/test_resolve_attendees.py`.

2. **P3.6 register validation** — same file. `load_register` validates shape,
   `VALID_KINDS`, councillor id presence and the councillor reference (when
   present), so a bad register fails the step rather than a skipped test.

3. **P2.4 stale output deletion** — `scripts/transform_spc_meetings.py`.
   `write_if_changed(generated, ttl_path, output_dir)` deletes files under
   `output_dir` absent from `generated` and counts that as a change.
   Tests in `tests/test_spc_meetings_dataset.py`.

4. **P2.5 dangling references** — `steps/export_spc_meetings/exporting.py`.
   Require a boolean `attendance_published`; fail when it is false but rows
   exist; raise on a person id absent from the register instead of counting.
   Tests in `tests/test_export_spc_meetings.py`.

5. **P2.6 fetch cache** — `steps/fetch_spc_minutes/fetching.py`.
   Validate `%PDF`, atomic write, verify the sidecar sha on every read (miss →
   re-download), separate `InvalidPdf` from `DownloadFailed`.
   Tests in `tests/test_fetch_spc_minutes.py`.

6. **P2.7 LLM cache** — `steps/extract_spc_items/extraction.py`.
   Key on a hash of `system + user`; write only after schema/echo validation;
   atomic write. Migrate the six local cache files before the replay run.
   Update the sweep's `cache_path` call. Tests in `tests/test_extract_spc_items.py`.

7. **P3.6 extraction fail-closed** — same file.
   Approval-only discard; minimum decision length/tokens; duplicate decision
   text; duplicate/unknown `item_key` fails the meeting; proposer/seconder
   grounding and presence with `*_unresolved` flags.

8. **COFOG levels** — same file. Division rejected; group justification as
   decided above. Tests in `tests/test_extract_spc_items.py`.

9. **P2.3 furniture residuals** — `steps/render_spc_minutes/rendering.py`.
   Page-height bands, 2-page threshold, footer pattern classification,
   `UnrecognisedFurniture` fail-closed. Tests in `tests/test_render_spc_minutes.py`.

10. **P2.8 contract** — `scripts/transform_spc_meetings.py`,
    `public/schemas/spc-meetings.schema.json`, `public/catalog/dataset-spc-meetings.ttl`,
    `public/CHANGELOG.md`. Bump to 1.1.0; drop `item_id`; add `item_key` and the
    unresolved flags to decisions; `additionalProperties: false`; CSVW
    `separator`/`null`; update versioned paths and distribution URLs.

11. **Regenerate and verify** — run the pipeline window with every cache file
    confirmed present first; run the publisher; verify tests, `pyright`,
    schema, counts and the `public/` diff. Do not push.
