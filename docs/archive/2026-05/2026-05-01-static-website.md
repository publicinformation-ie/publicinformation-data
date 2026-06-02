> **NOTE**: This document refers to the old `publicinfo-prototype` subdirectory structure.
> The website has been moved to the separate `publicinformation-web` repository at
> /Users/gingertechie/dev/publicinformation/publicinformation-web/
> 
> References to `publicinfo-prototype` in this document should be read as `../publicinformation-web`.

# Static Website Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a static Astro site listing Irish public bodies to Hetzner web hosting, triggered by Codeberg Actions CI/CD.

**Architecture:** A Python script fetches `public_bodies.csv` from Codeberg during each CI build and converts it to JSON; Astro consumes the JSON at build time to render a static list page; `lftp` deploys `dist/` to Hetzner via SFTP. The Astro project lives in a `publicinfo-prototype/` subdirectory of the existing `publicinformation-data` repo.

**Tech Stack:** Astro 4 (minimal template), Tailwind CSS, Python 3.11, pytest, Codeberg Actions (Forgejo), lftp, Hetzner web hosting (SFTP)

---

## Prerequisites — Already Complete

These were completed before the agent session:

- [x] Hetzner web hosting account exists with SFTP access
- [x] Codeberg repo: `https://codeberg.org/gingertechie/publicinformation-data`
- [x] Four secrets added to Codeberg repo:
  - `HETZNER_SFTP_USERNAME`
  - `HETZNER_SFTP_PASSWORD`
  - `HETZNER_SFTP_HOST`
  - `HETZNER_SFTP_PATH`

---

## Automated Tasks — Agent runs these sequentially

All paths are relative to the repo root `/Users/gingertechie/dev/publicinformation-data/` unless noted.
The Astro project root is `/Users/gingertechie/dev/publicinformation-data/publicinfo-prototype/`.

---

### Task 1: Scaffold Astro Project

> **Model:** haiku

**Files:**
- Create: `publicinfo-prototype/` (Astro project subdirectory)
- Create: `publicinfo-prototype/package.json`, `publicinfo-prototype/astro.config.mjs`, `publicinfo-prototype/tailwind.config.mjs`
- Create: `publicinfo-prototype/.gitignore`

- [ ] **Step 1: Scaffold the Astro project**

  Run from the repo root `/Users/gingertechie/dev/publicinformation-data/`:

  ```bash
  npm create astro@latest publicinfo-prototype -- --template minimal --no-git --install --yes
  ```

  Expected: directory `publicinfo-prototype/` created with `src/pages/index.astro`, `package.json`, `astro.config.mjs`.

  > If the command prompts interactively: TypeScript = No, git = No, install deps = Yes.

- [ ] **Step 2: Add Tailwind CSS integration**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype && npx astro add tailwind --yes
  ```

  Expected: `tailwind.config.mjs` created, `astro.config.mjs` updated with `@astrojs/tailwind`.

- [ ] **Step 3: Verify the project builds**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype && npm run build
  ```

  Expected: exits 0, `dist/index.html` exists.

- [ ] **Step 4: Create data and scripts directories**

  ```bash
  mkdir -p /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype/src/data
  mkdir -p /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype/scripts
  ```

- [ ] **Step 5: Create .gitignore inside the Astro project**

  Create `publicinfo-prototype/.gitignore`:

  ```
  dist/
  node_modules/
  .astro/
  .env
  __pycache__/
  *.pyc
  .pytest_cache/
  ```

