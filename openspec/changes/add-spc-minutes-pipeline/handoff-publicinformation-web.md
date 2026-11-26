# Handoff prompt: consume the SPC meetings dataset in publicinformation-web

> Finalised 2026-11-26 against the published `public/latest/spc-meetings/` output:
> 6 meetings, 28 people, 101 attendance rows, 46 agenda items, 18 decisions and
> 6 minutes files. Every URL, file name and field below exists in that output.

Paste everything below the line into an agent session on the
`publicinformation-ie/publicinformation-web` repo.

---

You are working in the `publicinformation-ie/publicinformation-web` repo (Astro,
static build). The data repo, `publicinformation-data`, now publishes a new
dataset, **SPC meetings**: the minutes of council Strategic Policy Committees.
It covers who attended, the official decisions, and the topic of each agenda
item on a common taxonomy. The first committee is Meath County Council's
Transportation and Urban Regeneration SPC (6 meetings, February 2025 to May
2026). More councils and committees will follow with no schema change. Read
`AGENTS.md`, `PRODUCT.md`, `DESIGN.md` and the `motions` dataset integration
before you start.

Use OpenSpec: propose the change with `/opsx:propose` before writing code.

## What the data repo publishes

Base: `https://data.publicinformation.ie/latest/spc-meetings/`. A versioned copy
with identical bytes is at `https://data.publicinformation.ie/v1.0.0/spc-meetings/`.
Each table is published as `.jsonld` (a `@context` + `@graph`), `.csv` and
`.csv-metadata.json`. Fetch the JSON-LD through `src/lib/dataSource.ts`
(`fetchDatasetJson`, `fetchDatasetFreshness`), as `src/lib/motions.ts` does for
`latest/motions/motions.jsonld`. The CSV files are for spreadsheet users; the
site should read the JSON-LD.

| File | Rows | One record per | Fields |
|---|---|---|---|
| `meetings.jsonld` | 6 | meeting | `meeting_id`, `committee_id`, `committee_name`, `public_body_id`, `public_body` (Public Bodies URI), `meeting_date`, `venue`, `start_time`, `end_time`, `source_url`, `source_sha256`, `minutes_path`, `attendance_published` |
| `people.jsonld` | 28 | person | `person_id`, `canonical_name`, `kind` (`councillor` \| `sectoral_representative` \| `official` \| `guest`), `councillor_id` (councillors only; the same ID the motions dataset uses), `public_body_id`, `public_body` |
| `attendance.jsonld` | 98 | person × meeting | `meeting_id`, `meeting_date`, `person_id`, `category` (`councillors` \| `sectoral_representatives` \| `apologies` \| `officials` \| `presenters`), `role` (as printed, or null), `status` (`present` \| `apologies`), `mode` (`remote` \| `in_person` \| `not_stated`), `presented` (true when the name also appears in the presenters block) |
| `items.jsonld` | 46 | agenda item | `item_id`, `meeting_id`, `item_number`, `item_key`, `title`, `text`, `is_minutes_approval`, `topics_published`, `cofog` (array of 1–3 codes, first is primary), `subdomains` (array), `procedural` |
| `decisions.jsonld` | 18 | official decision | `decision_id`, `meeting_id`, `meeting_date`, `item_key`, `item_number`, `decision_text` (verbatim quote), `decision_type` (`agreed` \| `adopted` \| `recommended_to_council` \| `referred` \| `deferred` \| `appointment`), `proposer`, `seconder` (person IDs or null) |
| `minutes/<council>/<committee>/<YYYY-MM-DD>.md` | 6 | meeting | verbatim minutes as Markdown with YAML front matter |

Every record also carries `@id` and `@type` (`spc:Meeting`, `spc:Person`,
`spc:Attendance`, `spc:Item`, `spc:Decision`). Join on `meeting_id` and
`person_id`; join a decision to its item on `item_key` (not `item_number` — the
May 2026 minutes print two items as `6.0`, published as `item-6-0` and
`item-6-0-2`).

IDs look like `meath/transportation-urban-regeneration/2026-02-19` (meeting),
`meath/sean-drew` (councillor) and `meath/person/dave-anderson` (non-councillor).
They are stable, so use them in URLs.

### Sample records (real, one per file, trimmed to the published fields)

`meetings.jsonld`:

