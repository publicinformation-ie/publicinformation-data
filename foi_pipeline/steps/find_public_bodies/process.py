#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scripts.file_utils import append_error, write_json, write_status
from scripts.http_utils import fetch

STEP_NAME = "find_public_bodies"
SOURCE_URL = "https://www.gov.ie/en/departments/"
SECTION_IDS = ["departments", "agencies", "local-authorities"]
BASE_ID = 1000


def generate_short_name(name):
    """Generate short name from public body name."""
    # Common acronyms mapping - ordered by specificity (longest first)
    acronyms = {
        "Department of Agriculture, Food and the Marine": "DAFM",
        "Department of Social Protection": "DSP",
        "Department of Housing, Local Government and Heritage": "DHLGH",
        "Department of Health": "DoH",
        "Department of Education": "DoE",
        "Department of Justice": "DoJ",
        "Department of Finance": "DoF",
        "Department of Transport": "DoT",
        "Department of Public Expenditure, NDP Delivery and Reform": "DPER",
        "Department of Enterprise, Trade and Employment": "DETE",
        "Department of Environment, Climate and Communications": "DECC",
        "Department of Further and Higher Education, Research, Innovation and Science": "DFHERIS",
        "Department of Children, Equality, Disability, Integration and Youth": "DCEDIY",
        "Department of the Taoiseach": "Taoiseach",
        "Department of the Tánaiste": "Tánaiste",
        "Revenue Commissioners": "Revenue",
        "Health Service Executive": "HSE",
        "Central Statistics Office": "CSO",
        "Office of the President": "President",
        "Office of the Taoiseach": "Taoiseach",
        "Office of the Tánaiste": "Tánaiste",
        "Office of the Attorney General": "AG",
    }
    
    # Check for exact match first
    if name in acronyms:
        return acronyms[name]
    
    # Check for prefix matches (e.g., "Department of ...")
    for prefix, short in acronyms.items():
        if name.startswith(prefix):
            return short
    
    # Try to extract known acronym from name (case-insensitive)
    # Look for common patterns like HSE, CSO, etc.
    caps_matches = re.findall(r'\b(HSE|CSO|IDA|ESB|EIRGRID|RTE|NTMA|NTA|CIE|Iarnrod Eireann|Irish Rail)\b', name, re.IGNORECASE)
    if caps_matches:
        return caps_matches[0].upper()
    
    # Try to extract all-caps sequences (2+ letters)
    caps_matches = re.findall(r'\b[A-Z]{2,}\b', name)
    if caps_matches:
        return caps_matches[0]
    
    # For departments without specific mapping, use "Dept" prefix
    if name.startswith("Department of"):
        # Extract first significant word after "Department of"
        words = name.split()
        if len(words) >= 3:
            return f"Dept {words[2][:3].upper()}"
        return "Dept"
    
    # Fallback: use acronym from first letters of each word (max 5 letters)
    words = [w for w in name.split() if w not in ("the", "of", "and", "for", "&", "a", "an")]
    if words:
        # For single word, take first 3 letters
        if len(words) == 1:
            return words[0][:3].upper()
        # For multiple words, take first letter of each word
        acronym = "".join(w[0].upper() for w in words[:5])
        return acronym if len(acronym) <= 5 else acronym[:5]
    
    return "N/A"


def scrape_public_bodies(step_dir):
    errors_path = Path(step_dir) / "errors.json"
    write_json(errors_path, [])

    response = fetch("GET", SOURCE_URL)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    bodies = []
    seen_urls = set()
    body_id = BASE_ID + 1

    for section_id in SECTION_IDS:
        section = soup.find("section", id=section_id)
        if not section:
            print(f"Warning: section '{section_id}' not found on page", file=sys.stderr)
            continue
        for link in section.find_all("a", href=True):
            href = link["href"]
            full_url = urljoin(SOURCE_URL, href)
            if full_url in seen_urls:
                continue
            name = link.get_text(strip=True)
            if not name:
                continue
            seen_urls.add(full_url)
            bodies.append({
                "public_body_id": body_id,
                "name": name,
                "short_name": generate_short_name(name),
                "official_website_url": full_url,
                "status": {
                    "website_url": {
                        "url": full_url,
                        "status": "not_attempted"
                    },
                    "foi_page": {
                        "url": None,
                        "status": "not_attempted"
                    },
                    "foi_email": {
                        "email": None,
                        "status": "not_attempted"
                    },
                    "disclosures_page": {
                        "url": None,
                        "status": "not_attempted"
                    },
                    "disclosure_files": {
                        "total": 0,
                        "valid": 0,
                        "failed": 0,
                        "status": "not_attempted"
                    },
                    "foi_requests": {
                        "valid": 0,
                        "errors": 0,
                        "status": "not_attempted"
                    }
                }
            })
            body_id += 1

    return bodies


def main():
    parser = argparse.ArgumentParser(description="Scrape Irish public bodies from gov.ie")
    parser.add_argument("--input", required=True, help="Previous step output (unused for first step)")
    parser.add_argument("--output", default=None, help="Path to write output.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    args = parser.parse_args()

    step_dir = Path(__file__).parent
    output_path = Path(args.output) if args.output else step_dir / "output.json"

    if not args.force and output_path.exists():
        print(f"Output exists at {output_path}, skipping (use --force to re-run)")
        sys.exit(0)

    try:
        bodies = scrape_public_bodies(step_dir)
    except Exception as e:
        append_error(
            step_dir,
            {
                "step": STEP_NAME,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": type(e).__name__,
                "error_message": str(e),
                "context": {"url": SOURCE_URL},
            },
        )
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)

    if not bodies:
        print("Fatal error: scrape returned 0 bodies - page structure may have changed", file=sys.stderr)
        sys.exit(1)

    output = {
        "metadata": {
            "step": "find_public_bodies",
            "completed_at": datetime.now(timezone.utc).isoformat()
        },
        "public_bodies": bodies
    }
    write_json(output_path, output)
    write_status(step_dir, len(bodies))
    print(f"Wrote {len(bodies)} public bodies to {output_path}")


if __name__ == "__main__":
    main()