- [ ] **Step 6: Commit the scaffold**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data
  git add publicinfo-prototype/
  git commit -m "chore: scaffold Astro project with Tailwind"
  ```

---

### Task 2: Write CSV→JSON Conversion Script

> **Model:** sonnet — error handling and fallback logic requires careful reasoning

**Files:**
- Create: `publicinfo-prototype/scripts/csv_to_json.py`
- Create: `publicinfo-prototype/scripts/test_csv_to_json.py`

- [ ] **Step 1: Write the failing test first**

  Create `publicinfo-prototype/scripts/test_csv_to_json.py`:

  ```python
  import json
  import pytest
  from unittest.mock import patch, MagicMock
  from pathlib import Path
  import sys

  sys.path.insert(0, str(Path(__file__).parent))

  from csv_to_json import convert_csv_to_json

  SAMPLE_CSV = (
      "public_body_id,public_body_name,public_body_short_name,"
      "public_body_url,public_body_category,last_checked,last_modified
"
      "1001,\"Department of Agriculture, Food and the Marine\",DAFM,"
      "https://www.gov.ie/en/organisation/dafm/,government department,2026-04-27,2026-04-27
"
      "1002,Department of Finance,DOF,"
      "https://www.gov.ie/en/organisation/dof/,government department,2026-04-27,2026-04-27
"
  )


  def test_converts_csv_to_json(tmp_path):
      out = tmp_path / "public_bodies.json"
      with patch("csv_to_json.requests.get") as mock_get, \
           patch("csv_to_json.OUTPUT_PATH", str(out)):
          mock_get.return_value.text = SAMPLE_CSV
          mock_get.return_value.raise_for_status = MagicMock()
          convert_csv_to_json()

      data = json.loads(out.read_text())
      assert len(data) == 2
      assert data[0]["public_body_id"] == 1001
      assert data[0]["public_body_name"] == "Department of Agriculture, Food and the Marine"
      assert data[0]["public_body_url"] == "https://www.gov.ie/en/organisation/dafm/"


  def test_writes_empty_list_on_network_error(tmp_path):
      out = tmp_path / "public_bodies.json"
      with patch("csv_to_json.requests.get") as mock_get, \
           patch("csv_to_json.OUTPUT_PATH", str(out)):
          mock_get.side_effect = Exception("network error")
          convert_csv_to_json()

      data = json.loads(out.read_text())
      assert data == []


  def test_writes_empty_list_on_missing_columns(tmp_path):
      out = tmp_path / "public_bodies.json"
      with patch("csv_to_json.requests.get") as mock_get, \
           patch("csv_to_json.OUTPUT_PATH", str(out)):
          mock_get.return_value.text = "wrong,columns
foo,bar
"
          mock_get.return_value.raise_for_status = MagicMock()
          convert_csv_to_json()

      data = json.loads(out.read_text())
      assert data == []
  ```

- [ ] **Step 2: Run test to confirm it fails**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype && pip install pytest requests --quiet && pytest scripts/test_csv_to_json.py -v
  ```

  Expected: `ModuleNotFoundError: No module named 'csv_to_json'`

- [ ] **Step 3: Write the implementation**

  Create `publicinfo-prototype/scripts/csv_to_json.py`:

  ```python
  import csv
  import io
  import json
  import sys
  import requests

  CSV_URL = "https://codeberg.org/gingertechie/publicinformation-data/raw/branch/main/public_bodies.csv"
  OUTPUT_PATH = "src/data/public_bodies.json"

  REQUIRED_COLUMNS = {
      "public_body_id",
      "public_body_name",
      "public_body_short_name",
      "public_body_url",
      "public_body_category",
  }


  def convert_csv_to_json():
      try:
          response = requests.get(CSV_URL, timeout=30)
          response.raise_for_status()
          reader = csv.DictReader(io.StringIO(response.text))
          rows = list(reader)

          if not rows or not REQUIRED_COLUMNS.issubset(set(rows[0].keys())):
              print(
                  f"Warning: CSV missing required columns. Found: {list(rows[0].keys()) if rows else 'none'}",
                  file=sys.stderr,
              )
              _write([], OUTPUT_PATH)
              return

          records = [
              {
                  "public_body_id": int(row["public_body_id"]) if row["public_body_id"].isdigit() else row["public_body_id"],
                  "public_body_name": row["public_body_name"],
                  "public_body_short_name": row["public_body_short_name"],
                  "public_body_url": row["public_body_url"],
                  "public_body_category": row["public_body_category"],
              }
              for row in rows
          ]
          _write(records, OUTPUT_PATH)
          print(f"Wrote {len(records)} records to {OUTPUT_PATH}")

      except Exception as exc:
          print(f"Error fetching/parsing CSV: {exc}", file=sys.stderr)
          _write([], OUTPUT_PATH)


  def _write(data, path):
      with open(path, "w", encoding="utf-8") as f:
          json.dump(data, f, indent=2, ensure_ascii=False)


  if __name__ == "__main__":
      convert_csv_to_json()
  ```

- [ ] **Step 4: Run tests to confirm they pass**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype && pytest scripts/test_csv_to_json.py -v
  ```

  Expected:
  ```
  PASSED scripts/test_csv_to_json.py::test_converts_csv_to_json
  PASSED scripts/test_csv_to_json.py::test_writes_empty_list_on_network_error
  PASSED scripts/test_csv_to_json.py::test_writes_empty_list_on_missing_columns
  ```

- [ ] **Step 5: Commit**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data
  git add publicinfo-prototype/scripts/
  git commit -m "feat: add CSV to JSON conversion script with tests"
  ```

---

### Task 3: Generate Initial Data File

> **Model:** haiku

**Files:**
- Create: `publicinfo-prototype/src/data/public_bodies.json`

