# Scripts

## admin-corrections.mjs

Interactive CLI for reviewing and actioning pending user-submitted corrections from the public API.

### Prerequisites

Copy `.env.admin.example` to `.env.admin` in the repo root and fill in the values:

```bash
cp .env.admin.example .env.admin
# edit .env.admin and set ADMIN_API_KEY
```

The script requires these three variables in `.env.admin`:

| Variable | Description |
|---|---|
| `CORRECTIONS_URL` | Base URL of the corrections API |
| `ADMIN_API_KEY` | Secret key for authenticating admin API requests |
| `SIGN_KARMA_URL` | URL of the karma-signing service |

The script also reads pipeline `output.json` files to enrich override records, so you should have a recent pipeline run locally before accepting corrections that involve `foi_email`, `disclosures_page`, or `foi_page` fields.

### Usage

```bash
node scripts/admin-corrections.mjs
```

### What it does

For each pending correction, you are shown:

- The public body name and ID
- The field being corrected (`website_url`, `foi_page`, `foi_email`, or `disclosures_page`)
- The current value and the user's suggested value
- The submitter's DID, IP address, and submission timestamp

You then choose:

- **`a` — Accept**: writes an override record to `foi_pipeline/steps/<step>/override.json`, signs +10 karma for the submitter, and marks the correction accepted in the API
- **`r` — Reject**: optionally provide a reason, marks the correction rejected in the API
- **`s` — Skip**: leaves the correction pending for later review

### After accepting corrections

The script prints the next steps, which are roughly:

```bash
git add foi_pipeline/steps/<step>/override.json
git commit -m "feat: accept correction for <field> (body <id>)"
git push
# re-run export_status step and redeploy pipeline data to CDN
```

Override files take effect when the pipeline is re-run — accepted corrections bypass the normal pipeline logic for that body/field combination.
