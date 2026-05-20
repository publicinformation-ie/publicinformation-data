# Curated Topics Feature — Design Spec

**Date:** 2026-05-20  
**Status:** Approved  
**Repos affected:** `publicinformation-data`, `publicinformation-web`

---

## Overview

A keyword-driven "curated topics" feature that lets a curator maintain a short list of topic phrases. Each topic auto-matches FOI requests from the full dataset using OR keyword logic. Topics are displayed as a size-scaled word cloud on both the home page and a dedicated `/topics` index, and each topic links to a paginated page of matched FOI requests.

This is a fully static approach: all matching runs at pipeline/build time. No client-side search, no database.

---

## Data Pipeline (`publicinformation-data`)

### New step: `generate_topics`

Location: `foi_pipeline/steps/generate_topics/`

#### Input: `topics-config.json` (curator-maintained)

Hand-authored file committed alongside the step. Defines all topics.

```json
[
  {
    "slug": "housing",
    "label": "Housing",
    "keywords": ["housing", "rent", "homeless", "eviction"]
  },
  {
    "slug": "covid-contracts",
    "label": "Covid Contracts",
    "keywords": ["covid", "ppe", "pandemic", "procurement"]
  }
]
```

- `slug`: URL-safe identifier, used as the route segment for `/topics/[slug]`
- `label`: Display text, used in the word cloud chip and page heading
- `keywords`: One or more strings; a record matches if `request_description` contains **any** keyword (case-insensitive substring match, OR logic)

#### Processing (`process.py`)

1. Read `topics-config.json`
2. Read `../extract_disclosures_canonicalize/output.json` for the full set of FOI disclosures
3. For each topic, filter records where `request_description` contains any keyword (case-insensitive)
4. Sort matched records by `decision_date` descending (nulls last), consistent with existing sort behaviour
5. Write step-local `output.json`
6. Write `public/topics.json`

#### Output shape (`public/topics.json`)

```json
[
  {
    "slug": "housing",
    "label": "Housing",
    "keywords": ["housing", "rent", "homeless", "eviction"],
    "match_count": 42,
    "disclosures": [
      {
        "public_body_id": 1001,
        "name": "Department of Housing, Local Government and Heritage",
        "file_url": "https://...",
        "file_type": "xlsx",
        "foi_reference_id": "23/001",
        "decision_date": "2023-03-15T00:00:00",
        "requester_type": "Journalist",
        "decision_status": "Successful",
        "review_status": null,
        "related_request": null,
        "request_description": "All records relating to housing..."
      }
    ]
  }
]
```

Disclosures are embedded (denormalized) so the Astro site does not need to cross-reference `foi-disclosures.json` when building topic pages.

#### Step files

| File | Purpose |
|------|---------|
| `topics-config.json` | Curator-maintained topic definitions (committed to repo) |
| `process.py` | Matching logic, writes output.json and public/topics.json |
| `pipeline-status.json` | Standard step tracking (written by `write_status`) |
| `output.json` | Step-local output for pipeline introspection |
| `__init__.py` | Empty, required for Python package structure |

#### `pipeline.json`

Add `"generate_topics"` as the last entry, after `"export_status"`:

```json
{
  "steps": [
    "find_public_bodies",
    "resolve_website_urls",
    "validate_websites",
    "find_foi_pages",
    "check_foi_pages",
    "get_foi_emails",
    "find_disclosure_pages",
    "find_disclosure_files",
    "transform_disclosure_files",
    "extract_disclosures_detect_header_row",
    "extract_disclosures_canonicalize",
    "export_status",
    "generate_topics"
  ]
}
```

---

## Web (`publicinformation-web`)

### Data layer

**`src/lib/fetchData.ts`** — add:

```ts
export interface Topic {
  slug: string;
  label: string;
  keywords: string[];
  match_count: number;
  disclosures: FoiDisclosure[];
}

export async function fetchTopics(): Promise<Topic[]> {
  const url = `${import.meta.env.DATA_BASE_URL}/topics.json`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to fetch topics: ${response.status}`);
  return response.json();
}
```

### New component: `TopicCloud.astro`

Location: `src/components/TopicCloud.astro`

Receives `topics: Topic[]`. Renders each topic as a clickable chip linking to `/topics/[slug]`. Chip `font-size` is set from one of 5 tiers based on `match_count` relative to the maximum count in the dataset. Tiers use the existing type scale tokens (`--text-body-xs` through `--text-s`). The component is used on both the home page and the `/topics` index page.

Sizing tiers (thresholds to be tuned once real data is available):

| Tier | Condition | Token |
|------|-----------|-------|
| 1 (smallest) | bottom 20% | `--text-body-xs` (14px) |
| 2 | 20–40% | `--text-body-s` (16px) |
| 3 | 40–60% | `--text-body` (19px) |
| 4 | 60–80% | `--text-s` (20px) |
| 5 (largest) | top 20% | `--text-m` (24px) |

Chips use `--color-primary` for the text colour and carry a hover underline. No background fill — the cloud reads as text, not a tag list.

### New pages

#### `/topics` (`src/pages/topics.astro`)

Fetches `topics.json` at build time. Renders:
- Page heading: "Topics"
- Brief descriptor: "Browse FOI requests by topic"  
- `TopicCloud` component with all topics

#### `/topics/[slug]` (`src/pages/topics/[slug].astro`)

`getStaticPaths()` fetches `topics.json` and generates one path per topic, passing `topic` as a prop (includes embedded disclosures).

Renders:
- Page heading: topic label
- Record count subtitle
- Paginated `FoiDisclosureList` — reuses the existing component unchanged
- `Pagination` component — reuses the existing component unchanged
- Page size: inherits `PAGE_SIZE` from `src/config/foi.ts`

#### Home page (`src/pages/index.astro`)

Fetches `topics.json` alongside existing data fetches. Adds a "Browse by Topic" section containing `TopicCloud`, placed after the existing hero/intro content and before the public bodies listing.

### Navigation

`src/components/AppNav.astro` — add a "Topics" nav link pointing to `/topics`.

---

## Data flow summary

```
topics-config.json (curator)
        +
extract_disclosures_canonicalize/output.json
        ↓
generate_topics/process.py
        ↓
public/topics.json
        ↓
Astro build (fetchTopics())
        ↓
/topics              → TopicCloud
/topics/[slug]       → FoiDisclosureList (paginated)
index.astro          → TopicCloud (home page section)
```

---

## What is intentionally out of scope

- Full-text search (no search index, no query input)
- AND logic for keywords (OR only, revisit once results are reviewed)
- Editorial text on topic pages (minimal design; add later if needed)
- Manual record pinning (keywords-only for now)
- Topic grouping or hierarchy
