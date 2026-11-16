# resolve_recipients

Attributes every project row to a recipient from two independent signals, and
links local authorities to the Public Bodies dataset.

## The two signals

1. **The section heading**, normalised and looked up in the committed
   `recipient_aliases.json`, which carries the spelling variants the documents
   print (`Dun Loaghaire Rathdown County Council`, `Roscommon County`,
   `Waterford City and County Council including SDZ`, and the three titles the
   non-local-authority block appears under).
2. **The project-code prefix**, looked up in the committed `code_prefixes.json`.

Both files are the source of truth; nothing is inferred from a name at runtime.

| Situation | Outcome |
|---|---|
| heading and prefix name the same recipient | attributed (`heading+prefix`) |
| no heading, prefix names exactly one recipient | attributed (`prefix_only`) |
| heading names one recipient, prefix another | `RecipientConflict`, row withheld |
| no heading, prefix names several recipients | `RecipientUnresolved`, row withheld |
| prefix not declared, or heading unknown | `RecipientUnresolved`, row withheld |

`LCC` is the one prefix the documents genuinely reuse: it is Limerick's, and it
is also printed on Louth's provisional 2022 codes. The committed map records
both candidates, so a Louth row ending `LCC/22/xxxx` is not a conflict — but a
heading-less `LCC` row is ambiguous and is withheld rather than guessed.

## Local authorities and other recipients

- A **local authority** must resolve to a record in the Public Bodies register
  (`pipelines/foi_pipeline/steps/find_public_bodies/output.json`). If one does
  not, publication stops with an error naming the authority — a record without
  its body link is never emitted. The body's slug comes from the permanent seed
  (`slug_seed.json`) via `lib.body_refs`, so the published URI always matches
  the public-bodies dataset even if a name changes.
- **Any other recipient** (the `Campuses, Hospitals, Educational Institutions and
  Others` block: TUD, TCD, the hospitals, OPW, the NTA's own programme lines) is
  kept by its printed name with no `public_body`. Those organisations are not
  public bodies in that dataset, and inventing a link would be worse than
  leaving it out.

That block is also the document's own **Active Travel Investment** "Others"
table, so every block in it belongs to the `active_travel` stream — including
the 2026 edition, where it prints one `Subtotal` per sub-programme (regional
bikes, school cycle parking, NTA support, campuses). A local-authority section's
block order still decides its streams.

## Output

Each project row gains `recipient_name`, `recipient_kind` (`local_authority` or
`other`), `recipient_slug`, `public_body_id` and `public_body`. Each section
gains the same, plus `resolution` (`heading+prefix` or `prefix_only`) and, for
the non-local-authority block, `stream_rule:
non_local_authority_section`. Rows whose recipient could not be resolved are
withheld and reported.

## Errors

`RecipientConflict`, `RecipientUnresolved` — both withhold the row. An
unresolvable local authority in the register is process-fatal (a configuration
drift, not a data defect).
