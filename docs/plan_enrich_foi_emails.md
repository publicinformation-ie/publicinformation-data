# Plan: Enrich public_body_foi_details.csv with FOI Email Addresses from foi.gov.ie

## Overview

This plan outlines the approach to enrich the `public_body_foi_details.csv` file with FOI email addresses scraped from [foi.gov.ie/all-foi-bodies](https://foi.gov.ie/all-foi-bodies). The foi.gov.ie website maintains a comprehensive and up-to-date list of all FOI bodies in Ireland, including their official FOI contact email addresses.

## Current State

- **Source**: `public_body_foi_details.csv` contains public body IDs, names, FOI contact emails, disclosure page URLs, and timestamps
- **Problem**: Many entries have missing or empty `foi_contact_email` values (approximately 40% based on initial review)
- **Opportunity**: foi.gov.ie provides authoritative FOI contact information for all public bodies

## Proposed Solution

### Option A: Create New Script (Recommended)

Create a new script `scripts/enrich_foi_emails_from_gov_portal.py` that:

1. Scrapes foi.gov.ie/all-foi-bodies to get the complete list of FOI body pages
2. Visits each FOI body page to extract the organization name and email address
3. Matches these entries with our existing `public_body_foi_details.csv` based on name similarity
4. Updates the CSV with missing email addresses
5. Refactors common code from existing scripts (`get_foi_contact_info.py`, `get_foi_pages_for_public_bodies.py`)

### Option B: Extend Existing Script

Extend `get_foi_contact_info.py` to add a new mode for scraping foi.gov.ie. However, this would:
- Mix two different data sources (individual public body websites vs. central FOI portal)
- Make the script more complex and harder to maintain
- Not follow single-responsibility principle

**Decision**: Option A (new script) is recommended for clarity and maintainability.

---

## Detailed Plan for New Script

### Script Name
`scripts/enrich_foi_emails_from_gov_portal.py`

### Inputs
- `public_body_foi_details.csv` - Current FOI details (required)
- `--output-file` - Path to write updated CSV (required)
- `--force-update` - Reprocess all rows, not just those with missing emails (optional, default: False)
- `--rate-limit` - Delay between requests in seconds (optional, default: 0.2)

### Output
Updated CSV with:
- Missing `foi_contact_email` fields populated from foi.gov.ie
- `last_checked` date updated to today
- `last_modified` date updated when email is added/changed

### Workflow

1. **Load existing data**
   - Read `public_body_foi_details.csv`
   - Identify rows with missing or empty `foi_contact_email`
   - Create lookup dictionary by `public_body_id` for quick access

2. **Scrape foi.gov.ie/all-foi-bodies**
   - Fetch the main page
   - Parse HTML to extract all FOI body links (in `<a href="/foi_units/...">` tags)
   - Store mapping of organization names to URLs

3. **Scrape individual FOI body pages**
   - For each FOI body URL from step 2:
     - Fetch the page
     - Parse the table to extract:
       - Organization name (from "Organisation:" row)
       - Email address (from "Email:" row, mailto link)
     - Store in a dictionary: `{normalized_name: email}`

4. **Match and enrich**
   - For each public body in our CSV:
     - If `foi_contact_email` is empty or `--force-update` is True:
       - Normalize the public body name (lowercase, remove punctuation, standardize abbreviations)
       - Find best match in foi.gov.ie data using fuzzy matching
       - If good match found (confidence > 90%), update email
       - Log mismatches and failures for manual review

5. **Write output**
   - Write updated data to output CSV
   - Preserve all existing columns
   - Update `last_checked` to today's date
   - Update `last_modified` if email was added/changed

### Name Matching Strategy

To handle variations in naming between our CSV and foi.gov.ie:

1. **Normalization function**:
   ```python
   def normalize_name(name):
       # Convert to lowercase
       # Remove punctuation (except hyphens and ampersands)
       # Expand common abbreviations (e.g., "Dept" -> "Department")
       # Remove "The", "An" prefixes
       # Standardize spacing
   ```

2. **Matching algorithm**:
   - First try: Exact match on normalized name
   - Second try: Fuzzy match using `difflib.get_close_matches()` or `fuzzywuzzy`
   - Third try: Partial string matching (if one name contains the other)
   - Fourth try: Token-based matching (Jaccard similarity on word sets)
   - Manual review for matches below 90% confidence

3. **Special cases to handle**:
   - Department name variations (e.g., "Department of Health" vs "Department of Health (DoH)")
   - Irish language names (e.g., "An Garda Síochána" vs "Garda Siochana")
   - Acronyms and abbreviations
   - Recent name changes (e.g., department mergers)

### Common Code Refactoring

Extract shared functionality into a new module `scripts/common/utils.py`:

1. **HTTP utilities**:
   - `_request()` with SSL fallback (already exists in both scripts)
   - Rate limiting helper
   - User-Agent headers

2. **CSV utilities**:
   - Load/save CSV with consistent encoding
   - Date handling for `last_checked` and `last_modified`

3. **HTML parsing utilities**:
   - Common BeautifulSoup patterns
   - Email extraction from text and mailto links

4. **Name normalization**:
   - Shared normalization function for matching

### Error Handling and Logging

1. **Logging levels**:
   - INFO: Progress updates (e.g., "Processing X of Y")
   - WARNING: Low-confidence matches, skipped items
   - ERROR: Failed requests, parsing errors

2. **Output files**:
   - Main output: Updated CSV
   - Log file: `enrich_foi_emails.log` with timestamp
   - Mismatch report: `foi_email_mismatches.csv` for manual review

3. **Statistics**:
   - Total rows processed
   - Emails added
   - Emails updated
   - Matches failed (with reasons)

### Testing Strategy

1. **Unit tests** (in `scripts/test_enrich_foi_emails.py`):
   - Name normalization function
   - Matching algorithm with known test cases
   - HTML parsing for email extraction
   - CSV reading/writing

2. **Integration tests**:
   - Run against a small subset of data
   - Verify output format and content
   - Test with mocked HTTP responses

3. **Manual verification**:
   - Spot-check a sample of updated emails against foi.gov.ie
   - Review mismatch report

### Rate Limiting and Performance

- Default delay: 0.2 seconds between requests (5 requests/second)
- Estimated time for ~300 FOI bodies: ~60 seconds
- Option to adjust rate limit via command line
- Consider caching responses for development/testing

### Command Line Interface

```bash
# Update only missing emails
python scripts/enrich_foi_emails_from_gov_portal.py \
    --input-file public_body_foi_details.csv \
    --output-file public_body_foi_details_updated.csv

# Force update all emails
python scripts/enrich_foi_emails_from_gov_portal.py \
    --input-file public_body_foi_details.csv \
    --output-file public_body_foi_details_updated.csv \
    --force-update

# Custom rate limit
python scripts/enrich_foi_emails_from_gov_portal.py \
    --input-file public_body_foi_details.csv \
    --output-file public_body_foi_details_updated.csv \
    --rate-limit 0.5
```

---

## Implementation Steps

### Step 1: Create common utilities module
- Extract shared code from existing scripts
- Create `scripts/common/utils.py` with:
  - HTTP request helper with SSL fallback
  - Rate limiting
  - CSV helpers
  - Name normalization

### Step 2: Create the enrichment script
- Implement scraping logic for foi.gov.ie
- Implement name matching
- Implement CSV enrichment
- Add comprehensive logging

### Step 3: Create unit tests
- Test name normalization
- Test matching algorithm
- Test HTML parsing
- Test CSV operations

### Step 4: Manual testing
- Run against small subset
- Verify output
- Adjust matching thresholds as needed

### Step 5: Full run
- Run against complete dataset
- Review mismatch report
- Manually resolve ambiguous matches

### Step 6: Integration
- Add to documentation
- Consider adding to CI/CD pipeline for periodic updates

---

## Expected Challenges and Mitigations

| Challenge | Mitigation |
|-----------|------------|
| Name variations between datasets | Use fuzzy matching with manual review for low-confidence matches |
| Website rate limiting/blocking | Implement rate limiting, respect robots.txt, use proper User-Agent |
| SSL certificate issues | Use existing SSL fallback pattern from other scripts |
| Missing or malformed data on foi.gov.ie | Log errors, skip problematic entries, manual review |
| Duplicate entries | Use public_body_id as primary key, deduplicate before processing |
| Character encoding issues | Use UTF-8 consistently, handle encoding in HTTP responses |

---

## Success Criteria

1. All public bodies with FOI email addresses on foi.gov.ie have their email populated in our CSV
2. No false positives (incorrect email assignments)
3. Less than 5% of matches require manual review
4. Script runs successfully without errors
5. Performance: Completes within 2 minutes for full dataset

---

## Files to Create/Modify

### New Files
- `scripts/enrich_foi_emails_from_gov_portal.py` - Main enrichment script
- `scripts/test_enrich_foi_emails.py` - Unit tests
- `scripts/common/utils.py` - Shared utilities (if not already exists)

### Modified Files
- `public_body_foi_details.csv` - Updated with new email addresses

### Documentation Updates
- This plan document (already being created)
- Update README if one exists

---

## Next Steps

1. **Review this plan** - Ensure approach aligns with project goals
2. **Implement common utilities** - Extract shared code first
3. **Implement enrichment script** - Core functionality
4. **Test with sample data** - Validate approach
5. **Run full enrichment** - Populate missing emails
6. **Manual review** - Verify results, especially edge cases
7. **Commit changes** - Save updated data and scripts

---

## Questions for Review

Before proceeding with implementation, please confirm:

1. Is the new script approach (Option A) acceptable, or would you prefer extending an existing script?
2. Are there any existing naming conventions or patterns I should follow for the new script?
3. Should the script be added to any existing automation or CI/CD pipeline?
4. Are there any specific rate limiting requirements or constraints?
5. Should I create the `scripts/common/` directory for shared utilities, or is there an existing location for shared code?
6. Are there any specific logging or output file requirements?

---

*Plan created: 2026-04-30*
*Status: Pending review*
