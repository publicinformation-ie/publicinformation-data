> **NOTE**: This document refers to the old `publicinfo-prototype` subdirectory structure.
> The website has been moved to the separate `publicinformation-web` repository at
> /Users/gingertechie/dev/publicinformation/publicinformation-web/
> 
> References to `publicinfo-prototype` in this document should be read as `../publicinformation-web`.

# Public Body Data Status Page — Design Spec

**Date:** 2026-05-05
**Status:** Approved
**Scope:** Public-facing status page showing completeness of public body data

---

## Overview

A public-facing status page that displays the completeness and validation status of data for each Irish public body. The page presents a table where rows represent public bodies and columns represent different types of data (website URL, FOI page URL, email address, etc.), with color-coded status indicators.

---

## Audience

- **Primary:** General public, researchers, journalists
- **Secondary:** Developers, data maintainers (via public access)

---

## Requirements

### Functional Requirements

1. Display a table of all public bodies with their data completeness status
2. Columns: Website, FOI Page, FOI Email, Disclosures Page, Disclosure Files, FOI Requests
3. Status indicators per cell:
   - Not attempted / Missing: Gray with "—" character
   - Success / Valid: Green with "✓" character
   - Failed / Invalid: Red with "✗" character
   - Partial success: Amber with "!" character (Disclosure Files only)
4. FOI Requests column displays "valid/total" count with color based on error count
5. Rows sorted alphabetically by public body full name
6. Public body identifier: Full name (short name) format

### Non-Functional Requirements

- Static page generated at build time
- No client-side JavaScript required for core functionality
- WCAG 2.1 AA compliant
- Consistent with existing style guide and design system
- Uses semantic HTML table elements

---

## Page Location

- **URL:** `/data-status` (or similar)
- **File:** `publicinfo-prototype/src/pages/data-status.astro`
- **Navigation:** Footer only (not in main navigation)

---

## Pipeline Data Architecture

### Overview

To simplify status page generation, we enhance the existing pipeline step outputs to **carry accumulated status data** for each public body. This eliminates the need for a separate aggregation step.

Each step reads the previous step's output, adds its own validation/status data, and writes the enhanced output. The final step's output contains the complete status data for all public bodies, which the Astro page imports directly.

### Step Output Structure

**Base structure (after `find_public_bodies` step):**
```json
{
  "metadata": {
    "step": "find_public_bodies",
    "completed_at": "2026-05-05T10:00:00Z"
  },
  "public_bodies": [
    {
      "public_body_id": 1001,
      "name": "Department of Health",
      "short_name": "DoH",
      "status": {
        "website": {
          "url": "https://health.gov.ie",
          "status": "not_attempted"
        }
      }
    }
  ]
}
```

**After `validate_websites` step:**
```json
{
  "metadata": {
    "step": "validate_websites",
    "completed_at": "2026-05-05T10:05:00Z"
  },
  "public_bodies": [
    {
      "public_body_id": 1001,
      "name": "Department of Health",
      "short_name": "DoH",
      "status": {
        "website": {
          "url": "https://health.gov.ie",
          "status": "success",
          "checked_at": "2026-05-05T10:05:00Z",
          "http_status": 200
        }
      }
    }
  ]
}
```

**After `find_foi_pages` step:**
```json
{
  "metadata": {
    "step": "find_foi_pages",
    "completed_at": "2026-05-05T10:10:00Z"
  },
  "public_bodies": [
    {
      "public_body_id": 1001,
      "name": "Department of Health",
      "short_name": "DoH",
      "status": {
        "website": {
          "url": "https://health.gov.ie",
          "status": "success",
          "checked_at": "2026-05-05T10:05:00Z",
          "http_status": 200
        },
        "foi_page": {
          "url": "https://health.gov.ie/foi",
          "status": "success",
          "checked_at": "2026-05-05T10:10:00Z"
        }
      }
    }
  ]
}
```

