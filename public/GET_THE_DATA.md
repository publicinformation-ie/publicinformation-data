# Get the Data

Downloadable spreadsheet files, one per dataset. Every file is a plain CSV
you can open in Excel, Google Sheets, or Numbers — no software beyond a
spreadsheet program is needed.

## [Public bodies](latest/public-bodies/public-bodies.csv)

Every public body in Ireland: its name, whether it handles Freedom of Information (FOI) requests, and its FOI contact email.

| Column | What it means |
|---|---|
| `name` | The public body's name |
| `foi_subject` | Whether this body handles FOI requests |
| `foi_email_email` | Their FOI contact email address |

## [FOI disclosures](latest/foi-disclosures/foi-disclosures.csv)

Records of information already released under FOI: what was asked, who asked (e.g. journalist, member of the public), when, and the outcome.

## [FOI request files](latest/foi-request-files/foi-request-files.csv)

The original source documents each disclosure record came from.

## [Who does what](latest/who-does-what/who-does-what.csv)

Links from each public body to its page on the Government's "Who Does What" directory.

## [data.gov.ie links](latest/data-gov-ie-links/data-gov-ie-links.csv)

Links from each public body to its organisation page on data.gov.ie, Ireland's open data portal.

## [lobbying.ie links](latest/lobbying-ie-links/lobbying-ie-links.csv)

Links from each public body to its page on lobbying.ie, Ireland's Register of Lobbying, with a point-in-time count of lobbying returns filed against it.

## [Public body actions](latest/public-body-actions/actions.csv)

The published commitments ("actions") of public bodies, taken from their strategy and action-plan documents, together with how each action's reported status changed in later progress reports.

| Column | What it means |
|---|---|
| `action_text` | The action as published |
| `plan_title` | The plan that declared the action |
| `original_deadline_start` | The plan's deadline, as a normalised date |
| `lead` | The organisation leading the action |

This dataset has three tables: [actions](latest/public-body-actions/actions.csv) (one row per published action), [status observations](latest/public-body-actions/action-status-observations.csv) (one row per progress report's update on an action), and [relationships](latest/public-body-actions/action-relationships.csv) (how actions relate to one another).

## [Motions](latest/motions/motions.csv)

Motions moved at meetings of Irish local authorities, from the authorities' published meeting minutes: who proposed and seconded each motion, the meeting date and type, and the outcome.

## Worked example: find a body's FOI contact email

1. Open [public-bodies.csv](latest/public-bodies/public-bodies.csv) in a spreadsheet program.
2. Search or filter the `name` column for the body you're interested in.
3. Read the `foi_email_email` column on that row — that's their FOI contact address.

---

Want the full technical details behind each file (every column, how the data was collected, what to watch out for)? See the [Public Bodies](latest/public-bodies/README.md), [FOI Disclosures](latest/foi-disclosures/README.md), [FOI Request Files](latest/foi-request-files/README.md), [Who Does What](latest/who-does-what/README.md), [data.gov.ie Links](latest/data-gov-ie-links/README.md), [lobbying.ie Links](latest/lobbying-ie-links/README.md), [Public Body Actions](latest/public-body-actions/README.md), and [Motions](latest/motions/README.md) reference pages.

Wondering how complete this data is, or found something that looks wrong? See [Data quality & reporting a problem](DATA_QUALITY.md).