- [ ] **Step 1: Run the conversion script**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype && python scripts/csv_to_json.py
  ```

  Expected: `Wrote N records to src/data/public_bodies.json`

- [ ] **Step 2: Verify the output**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype && python -c "import json; d=json.load(open('src/data/public_bodies.json')); print(f'{len(d)} records, first: {d[0][\"public_body_name\"]}')"
  ```

  Expected: `145 records, first: Department of Agriculture, Food and the Marine` (count may vary)

- [ ] **Step 3: Commit the data file**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data
  git add publicinfo-prototype/src/data/public_bodies.json
  git commit -m "chore: add initial public bodies data (generated from CSV)"
  ```

---

### Task 4: Create Layout Component

> **Model:** haiku

**Files:**
- Create: `publicinfo-prototype/src/layouts/Layout.astro`

- [ ] **Step 1: Create the layouts directory and write Layout.astro**

  ```bash
  mkdir -p /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype/src/layouts
  ```

  Create `publicinfo-prototype/src/layouts/Layout.astro`:

  ```astro
  ---
  interface Props {
    title: string;
  }
  const { title } = Astro.props;
  ---
  <!DOCTYPE html>
  <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <meta name="description" content="List of public bodies in Ireland subject to Freedom of Information." />
      <title>{title}</title>
    </head>
    <body class="bg-white text-gray-900 min-h-screen">
      <slot />
    </body>
  </html>
  ```

- [ ] **Step 2: Commit**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data
  git add publicinfo-prototype/src/layouts/Layout.astro
  git commit -m "feat: add base Layout component"
  ```

---

### Task 5: Create Index Page

> **Model:** haiku

**Files:**
- Modify: `publicinfo-prototype/src/pages/index.astro`

- [ ] **Step 1: Write index.astro**

  Replace `publicinfo-prototype/src/pages/index.astro` with:

  ```astro
  ---
  import Layout from '../layouts/Layout.astro';
  import bodies from '../data/public_bodies.json';
  ---
  <Layout title="Public Bodies in Ireland">
    <main class="max-w-4xl mx-auto px-4 py-8">
      <h1 class="text-3xl font-bold mb-2">Public Bodies in Ireland</h1>
      <p class="text-gray-500 mb-8">{bodies.length} bodies listed</p>

      {bodies.length > 0 ? (
        <ul class="space-y-3">
          {bodies.map((body) => (
            <li class="border rounded-lg p-4 hover:bg-gray-50 transition-colors">
              <div class="flex items-start justify-between gap-4">
                <div>
                  <a
                    href={body.public_body_url || '#'}
                    class="text-lg font-semibold text-blue-700 hover:underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {body.public_body_name}
                  </a>
                  {body.public_body_short_name && (
                    <span class="ml-2 text-sm text-gray-500">({body.public_body_short_name})</span>
                  )}
                </div>
                <span class="text-xs text-gray-400 whitespace-nowrap capitalize shrink-0">
                  {body.public_body_category}
                </span>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p class="text-gray-500">No public bodies data available.</p>
      )}
    </main>
  </Layout>
  ```

- [ ] **Step 2: Build to verify no errors**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype && npm run build
  ```

  Expected: exits 0, `dist/index.html` exists.

- [ ] **Step 3: Confirm data was rendered into HTML**

  ```bash
  grep -c "gov.ie" /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype/dist/index.html
  ```

  Expected: a number greater than 0.

- [ ] **Step 4: Commit**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data
  git add publicinfo-prototype/src/pages/index.astro
  git commit -m "feat: add public bodies list page"
  ```

---

### Task 6: Verify Local Build

> **Model:** haiku

**Files:** no changes — verification only