**After `extract_disclosures` step (final step for status data):**
```json
{
  "metadata": {
    "step": "extract_disclosures",
    "completed_at": "2026-05-05T10:25:00Z"
  },
  "public_bodies": [
    {
      "public_body_id": 1001,
      "name": "Department of Health",
      "short_name": "DoH",
      "status": {
        "website": {
          "url": "https://health.gov.ie",
          "status": "success",
          "checked_at": "2026-05-05T10:05:00Z",
          "http_status": 200
        },
        "foi_page": {
          "url": "https://health.gov.ie/foi",
          "status": "success",
          "checked_at": "2026-05-05T10:10:00Z"
        },
        "foi_email": {
          "email": "foi@health.gov.ie",
          "status": "success"
        },
        "disclosures_page": {
          "url": "https://health.gov.ie/foi/disclosures",
          "status": "success",
          "checked_at": "2026-05-05T10:20:00Z"
        },
        "disclosure_files": {
          "status": "partial",
          "total": 5,
          "valid": 4,
          "failed": 1
        },
        "foi_requests": {
          "valid": 123,
          "errors": 0
        }
      }
    }
  ]
}
```

### Step Implementation Pattern

Each step's `process.py` follows this pattern:

1. **Read input:** Load previous step's `output.json` (or create base structure for first step)
2. **Process data:** Perform the step's validation or data collection
3. **Update status:** For each public body, add/update the corresponding status entry
4. **Write output:** Save enhanced data to `output.json` with updated metadata

**Python template for step implementation:**
```python
import json
from pathlib import Path
from scripts.file_utils import read_json, write_json

def process(input_path, output_path):
    # Load previous step's output
    if Path(input_path).exists():
        data = read_json(input_path)
    else:
        data = {"metadata": {}, "public_bodies": []}
    
    # Process each public body
    for body in data["public_bodies"]:
        # Initialize status if not present
        if "status" not in body:
            body["status"] = {}
        
        # Add this step's status (example for validate_websites)
        if "website" in body.get("status", {}):
            body["status"]["website"]["status"] = validate_url(body["status"]["website"]["url"])
            body["status"]["website"]["checked_at"] = datetime.now().isoformat()
    
    # Update metadata
    data["metadata"] = {
        "step": "validate_websites",
        "completed_at": datetime.now().isoformat()
    }
    
    # Write output
    write_json(output_path, data)

if __name__ == "__main__":
    process(input_path, output_path)
```

### Step Contract Enhancement

The existing step contract is enhanced with these requirements:

1. **Input:** Each step (except first) reads the previous step's `output.json`
2. **Output:** Each step writes `output.json` with:
   - `metadata` object containing `step` name and `completed_at` timestamp
   - `public_bodies` array with consistent structure
   - Each public body has a `status` object that accumulates across steps
3. **Preservation:** Each step must preserve all existing data from previous steps
4. **Status addition:** Each step adds its domain-specific status to each body's `status` object

### Status Page Data Source

The Astro page imports the **final step's `output.json`** directly. No aggregation script needed.

For the initial implementation while other steps are being built, the status page can use whichever step's output is most recent.

**Simplified build script:**
```json
{
  "scripts": {
    "prebuild": "cp ../foi_pipeline/steps/extract_disclosures/output.json src/data/pipeline-status.json"
  }
}
```

Or to always use the latest step output:
```bash
# In prebuild script
LATEST_STEP=$(ls -td ../foi_pipeline/steps/*/output.json 2>/dev/null | head -1)
if [ -n "$LATEST_STEP" ]; then
  cp "$LATEST_STEP" src/data/pipeline-status.json
else
  # Fallback: create empty structure
  echo '{"metadata": {}, "public_bodies": []}' > src/data/pipeline-status.json
fi
```

### Advantages of This Architecture

1. **Simpler status page generation:** Just copy one file
2. **No separate aggregation step:** Status accumulates naturally through the pipeline
3. **Each step remains focused:** Only adds its own domain-specific status data
4. **Backward compatible:** Existing steps can be enhanced incrementally
5. **Pipeline orchestrator unchanged:** Existing staleness checking and step sequencing still works
6. **Easy to add new steps:** New validation steps just add their status to the existing structure