```json
{
  "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
  "committee_id": "meath/transportation-urban-regeneration",
  "committee_name": "Transportation & Urban Regeneration Strategic Policy Committee",
  "public_body_id": 1511,
  "meeting_date": "2026-02-19",
  "venue": "Swift Room, Buvinda House, Dublin Rd, Navan, C15 Y291",
  "start_time": "2.30 pm",
  "end_time": "16.10 pm",
  "source_url": "https://www.meath.ie/system/files/media/file-uploads/2026-09/February%202026%20-%20Minutes%20-%20SPC%20Transportation%20and%20Urban%20Regeneration_0.pdf",
  "source_sha256": "5c8ee59ba08631373f4ce443d9454293c03274a491600a2ddab68daca1f3cd35",
  "minutes_path": "minutes/meath/transportation-urban-regeneration/2026-02-19.md",
  "attendance_published": true,
  "@type": "spc:Meeting",
  "public_body": "https://data.publicinformation.ie/body/meath-county-council",
  "@id": "https://data.publicinformation.ie/spc-meetings/meeting/meath/transportation-urban-regeneration/2026-02-19"
}
```

`people.jsonld`:

```json
{
  "person_id": "meath/alan-tobin",
  "canonical_name": "Alan Tobin",
  "kind": "councillor",
  "councillor_id": "meath/alan-tobin",
  "public_body_id": 1511,
  "@type": "spc:Person",
  "public_body": "https://data.publicinformation.ie/body/meath-county-council",
  "@id": "https://data.publicinformation.ie/spc-meetings/person/meath/alan-tobin"
}
```

`attendance.jsonld`:

```json
{
  "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
  "meeting_date": "2026-02-19",
  "person_id": "meath/michael-bray",
  "category": "councillors",
  "role": "Chair",
  "status": "present",
  "mode": "not_stated",
  "presented": false,
  "@type": "spc:Attendance",
  "@id": "https://data.publicinformation.ie/spc-meetings/attendance/meath/transportation-urban-regeneration/2026-02-19/meath/michael-bray"
}
```

`items.jsonld`:

```json
{
  "item_id": "meath/transportation-urban-regeneration/2026-02-19/item-1-0",
  "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
  "item_number": "1.0",
  "item_key": "item-1-0",
  "title": "Minutes of Previous Meeting 11th September 2025",
  "text": "1.0 Minutes of Previous Meeting 11th September 2025 Proposed by; Cllr Amanda Smith (AS) Seconded by: Cllr Mike Bray (MB)",
  "is_minutes_approval": true,
  "topics_published": true,
  "cofog": ["01.1.1"],
  "subdomains": [],
  "procedural": true,
  "@type": "spc:Item",
  "@id": "https://data.publicinformation.ie/spc-meetings/item/meath/transportation-urban-regeneration/2026-02-19/item-1-0"
}
```

`decisions.jsonld`:

```json
{
  "item_key": "item-3-0",
  "item_number": "3.0",
  "decision_text": "MB referred Item to the next SPC in order to facilitate attendance of Cllr. Helen Meyer who could not attend due to other commitments.",
  "decision_type": "referred",
  "proposer": "meath/michael-bray",
  "seconder": null,
  "decision_id": "meath/transportation-urban-regeneration/2026-02-19/d01",
  "meeting_id": "meath/transportation-urban-regeneration/2026-02-19",
  "meeting_date": "2026-02-19",
  "@type": "spc:Decision",
  "@id": "https://data.publicinformation.ie/spc-meetings/decision/meath/transportation-urban-regeneration/2026-02-19/d01"
}
```

### Minutes Markdown

Front matter, exactly these keys (`venue` and the times can be null):

```yaml
---
meeting_id: "meath/transportation-urban-regeneration/2026-02-19"
committee_id: "meath/transportation-urban-regeneration"
committee_name: "Transportation & Urban Regeneration Strategic Policy Committee"
public_body_id: 1511
meeting_date: "2026-02-19"
venue: "Swift Room, Buvinda House, Dublin Rd, Navan, C15 Y291"
start_time: "2.30 pm"
end_time: "16.10 pm"
source_url: "https://www.meath.ie/system/files/media/file-uploads/2026-09/February%202026%20-%20Minutes%20-%20SPC%20Transportation%20and%20Urban%20Regeneration_0.pdf"
source_sha256: "5c8ee59ba08631373f4ce443d9454293c03274a491600a2ddab68daca1f3cd35"
---
```

The body starts with `# <committee name>`, then a date/venue line, an
`## Attendance` block (grouped `### Councillors`, `### Sectoral
Representatives`, `### Absent / Apologies`, `### Officials`, `### Presenters`,
each entry the printed text), then `## Agenda items`. Each agenda item is a
`##` heading ending in an anchor built from `item_key`:

```markdown
## 4.0 Climate Action – Decarbonisation Zones (DZ’s) {#item-4-0}
```

so `item-6-0-2` is `{#item-6-0-2}`. The ad-hoc business section is
`## AOB {#aob}` (then `{#aob-2}` and so on). Markdown/HTML characters are
backslash-escaped (`\&`, `\<`, `\#`), and the text keeps the council's typos and
initials ("SD", "MM") verbatim.

