> **NOTE**: This document refers to the old `publicinfo-prototype` subdirectory structure.
> The website has been moved to the separate `publicinformation-web` repository at
> /Users/gingertechie/dev/publicinformation/publicinformation-web/
> 
> References to `publicinfo-prototype` in this document should be read as `../publicinformation-web`.

# Public Information Static Site Prototype - Handoff Document

---

## **Project Overview**

**Goal:** Build a static website prototype using [public_bodies.csv](https://codeberg.org/gingertechie/publicinformation-data/raw/branch/main/public_bodies.csv) data, deployed via Codeberg Actions to Hetzner Static Hosting.

**Tech Stack:**

- **Static Site Generator:** [Astro](https://astro.build/) (Minimal theme + Tailwind CSS)
- **Data Source:** CSV → JSON (stored in repo)
- **Hosting:** Hetzner Static Hosting (EU-based, SFTP deployment)
- **CI/CD:** Codeberg Actions
- **Styling:** Tailwind CSS

**Requirements:**

- No dependency on non-EU services.
- Low traffic (<10 visitors/day).
- Rebuild only when source data changes.
- Fail gracefully if CSV fetch fails.
- Simple list page to display public bodies (no detail pages).
- Use SFTP for deployment to Hetzner.

---

## **Context**

- **Current Setup:** Strapi + Node.js backend, Python scripts for data ingestion.
- **Why Static?** Data changes infrequently; simpler and cheaper than a VPS.
- **User:** Solo developer (Dave Anderson) with Python/Django experience.
- **Hosting Constraints:** Hetzner Static Hosting (SFTP only, no SSH).

---

## **Implementation Plan**

---

### **1. Data Pipeline**

#### **Option A: Pre-convert CSV to JSON (Recommended)**

- Manually convert [public_bodies.csv](https://codeberg.org/gingertechie/publicinformation-data/raw/branch/main/public_bodies.csv) to JSON.
- Store as `/src/data/public_bodies.json` in the repo.
- Update JSON manually when CSV changes.

#### **Option B: Automated CSV → JSON (Fallback)**

If you prefer to automate the conversion during the build, use this script:

```python
# scripts/csv_to_json.py
import pandas as pd
import json

csv_url = "https://codeberg.org/gingertechie/publicinformation-data/raw/branch/main/public_bodies.csv"
try:
    df = pd.read_csv(csv_url)
    data = df.to_dict(orient="records")
    with open("src/data/public_bodies.json", "w") as f:
        json.dump(data, f, indent=2)
except Exception as e:
    print(f"Error fetching/parsing CSV: {e}")
    # Fail gracefully: Use a fallback empty JSON
    with open("src/data/public_bodies.json", "w") as f:
        json.dump([], f)
```

---

### **2. Astro Project Setup**

#### **Initialize Project**

Run these commands to set up the Astro project with Tailwind CSS:

```bash
npm create astro@latest publicinfo-prototype -- --template minimal
cd publicinfo-prototype
npm install
npx astro add tailwind
npm install
```

#### **Directory Structure**

```
publicinfo-prototype/
├── src/
│   ├── pages/
│   │   └── index.astro       # Main page (see below)
│   ├── layouts/
│   │   └── Layout.astro      # Base layout
│   └── data/
│       └── public_bodies.json # Data file (manually updated or generated)
├── scripts/
│   └── csv_to_json.py         # Only if using Option B
├── .codeberg/
│   └── workflows/
│       └── deploy.yml         # CI/CD workflow (see below)
└── package.json
```

---

#### **Astro Files**

`**src/layouts/Layout.astro`:**

```astro
---
import '../styles/global.css';
---
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width" />
    <title>{title}</title>
  </head>
  <body class="bg-white text-gray-900">
    <slot />
  </body>
</html>
```

`**src/pages/index.astro`:**

```astro
---
import Layout from '../layouts/Layout.astro';
const data = await import('../data/public_bodies.json');
const bodies = data.default;
---
<Layout title="Public Bodies in Ireland">
  <main class="max-w-4xl mx-auto p-6">
    <h1 class="text-3xl font-bold mb-6">Public Bodies in Ireland</h1>
    <div class="space-y-4">
      {bodies.length > 0 ? (
        bodies.map(body => (
          <div key={body.id || body.name} class="p-4 border rounded-lg hover:bg-gray-50">
            <h2 class="text-xl font-semibold">
              <a href={body.website_url || '#'} class="text-blue-600 hover:underline">
                {body.name}
              </a>
            </h2>
            {body.description && <p class="text-gray-600 mt-2">{body.description}</p>}
          </div>
        ))
      ) : (
        <p class="text-gray-500">No public bodies data available.</p>
      )}
    </div>
  </main>
</Layout>
```

---

### **3. Codeberg Actions Workflow**

#### **Workflow File: `.codeberg/workflows/deploy.yml**`

```yaml
name: Build and Deploy to Hetzner via SFTP

on:
  push:
    branches: [main]
    paths:
      - 'src/data/public_bodies.json'
      - 'src/**'
      - 'scripts/csv_to_json.py'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v3

      # Only if using Option B (CSV → JSON)
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Python dependencies
        run: pip install pandas

      - name: Convert CSV to JSON
        run: python scripts/csv_to_json.py

      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '22'

      - name: Install Astro dependencies
        run: npm install

      - name: Build Astro site
        run: npm run build

      - name: Deploy to Hetzner via SFTP
        run: |
          sudo apt-get update && sudo apt-get install -y lftp
          echo "${{ secrets.HETZNER_SFTP_PASSWORD }}" > sftp_password.txt
          chmod 600 sftp_password.txt
          lftp -e "set ftp:ssl-allow no; put -r ./dist/* -o /var/www/html/; bye" -u ${{ secrets.HETZNER_SFTP_USERNAME }},`cat sftp_password.txt` sftp://157.90.184.173
```

---

### **4. Hetzner Static Hosting Setup**

1. **Create a Static Hosting Instance:**
  - Log in to [Hetzner Robot](https://robot.hetzner.com/) (for Static Hosting).
  - Create a new **Static Hosting** instance and note the **SFTP credentials** (username and password).
2. **Add Secrets to Codeberg:**
  - Go to **Repository Settings → Secrets → Add Secret**.
  - Add the following secrets:
    - `HETZNER_SFTP_USERNAME`: Your Hetzner SFTP username (e.g., `u123456`).
    - `HETZNER_SFTP_PASSWORD`: Your SFTP password.
3. **Deployment Path:**
  - The workflow uploads files to `/var/www/html/` on the Hetzner server. Ensure this is the correct path for your Static Hosting instance.

---

### **5. Deployment Steps**

1. **Set up Hetzner Static Hosting** and note the SFTP credentials.
2. **Add `HETZNER_SFTP_USERNAME` and `HETZNER_SFTP_PASSWORD**` to Codeberg Secrets.
3. **Convert CSV to JSON** (Option A) or include `csv_to_json.py` (Option B).
4. **Push to Codeberg** (`main` branch).
5. **Monitor Codeberg Actions** for the workflow run.
6. **Verify deployment** at your Hetzner Static Hosting URL.

---

## **Open Questions for Implementer**

1. **CSV Columns:** Confirm the column names in `public_bodies.csv` (e.g., `id`, `name`, `website_url`, `description`). The Astro template assumes these columns exist. Adjust the template if your CSV uses different names.
2. **Hetzner Credentials:** Are the SFTP credentials for Hetzner ready? If not, who will provide them?
3. **Data Update Frequency:** How often does `public_bodies.csv` change? This determines whether to use Option A (manual JSON updates) or Option B (automated CSV → JSON).

---

## **Deliverables**

- Codeberg repo with:
  - Astro project (`src/`, `package.json`).
  - Data file (`src/data/public_bodies.json` or `scripts/csv_to_json.py`).
  - Codeberg Actions workflow (`.codeberg/workflows/deploy.yml`).
- Hetzner Static Hosting instance configured.
- Successful deployment with live URL.

---

## **Resources**

- [Astro Docs](https://docs.astro.build/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Codeberg Actions Docs](https://docs.codeberg.org/ci-cd/)
- [Hetzner Static Hosting](https://www.hetzner.com/web-hosting)
- [Hetzner Robot (Static Hosting Management)](https://robot.hetzner.com/)

---

## **Notes**

- The workflow uses `lftp` to deploy via SFTP. If `lftp` is unavailable, you can use `sftp` or `ncftpput` as alternatives.
- If the CSV fetch fails, the site will display *"No public bodies data available."*
- For local testing, run `npm run dev` and visit `http://localhost:3000`.