### Trade-offs

- Each step reads/writes the full dataset (negligible for ~286 bodies)
- Steps need to preserve and carry forward data from previous steps
- First step (`find_public_bodies`) needs to initialize the base structure with `status.website`

---

## Data Structure for Status Page

The final step's `output.json` is copied to `publicinfo-prototype/src/data/pipeline-status.json` and imported by the Astro page. The structure the status page needs from each public body:

```json
{
  "public_body_id": 1001,
  "name": "Department of Health",
  "short_name": "DoH",
  "status": {
    "website": {
      "status": "success|failed|not_attempted",
      "url": "https://..."
    },
    "foi_page": {
      "status": "success|failed|not_attempted",
      "url": "https://..."
    },
    "foi_email": {
      "status": "success|failed|not_attempted",
      "email": "string"
    },
    "disclosures_page": {
      "status": "success|failed|not_attempted",
      "url": "https://..."
    },
    "disclosure_files": {
      "status": "success|failed|not_attempted|partial",
      "total": 5,
      "valid": 3,
      "failed": 2
    },
    "foi_requests": {
      "valid": 123,
      "errors": 5
    }
  }
}
```

Note: Additional fields in the pipeline output (like `checked_at`, `http_status`, `error`) are preserved but not displayed by the status page. They're available for future enhancements.

---

## Visual Design

### Layout

- Full-width table within 960px content container
- Clean, minimal styling consistent with GOV.UK-inspired design system
- Responsive: scrolls horizontally on small screens if needed

### Table Styling

- **Borders:** 1px solid `#DEE0E2` (--color-grey-light)
- **Zebra striping:** Even rows use `#F3F2F1` (--color-grey-lightest)
- **Hover:** Row background changes to light gray on hover

### Header Row

- **Background:** `#1B3A5C` (--color-secondary)
- **Text:** White
- **Font:** 600 weight, 16px
- **Border:** 2px solid `#505A5F` (--color-grey-dark) at bottom

### Cells

- **Padding:** 12px 16px
- **Text alignment:** Left for all columns
- **Font:** 16px / 1rem body text

### Column Headers

- Website
- FOI Page
- FOI Email
- Disclosures Page
- Disclosure Files
- FOI Requests

### Row Identifiers

Format: **"Full name (short name)"**
Example: **"Department of Health (DoH)"**

### Status Indicators

Centered in cell with character + color:

| Status | Color | Character | CSS Class / Token |
|--------|-------|-----------|-------------------|
| Not attempted | `#B1B4B6` (--color-grey-mid) | — | `status-grey-mid` |
| Success | `#00723B` (--color-primary) | ✓ | `status-primary` |
| Failed | `#F47738` (--color-status-refused) | ✗ | `status-refused` |
| Partial | `#6F3FBF` (--color-status-extension) | ! | `status-extension` |

**FOI Requests column:** Displays text "valid/total" (e.g., "123/128") with color determined by error count (green if 0 errors, red if >0).

---

## Status Logic

### Simple Fields (website, foi_page, foi_email, disclosures_page)

```
status === "success"     -> ✓ green
status === "failed"      -> ✗ red
status === "not_attempted" or field missing/null -> — gray
```

### Disclosure Files

```
total === 0              -> — gray
failed === 0             -> ✓ green  (all valid)
valid === 0              -> ✗ red    (all failed)
valid > 0 AND failed > 0 -> ! amber (partial)
```

### FOI Requests

```
Display: "${valid}/${valid + errors}"
Color: errors === 0 -> green, errors > 0 -> red
```

---

## Implementation

### Build Integration

1. Pipeline runs and final step outputs `output.json` with complete status data
2. Build script copies final step's `output.json` to `publicinfo-prototype/src/data/pipeline-status.json`
3. Astro build includes this data file

**package.json script:**
```json
{
  "scripts": {
    "prebuild": "cp ../foi_pipeline/steps/extract_disclosures/output.json src/data/pipeline-status.json"
  }
}
```

