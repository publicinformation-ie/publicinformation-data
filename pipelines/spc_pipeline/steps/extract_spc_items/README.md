# extract_spc_items (paid)

One paid model call per meeting extracts official decisions and COFOG 1999 /
transport-subdomain topics from the rendered agenda items.

## Prompt

`PROMPT_VERSION = "spc-items-v1"`. The prompt contains:

- the meeting ID, date and committee;
- every item's number, title and text **except** minutes-approval items, which
  are classified deterministically (`01.1.1`, `procedural: true`) and never
  sent;
- the meeting's printed initials map;
- the closed lists: every COFOG 1999 code and description, the transport
  subdomains and their plain labels, and the decision types.

The model returns JSON validated against `RESPONSE_SCHEMA`:
`items[]` with `item_key` (the stable key, which disambiguates two items printed with the same number), `topics{cofog[1–3], subdomains[], procedural}` and
`decisions[{decision_text, decision_type, proposer, seconder}]`.

Models sometimes echo the meeting context they were given, either as
`meeting_id` / `date` / `committee` or as a `meeting` object. Those values are
accepted only when they agree with the meeting being extracted; a wrong echo
fails the meeting closed. Any other extra key is still a schema failure.

## Validation order

1. JSON schema — a failure withholds the whole meeting's decisions and topics.
2. Closed lists: unknown COFOG code, subdomain or decision type withholds the
   affected topics/decision.
3. The `04.5` rule: a subdomain without a `04.5` code withholds the item's
   topics.
4. Verbatim quote check (whitespace-normalised) against the item text; a
   paraphrase is `DecisionNotInSource` and is dropped.
5. Minutes-approval decisions are discarded and counted.
6. Proposer and seconder resolve through the meeting's initials, then the
   register. An unresolved value is an error and the field is `null`, never
   guessed.

Decision IDs are `<meeting_id>/dNN` in order of appearance.

## Cache

`pipelines/spc_pipeline/cache/llm/<sha256>-<model>-spc-items-v1.json` stores
the raw response. A re-run with the same source sha256, model and prompt
version makes no model call. A deliberate re-extraction that changes a
published decision set is a reviewed content change and belongs in
`public/CHANGELOG.md`.

## Configuration

The production model is `opencode-go/deepseek-v4.1-flash`
(`extraction.DEFAULT_MODEL`). `SPC_LLM_PROVIDER`, `SPC_LLM_MODEL`,
`SPC_LLM_BASE_URL`, `SPC_LLM_API_KEY` and `SPC_LLM_SESSION_ID` override it;
each falls back to the corresponding `MOTIONS_LLM_*` value when unset, then to
`llm_extract`'s defaults. The model is part of the cache key, so switching it
extracts afresh instead of reading another model's responses.

## Model choice

Chosen on 2026-11-26 from the sweep in
`experiments/2026-11-26-spc-model-sweep/REPORT.md` (six meetings, gold set,
cached calls). Gate: decision recall ≥ 0.90, decision type accuracy ≥ 0.90,
topic agreement ≥ 0.75, zero verbatim and extraction failures. All three
candidates passed the gate:

| Model | Recall | Type | Topic agreement | USD/meeting |
|---|---:|---:|---:|---:|
| `opencode-go/deepseek-v4.1-flash` | 0.945 | 1.000 | 0.800 | 0.0011 |
| `opencode-go/glm-5.3-flash` | 1.000 | 0.945 | 0.772 | 0.0010 |
| `opencode-go/gpt-6-luna` | 1.000 | 0.945 | 0.766 | 0.0008 |

`deepseek-v4.1-flash` was chosen for its perfect decision-type accuracy and
the best topic agreement; the cost difference is negligible. Re-run the sweep
with the same command before changing it, and update this table and
`REPORT.md` together.

## Cost

The step is listed in `paid_steps: {"extract_spc_items": ["llm"]}` and in
`CLAUDE.md`'s cost rule. Do not run it, a full pipeline, or a `--from`/`--to`
window reaching it without explicit permission for that run. The deterministic
window ends at `--to render_spc_minutes`.

## Errors

`ExtractionFailed`, `MissingItem`, `UnexpectedItem`, `UnknownCofogCode`,
`DuplicateCofogCode`, `UnknownSubdomain`, `SubdomainWithoutTransport`,
`UnknownDecisionType`, `DecisionNotInSource`, `UnresolvedDecisionPerson`.
