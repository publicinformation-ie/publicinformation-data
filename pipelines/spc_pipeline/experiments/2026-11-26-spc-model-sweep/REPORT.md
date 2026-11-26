# SPC model sweep

Candidates scored against the hand-labelled gold set for the six Meath Transportation and Urban Regeneration SPC meetings (February 2025 to May 2026). Every call was made once per meeting per model and cached; re-scoring is offline and free.

## Method

- **Decisions.** A gold decision is matched by a same-item decision whose quote is the same span, allowing a boundary difference: one quote contains the other and the shorter span is at least half the longer or six words long. Pairing is greedy, so each gold decision matches once. Precision and recall follow from that pairing.
- **Decision type** is scored over the matched pairs.
- **Topics.** *Strict* requires the same primary COFOG code. *Hierarchy-tolerant agreement* also accepts the gold primary appearing anywhere in the model's list, or a group/class relation (04.5 vs 04.5.1), because both are defensible readings of the item.
- **Verbatim failure rate** is the share of produced decisions the quote check rejected. **Extraction failure rate** is the share of meetings whose response violated the schema or its echoed context; a failed meeting scores zero, never a silent pass.
- **Cost** is a deterministic chars/4 token estimate at the prices in `prices.json` (repo-recorded, possibly stale). It ranks models consistently but is not billable.

## Caveats

- The gold set was labelled from the minutes by hand and is a floor, not a ceiling: genuine agreements the labeller did not list count against precision. Read precision as agreement with the hand labels.
- Six meetings is a small sample. Differences of a few points are within noise and should not decide a model on their own.
- Procedural items (for example "Matters Arising") are labelled `01.1.1`; models often prefer the substantive transport code. That is a labelling judgment, so topic numbers understate model quality.

## opencode-go/deepseek-v4.1-flash

| Metric | Mean |
|---|---:|
| Decision precision | 0.833 |
| Decision recall | 0.945 |
| Decision type accuracy | 1.0 |
| Topic primary accuracy (strict) | 0.724 |
| Topic agreement (hierarchy-tolerant) | 0.8 |
| Verbatim failure rate | 0.0 |
| Extraction failure rate | 0.0 |
| Cost per meeting (USD) | 0.0011 |

| Meeting | Precision | Recall | Type | Topics | Verbatim fail | Cost |
|---|---:|---:|---:|---:|---:|---:|
| 2026-02-19 | 1.0 | 1.0 | 1.0 | 0.333 | 0.0 | 0.0009735 |
| 2026-05-21 | 0.5 | 1.0 | 1.0 | 1.0 | 0.0 | 0.0012255 |
| 2025-02-20 | 1.0 | 1.0 | 1.0 | 0.8 | 0.0 | 0.00101475 |
| 2025-05-27 | 1.0 | 1.0 | 1.0 | 0.875 | 0.0 | 0.0014643 |
| 2025-09-11 | 1.0 | 1.0 | 1.0 | 0.667 | 0.0 | 0.00101205 |
| 2025-11-20 | 0.5 | 0.667 | 1.0 | 0.667 | 0.0 | 0.00104745 |

## opencode-go/glm-5.3-flash

| Metric | Mean |
|---|---:|
| Decision precision | 0.903 |
| Decision recall | 1.0 |
| Decision type accuracy | 0.945 |
| Topic primary accuracy (strict) | 0.677 |
| Topic agreement (hierarchy-tolerant) | 0.772 |
| Verbatim failure rate | 0.0 |
| Extraction failure rate | 0.0 |
| Cost per meeting (USD) | 0.001 |

| Meeting | Precision | Recall | Type | Topics | Verbatim fail | Cost |
|---|---:|---:|---:|---:|---:|---:|
| 2026-02-19 | 1.0 | 1.0 | 1.0 | 0.333 | 0.0 | 0.0009548 |
| 2026-05-21 | 0.667 | 1.0 | 1.0 | 0.857 | 0.0 | 0.0011428 |
| 2025-02-20 | 1.0 | 1.0 | 0.667 | 0.6 | 0.0 | 0.00089425 |
| 2025-05-27 | 1.0 | 1.0 | 1.0 | 0.938 | 0.0 | 0.0013289999999999999 |
| 2025-09-11 | 1.0 | 1.0 | 1.0 | 0.667 | 0.0 | 0.00095535 |
| 2025-11-20 | 0.75 | 1.0 | 1.0 | 0.667 | 0.0 | 0.00101195 |

## opencode-go/gpt-6-luna

| Metric | Mean |
|---|---:|
| Decision precision | 0.795 |
| Decision recall | 1.0 |
| Decision type accuracy | 0.945 |
| Topic primary accuracy (strict) | 0.704 |
| Topic agreement (hierarchy-tolerant) | 0.766 |
| Verbatim failure rate | 0.0 |
| Extraction failure rate | 0.0 |
| Cost per meeting (USD) | 0.0008 |

| Meeting | Precision | Recall | Type | Topics | Verbatim fail | Cost |
|---|---:|---:|---:|---:|---:|---:|
| 2026-02-19 | 0.5 | 1.0 | 1.0 | 0.667 | 0.0 | 0.0007592 |
| 2026-05-21 | 0.667 | 1.0 | 1.0 | 0.714 | 0.0 | 0.0008647 |
| 2025-02-20 | 1.0 | 1.0 | 0.667 | 0.8 | 0.0 | 0.0007525 |
| 2025-05-27 | 1.0 | 1.0 | 1.0 | 0.875 | 0.0 | 0.0010715 |
| 2025-09-11 | 1.0 | 1.0 | 1.0 | 0.667 | 0.0 | 0.0007119 |
| 2025-11-20 | 0.6 | 1.0 | 1.0 | 0.5 | 0.0 | 0.0007957999999999999 |

## Decision

Gate: decision recall >= 0.90, decision type accuracy >= 0.90, topic agreement >= 0.75, verbatim failure rate = 0, extraction failure rate = 0.

Production model: `opencode-go/deepseek-v4.1-flash`.

The same choice is recorded in `steps/extract_spc_items/README.md`.