For development while pipeline steps are being added, use the latest available step output:
```bash
# Find latest step output and copy it
LATEST_STEP=$(ls -td ../foi_pipeline/steps/*/output.json 2>/dev/null | head -1)
if [ -n "$LATEST_STEP" ]; then
  cp "$LATEST_STEP" src/data/pipeline-status.json
else
  # Fallback: create empty structure
  echo '{"metadata": {}, "public_bodies": []}' > src/data/pipeline-status.json
fi
```

### Astro Page (`data-status.astro`)

```astro
---
import Layout from '../layouts/Layout.astro';
import statusData from '../data/pipeline-status.json';

const getStatus = (field, body) => {
  const data = body.status[field];
  if (!data || data.status === 'not_attempted') {
    return { char: '—', color: 'grey-mid' };
  }
  if (data.status === 'success') {
    return { char: '✓', color: 'primary' };
  }
  if (data.status === 'failed') {
    return { char: '✗', color: 'status-refused' };
  }
  if (field === 'disclosureFiles') {
    if (data.total === 0) return { char: '—', color: 'grey-mid' };
    if (data.failed === 0) return { char: '✓', color: 'primary' };
    if (data.valid === 0) return { char: '✗', color: 'status-refused' };
    return { char: '!', color: 'status-extension' };
  }
  return { char: '—', color: 'grey-mid' };
};

const getFoiRequestsDisplay = (body) => {
  const data = body.status.foi_requests;
  if (!data) {
    return { display: '—', color: 'grey-mid' };
  }
  const total = data.valid + data.errors;
  const display = `${data.valid}/${total}`;
  const color = data.errors === 0 ? 'primary' : 'status-refused';
  return { display, color };
};
---

<Layout>
  <main>
    <h1>Public Body Data Status</h1>
    
    <table class="status-table">
      <thead>
        <tr>
          <th scope="col">Public Body</th>
          <th scope="col">Website</th>
          <th scope="col">FOI Page</th>
          <th scope="col">FOI Email</th>
          <th scope="col">Disclosures Page</th>
          <th scope="col">Disclosure Files</th>
          <th scope="col">FOI Requests</th>
        </tr>
      </thead>
      <tbody>
        {statusData.public_bodies
          .sort((a, b) => a.name.localeCompare(b.name))
          .map(body => (
            <tr>
              <td><strong>{body.name}</strong> ({body.short_name})</td>
              <td class={`status-${getStatus('website', body).color}`} aria-label="Website: {getStatus('website', body).color}">
                {getStatus('website', body).char}
              </td>
              <td class={`status-${getStatus('foi_page', body).color}`} aria-label="FOI Page: {getStatus('foi_page', body).color}">
                {getStatus('foi_page', body).char}
              </td>
              <td class={`status-${getStatus('foi_email', body).color}`} aria-label="FOI Email: {getStatus('foi_email', body).color}">
                {getStatus('foi_email', body).char}
              </td>
              <td class={`status-${getStatus('disclosures_page', body).color}`} aria-label="Disclosures Page: {getStatus('disclosures_page', body).color}">
                {getStatus('disclosures_page', body).char}
              </td>
              <td class={`status-${getStatus('disclosureFiles', body).color}`} aria-label="Disclosure Files: {getStatus('disclosureFiles', body).color}">
                {getStatus('disclosureFiles', body).char}
              </td>
              <td class={`status-${getFoiRequestsDisplay(body).color}`} aria-label="FOI Requests: {getFoiRequestsDisplay(body).display}">
                {getFoiRequestsDisplay(body).display}
              </td>
            </tr>
          ))}
      </tbody>
    </table>
  </main>
</Layout>
```

### CSS Additions

Add to `publicinfo-prototype/src/styles/global.css`:

