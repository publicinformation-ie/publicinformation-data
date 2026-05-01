# Public Bodies in Ireland - Astro Prototype

A static website prototype for browsing Irish public bodies and their Freedom of Information (FOI) disclosure files.

## Project Overview

This Astro-based prototype provides:
- A browsable list of all Irish public bodies subject to FOI
- Individual detail pages for each public body showing:
  - Public Body Name and Short Name
  - Public Body URL (external link)
  - FOI Contact Email
  - FOI Disclosure Page URL
  - List of disclosure files with dates and download links

## Project Structure

```text
publicinfo-prototype/
├── src/
│   ├── data/
│   │   ├── public_bodies.json          # Simple list for home page
│   │   └── public_bodies_detailed.json # Full data for detail pages
│   ├── layouts/
│   │   └── Layout.astro                # Shared layout with header
│   ├── pages/
│   │   ├── index.astro                 # Home page with body list
│   │   └── body/
│   │       └── [id].astro              # Dynamic detail page
│   └── styles/
│       └── global.css                  # Tailwind CSS
├── scripts/
│   ├── csv_to_json.py                  # Original: fetches public_bodies.csv
│   └── generate_body_data.py          # Merges all CSV data sources
├── public/                            # Static assets
└── package.json
```

## Data Sources

The prototype uses CSV data files from the parent `publicinformation-data` directory:
- `public_bodies.csv` - Base public body information
- `public_body_foi_details.csv` - FOI contact emails and disclosure page URLs
- `public_body_foi_disclosure_files.csv` - Disclosure file URLs and dates

## Data Generation

To regenerate the JSON data files after updating CSV sources:

```bash
# Run the data merging script
python3 scripts/generate_body_data.py

# This will:
# 1. Merge all CSV files into src/data/public_bodies_detailed.json
# 2. Update src/data/public_bodies.json with the simple list
```

**Note:** The script expects CSV files to be in the parent directory (`../publicinformation-data/`).

## Commands

| Command | Action |
| :--- | :--- |
| `npm install` | Installs dependencies |
| `npm run dev` | Starts local dev server at `localhost:4321` |
| `npm run build` | Build production site to `./dist/` |
| `npm run preview` | Preview build locally before deploying |

## Learnings & Notes

### Session 1: Initial Setup
- Started with minimal Astro template
- Created basic home page listing public bodies from `public_bodies.csv`
- Used Tailwind CSS for styling (configured in `global.css`)

### Session 2: Adding Public Body View
- **Challenge:** Needed to merge data from multiple CSV files
  - Solution: Created `generate_body_data.py` script
  - Script uses Python's `csv` and `json` modules for clean data transformation
  - Groups disclosure files by `public_body_id` for efficient lookup

- **Astro Dynamic Routes:**
  - Created `src/pages/body/[id].astro` for detail pages
  - Must export `getStaticPaths()` function to pre-render all pages
  - Used `Object.values(bodies).map()` to generate paths for all 286 bodies

- **Data Fetching:**
  - Astro supports direct JSON imports: `import bodies from '../../data/public_bodies_detailed.json'`
  - No need for API endpoints - JSON is bundled at build time
  - All 286 pages are pre-generated as static HTML

- **Responsive Design:**
  - Desktop: Table layout for disclosure files
  - Mobile: Stacked card layout using Tailwind's responsive prefixes (`sm:`)
  - Used `hidden sm:block` and `sm:hidden` for layout switching

- **Layout Pattern:**
  - Shared `Layout.astro` with optional `showBackLink` prop
  - Avoids duplicating header across pages
  - Back navigation handled at layout level for consistency

### Future Improvements

- [ ] Add search/filter functionality on home page
- [ ] Implement pagination for disclosure files (currently shows all)
- [ ] Add sorting options for disclosure files (by date, name)
- [ ] Extract more metadata from disclosure file URLs (e.g., file type)
- [ ] Add caching headers for better performance
- [ ] Consider using Astro's `getStaticPaths` with pagination for very large datasets

### Data Quality Notes

- Some public bodies have no disclosure files (e.g., Department of Education and Youth)
- FOI email addresses are displayed as plain text (not links) to prevent scraping
- All external links open in new tabs with `target="_blank"` and `rel="noopener noreferrer"`
- Document names are extracted from URLs using `os.path.basename()`

## Deployment

The site can be deployed as static files to any hosting service:
- Netlify
- Vercel
- GitHub Pages
- Cloudflare Pages
- Bunny.net (current deployment target)

No server-side rendering required - all pages are pre-generated.