- [ ] **Step 1: Clean and rebuild**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype && rm -rf dist && npm run build
  ```

  Expected: exits 0.

- [ ] **Step 2: Confirm exactly one HTML page was generated**

  ```bash
  find /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype/dist -name "*.html" | wc -l
  ```

  Expected: `1` (index.html only — no detail pages per spec).

- [ ] **Step 3: Confirm the page has content**

  ```bash
  wc -c /Users/gingertechie/dev/publicinformation-data/publicinfo-prototype/dist/index.html
  ```

  Expected: at least 10000 bytes.

---

### Task 7: Create Codeberg Actions Workflow

> **Model:** sonnet — CI/CD YAML with multi-step pipeline and SFTP deployment requires careful reasoning

**Files:**
- Create: `.codeberg/workflows/deploy.yml`

> **Note:** The workflow file lives at the repo root (`.codeberg/workflows/`), not inside `publicinfo-prototype/`. All build steps use `working-directory: publicinfo-prototype` so paths within those steps are relative to the Astro project.

- [ ] **Step 1: Create the workflows directory**

  ```bash
  mkdir -p /Users/gingertechie/dev/publicinformation-data/.codeberg/workflows
  ```

- [ ] **Step 2: Write the workflow**

  Create `.codeberg/workflows/deploy.yml`:

  ```yaml
  name: Build and Deploy to Hetzner

  on:
    push:
      branches: [main]
      paths:
        - 'publicinfo-prototype/src/**'
        - 'publicinfo-prototype/scripts/csv_to_json.py'
        - '.codeberg/workflows/deploy.yml'

  jobs:
    build-and-deploy:
      runs-on: ubuntu-latest

      steps:
        - name: Checkout repository
          uses: actions/checkout@v3

        - name: Set up Python 3.11
          uses: actions/setup-python@v4
          with:
            python-version: '3.11'

        - name: Install Python dependencies
          run: pip install requests

        - name: Generate JSON from CSV
          working-directory: publicinfo-prototype
          run: python scripts/csv_to_json.py

        - name: Verify JSON was generated
          working-directory: publicinfo-prototype
          run: |
            if [ ! -f src/data/public_bodies.json ]; then
              echo "ERROR: public_bodies.json was not created" >&2
              exit 1
            fi
            echo "JSON file size: $(wc -c < src/data/public_bodies.json) bytes"

        - name: Set up Node.js 20
          uses: actions/setup-node@v3
          with:
            node-version: '20'

        - name: Install Node dependencies
          working-directory: publicinfo-prototype
          run: npm ci

        - name: Build Astro site
          working-directory: publicinfo-prototype
          run: npm run build

        - name: Deploy to Hetzner via SFTP
          working-directory: publicinfo-prototype
          env:
            SFTP_USER: ${{ secrets.HETZNER_SFTP_USERNAME }}
            SFTP_PASS: ${{ secrets.HETZNER_SFTP_PASSWORD }}
            SFTP_HOST: ${{ secrets.HETZNER_SFTP_HOST }}
            SFTP_PATH: ${{ secrets.HETZNER_SFTP_PATH }}
          run: |
            sudo apt-get update -qq && sudo apt-get install -y -qq lftp
            lftp -u "$SFTP_USER,$SFTP_PASS" "sftp://$SFTP_HOST" <<LFTP_SCRIPT
            set sftp:auto-confirm yes
            set net:timeout 30
            mirror -R --delete --verbose ./dist/ $SFTP_PATH
            bye
            LFTP_SCRIPT
  ```

  > **Note on `mirror -R --delete`:** Removes files from Hetzner that no longer exist in `dist/`, keeping the server in sync. Remove `--delete` if you prefer to keep old files.

- [ ] **Step 3: Commit**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data
  git add .codeberg/workflows/deploy.yml
  git commit -m "ci: add Codeberg Actions build and SFTP deploy workflow"
  ```

---

### Task 8: Push to Codeberg

> **Model:** haiku

**Files:** no new files

- [ ] **Step 1: Show commit log**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data && git log --oneline -8
  ```

  Expected: at least 6 new commits visible (scaffold, script, data, layout, page, workflow).

- [ ] **Step 2: Push**

  ```bash
  cd /Users/gingertechie/dev/publicinformation-data && git push
  ```

  Expected: push succeeds.

- [ ] **Step 3: Confirm workflow triggered**

  Visit `https://codeberg.org/gingertechie/publicinformation-data/actions` and confirm the **Build and Deploy to Hetzner** workflow is running or queued.

---

## Deployment Verification Checklist

After the workflow completes successfully:

- [ ] The Codeberg Actions run shows green (all steps pass)
- [ ] The Hetzner hosting URL loads the public bodies list
- [ ] The page shows `N bodies listed` (where N > 0)
- [ ] Clicking a body name opens the correct government URL
- [ ] Page renders correctly on mobile (Tailwind responsive layout)

---

## Key Implementation Notes

| Detail | Value |
|--------|-------|
| CSV source URL | `https://codeberg.org/gingertechie/publicinformation-data/raw/branch/main/public_bodies.csv` |
| CSV columns used | `public_body_id`, `public_body_name`, `public_body_short_name`, `public_body_url`, `public_body_category` |
| Data pipeline | Option B: automated CSV→JSON during CI build (no manual JSON commits) |
| Workflow location | `.codeberg/workflows/deploy.yml` (repo root) |
| Astro project location | `publicinfo-prototype/` (subdirectory of existing repo) |
| All workflow build steps | Use `working-directory: publicinfo-prototype` |
