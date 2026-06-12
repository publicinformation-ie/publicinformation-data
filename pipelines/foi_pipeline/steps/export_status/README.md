# export_status

Merges the outputs of all pipeline steps into a unified per-body status report and writes the public-facing JSON files consumed by the website.

## What it does

Reads `find_public_bodies/output.json` as the base record set, then iterates through each pipeline step in order (as defined in `pipeline.json`) and calls a per-step merger function that updates each body's `status` object. The status object tracks:

- `website_url` — whether the body's website is reachable.
- `foi_page` — whether a FOI page was found and is reachable.
- `foi_email` — whether a FOI contact email was extracted.
- `disclosures_page` — whether a disclosure log page was found.
- `disclosure_files` — total / valid / failed file counts.
- `foi_requests` — count of successfully canonicalised FOI request records.

In addition to the step-level `output.json`, this step writes three public JSON files to `public/`:

| File | Contents |
|---|---|
| `public/pipeline-data.json` | Full merged status for every public body |
| `public/disclosure-files.json` | Flat list of all discovered disclosure log file URLs |
| `public/foi-disclosures.json` | All canonicalised FOI request records |

## Input

All step `output.json` files (read directly from sibling step directories, not via the `--input` argument).

## Output

`output.json` — `{ metadata, public_bodies: [...] }`. Each body includes its full `status` object with results from every completed step.
