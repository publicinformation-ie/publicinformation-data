#!/usr/bin/env python3
"""
Generate consolidated JSON data for Public Body View pages.
Merges data from multiple CSV files:
- public_bodies.csv (base info)
- public_body_foi_details.csv (FOI email and disclosure page URL)
- public_body_foi_pages.csv (FOI page URL - currently not used per requirements)
- public_body_foi_disclosure_files.csv (disclosure files list)

Output: src/data/public_bodies_detailed.json
Structure: { public_body_id: { ...body data..., disclosure_files: [...] } }
"""

import csv
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from collections import defaultdict

# Path configuration
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "src" / "data"
INPUT_DIR = PROJECT_ROOT.parent  # publicinformation-data root

# Input CSV files
BODIES_CSV = INPUT_DIR / "public_bodies.csv"
FOI_DETAILS_CSV = INPUT_DIR / "public_body_foi_details.csv"
FOI_PAGES_CSV = INPUT_DIR / "public_body_foi_pages.csv"
DISCLOSURE_FILES_CSV = INPUT_DIR / "public_body_foi_disclosure_files.csv"

# Output JSON file
OUTPUT_JSON = DATA_DIR / "public_bodies_detailed.json"


def extract_filename_from_url(url):
    """Extract filename from URL path."""
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path
    return os.path.basename(path) if path else ""


def load_csv(filepath):
    """Load CSV file and return list of dicts."""
    if not filepath.exists():
        print(f"Warning: File not found: {filepath}", file=sys.stderr)
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main():
    print("Loading CSV data...")
    
    # Load all CSV files
    bodies = load_csv(BODIES_CSV)
    foi_details = load_csv(FOI_DETAILS_CSV)
    foi_pages = load_csv(FOI_PAGES_CSV)
    disclosure_files = load_csv(DISCLOSURE_FILES_CSV)
    
    print(f"  Loaded {len(bodies)} public bodies")
    print(f"  Loaded {len(foi_details)} FOI details")
    print(f"  Loaded {len(foi_pages)} FOI pages")
    print(f"  Loaded {len(disclosure_files)} disclosure files")
    
    # Index data by public_body_id for quick lookup
    bodies_by_id = {}
    for body in bodies:
        body_id = body.get("public_body_id", "")
        if body_id:
            bodies_by_id[body_id] = body
    
    foi_details_by_id = {}
    for detail in foi_details:
        body_id = detail.get("public_body_id", "")
        if body_id:
            foi_details_by_id[body_id] = detail
    
    foi_pages_by_id = {}
    for page in foi_pages:
        body_id = page.get("public_body_id", "")
        if body_id:
            foi_pages_by_id[body_id] = page
    
    # Group disclosure files by public_body_id
    disclosure_files_by_id = defaultdict(list)
    for df in disclosure_files:
        body_id = df.get("public_body_id", "")
        if body_id:
            disclosure_files_by_id[body_id].append(df)
    
    # Build consolidated data structure
    result = {}
    missing_bodies = set()
    
    for body_id, body in bodies_by_id.items():
        # Get FOI details
        foi_detail = foi_details_by_id.get(body_id, {})
        
        # Get disclosure files for this body
        files = disclosure_files_by_id.get(body_id, [])
        
        body_data = {
            "public_body_id": int(body_id) if body_id.isdigit() else body_id,
            "public_body_name": body.get("public_body_name", ""),
            "public_body_short_name": body.get("public_body_short_name", ""),
            "public_body_url": body.get("public_body_url", ""),
            "public_body_category": body.get("public_body_category", ""),
            "foi_contact_email": foi_detail.get("foi_contact_email", ""),
            "foi_disclosure_page_url": foi_detail.get("foi_disclosure_page_url", ""),
            "disclosure_files": []
        }
        
        # Process disclosure files
        for df in files:
            file_data = {
                "source_page_url": df.get("source_page_url", ""),
                "document_url": df.get("document_url", ""),
                "document_name": extract_filename_from_url(df.get("document_url", "")),
                "date_added": df.get("date_added", "")
            }
            body_data["disclosure_files"].append(file_data)
        
        # Sort disclosure files by date (newest first)
        body_data["disclosure_files"].sort(key=lambda x: x.get("date_added", ""), reverse=True)
        
        result[body_id] = body_data
    
    # Check for bodies with FOI details that aren't in main bodies list
    for body_id in foi_details_by_id:
        if body_id not in bodies_by_id:
            missing_bodies.add(body_id)
    
    if missing_bodies:
        print(f"  Warning: {len(missing_bodies)} bodies have FOI details but no base info")
    
    # Ensure output directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # Write output
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\nGenerated {OUTPUT_JSON}")
    print(f"  Total public bodies: {len(result)}")
    print(f"  Total disclosure files: {sum(len(b['disclosure_files']) for b in result.values())}")
    
    # Also update the existing public_bodies.json if it exists
    # This keeps the simple list for the home page
    simple_bodies = []
    for body_id, body_data in result.items():
        simple_bodies.append({
            "public_body_id": body_data["public_body_id"],
            "public_body_name": body_data["public_body_name"],
            "public_body_short_name": body_data["public_body_short_name"],
            "public_body_url": body_data["public_body_url"],
            "public_body_category": body_data["public_body_category"],
        })
    
    simple_output = DATA_DIR / "public_bodies.json"
    with open(simple_output, "w", encoding="utf-8") as f:
        json.dump(simple_bodies, f, indent=2, ensure_ascii=False)
    
    print(f"\nAlso updated {simple_output}")
    print(f"  Total bodies: {len(simple_bodies)}")


if __name__ == "__main__":
    main()