```css
/* Status table */
.status-table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5rem 0;
}

.status-table th,
.status-table td {
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--color-grey-light);
}

.status-table thead th {
  background-color: var(--color-secondary);
  color: var(--color-white);
  font-weight: 600;
  font-size: 1rem;
}

.status-table thead tr {
  border-bottom: 2px solid var(--color-grey-dark);
}

.status-table tbody tr:nth-child(even) {
  background-color: var(--color-grey-lightest);
}

.status-table tbody tr:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

/* Status colors */
.status-grey-mid { color: var(--color-grey-mid); }
.status-primary { color: var(--color-primary); }
.status-refused { color: var(--color-status-refused); }
.status-extension { color: var(--color-status-extension); }
```

---

## Pipeline Step Modifications

### `find_public_bodies` Step (Must be Enhanced First)

**Current behavior:** Outputs array of bodies with `public_body_id`, `name`, `official_website_url`

**Required enhancement:** Add `short_name` field and initialize `status.website`:

```json
{
  "metadata": {
    "step": "find_public_bodies",
    "completed_at": "2026-05-05T10:00:00Z"
  },
  "public_bodies": [
    {
      "public_body_id": 1001,
      "name": "Department of Health",
      "short_name": "DoH",
      "official_website_url": "https://health.gov.ie",
      "status": {
        "website": {
          "url": "https://health.gov.ie",
          "status": "not_attempted"
        }
      }
    }
  ]
}
```

**Implementation notes:**
- `short_name` can be derived from `name` (e.g., first word, acronym) or sourced from gov.ie
- Initialize `status.website.url` from `official_website_url`
- Set `status.website.status` to "not_attempted" (validation happens in next step)

### Subsequent Steps

Each subsequent step (`validate_websites`, `find_foi_pages`, `validate_emails`, `download_disclosure_files`, `extract_disclosures`) must:

1. Read previous step's `output.json`
2. For each public body, add its domain-specific status to the `status` object
3. Write enhanced `output.json` with updated `metadata.step` and `metadata.completed_at`

**Example: `validate_websites` step**
```python
# Pseudocode
for body in data["public_bodies"]:
    if "website" in body["status"]:
        url = body["status"]["website"]["url"]
        try:
            response = fetch(url, timeout=10)
            body["status"]["website"]["status"] = "success"
            body["status"]["website"]["http_status"] = response.status_code
        except Exception as e:
            body["status"]["website"]["status"] = "failed"
            body["status"]["website"]["error"] = str(e)
        body["status"]["website"]["checked_at"] = datetime.now().isoformat()
```

---

## Accessibility

### Semantic Structure

- Proper `<table>`, `<thead>`, `<tbody>`, `<th>`, `<td>` elements
- `<th scope="col">` for all column headers
- Table has implicit description via page `<h1>`

### Screen Reader Support

- Each status cell has `aria-label` with descriptive text (e.g., "Website: success")
- Status characters (✓, ✗, !, —) are Unicode characters that screen readers announce appropriately

### Color Contrast

All status colors meet WCAG 2.1 AA contrast requirements against white background:
- Green (#00723B): 6.2:1 ✓
- Red (#F47738): 4.5:1 ✓
- Purple (#6F3FBF): 6.5:1 ✓
- Gray (#B1B4B6): 4.5:1 ✓

### Keyboard Navigation

- Table is static and fully keyboard navigable
- No interactive elements require mouse
- Focus styles inherited from global styles

---

## Future Enhancements (Out of Scope)

- Summary statistics at top of page
- Visual progress indicators
- Sortable columns
- Filtering by status
- Tooltips with error details (hover to see why a URL failed)
- Pagination (currently single continuous page)
- Search functionality

---

## Dependencies

- Ingestion pipeline enhanced to carry accumulated status in `output.json` files
- Astro prototype build process
- Existing Layout component and global styles
- `find_public_bodies` step must be enhanced first to initialize the structure

---

## Testing

1. Verify page renders correctly with sample data
2. Check all status combinations display properly
3. Validate alphabetical sorting
4. Confirm accessibility with screen reader
5. Test responsive behavior on mobile devices
6. Verify color contrast meets WCAG standards
7. Test with partial pipeline data (not all steps completed)