### Vocabularies

Under `https://data.publicinformation.ie/vocabularies/`, each with CSVW
metadata, columns `uri,notation,name,description`:

| File | Terms |
|---|---|
| `cofog-1999.csv` | 188 COFOG 1999 divisions, groups and classes, with the UN descriptions |
| `transport-subdomain.csv` | 17 transport subdomains, with plain labels |
| `spc-decision-type.csv` | the six `decision_type` values |
| `spc-attendance-status.csv` | `present`, `apologies` |
| `spc-attendance-mode.csv` | `remote`, `in_person`, `not_stated` |
| `spc-attendee-category.csv` | the five `category` values |

Show the plain `name` (for example "Regional and local roads"), not the raw
notation code, wherever a reader sees a topic.

## Rules you must respect

1. **Approval of previous minutes is not a decision.** The data repo already
   excludes it: `is_minutes_approval` is true on those items and no decision
   references them. Do not reconstruct one from the Markdown.
2. **Counting attendance.** "Meetings attended by person X" means attendance
   rows with `status = present` and that `person_id`. The denominator is the
   meetings where `attendance_published` is `true`. A meeting with
   `attendance_published: false` has no attendance rows because its attendance
   is under review, not because nobody attended. Show it as "attendance not yet
   available", never as absence. (All six meetings currently publish
   attendance.)
3. **Names.** `attendance` carries no printed name: join `person_id` to
   `people.jsonld` for `canonical_name`. `role` is the role as printed (for
   example "Chair", "PPN Rep", "Senior Executive Engineer") and can be null.
   There is exactly one attendance row per person per meeting: a person printed
   in two blocks (an official who also presented) has their roles joined with
   `"; "`, and `presented: true` marks the presentation.
4. **Verbatim text.** The minutes Markdown reproduces the council's text
   exactly, including its typos and initials. Do not correct, summarise or
   expand it. Each meeting's attendance block maps initials to names, so you may
   show that legend beside the text. `decision_text` is a contiguous quote
   inside the item's `text`, so you can highlight it in place.
5. **Trust boundary.** The minutes Markdown has no raw HTML by contract (the
   renderer escapes markup), so it can be rendered like library documents (see
   the trust-boundary comment in `src/content.config.ts`). Still validate front
   matter with a zod schema and fail the build on a malformed file. Accept
   `source_url` only if it is http(s).
6. **Withheld parts.** An item with `topics_published: false` has `cofog: null`,
   `subdomains: null` and `procedural: null`; render the item without topics. A
   decision that failed validation is absent. Render what is there and do not
   invent placeholders.
7. **Councillor join.** For councillors, `councillor_id` is the same ID the
   motions dataset uses on `proposer_id` / `seconder_id`, so a councillor page
   can show both their motions and their SPC attendance.

## What to build

1. **Meeting page**, readable on a phone: `/bodies/<slug>/spc-meetings/<committee>/<date>/`
   or the route pattern that fits the existing per-body dataset pages. Show, in
   order:
   - a header with committee, `meeting_date`, `venue` and a link to
     `source_url`;
   - attendance grouped by `category`, with `mode` shown where stated and
     `apologies` listed separately;
   - the verbatim minutes, with each agenda item heading anchored (`#item-4-0`)
     and tagged with its topic labels;
   - decisions listed under their agenda item (`item_key`).
2. **Committee page**: the list of meetings, plus an attendance matrix
   (people × meetings) that becomes a per-person list on small screens.
3. **Person attendance**: on a councillor's existing pages, if any, and on a
   simple page for non-councillors, show meetings attended out of meetings with
   published attendance.
4. **Topics**: let a reader filter agenda items by COFOG group and, under
   Transport (`04.5`), by subdomain (`subdomains` is non-empty only for
   transport items). Consider surfacing Transport items on
   `/subjects/transport/`.
5. Register the dataset in `src/lib/datasets/registry.ts` with a manifest like
   `motionsManifest` (`perBody: true`). Add it to `llms.txt` and the data index
   the way other datasets are added.

## Done when

- `npm test` and the Astro build pass, and the build fails on malformed minutes
  front matter (test it with a fixture).
- A meeting page at 375px width has no horizontal scroll and the minutes text is
  fully readable.
- Attendance counts for one councillor and one PPN representative, checked by
  hand against the six Meath meetings, match the page.
- No page shows minutes approval as a decision.

## Report back

Routes added, components and schemas, how attendance totals are computed,
screenshots at phone and desktop width, and anything in the data contract that
made the work harder. Send that last point back to `publicinformation-data`.
