#!/usr/bin/env python3
"""
Transform public/pipeline-data.json to JSON-LD and CSV for Slice 1.
Usage: python scripts/transform_public_bodies.py
"""
import json
import csv
import re
from datetime import datetime

BASE_URI = "https://codeberg.org/gingertechie/publicinformation-data"
CONTACT_EMAIL = "dave@publicinformation.ie"

def slugify(text):
    """Convert text to URL slug."""
    if not text:
        return "unknown"
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    return slug.strip('-')

def get_foi_scope(status_dict):
    """Determine FOI scope from pipeline status."""
    foi_page = status_dict.get("foi_page", {})
    if foi_page.get("url"):
        return f"{BASE_URI}/ns/foi#FullScope"
    return f"{BASE_URI}/ns/foi#NoScope"

def get_body_uri(body):
    """Generate Cool URI for a public body."""
    name = body.get("public_body_name", "unknown")
    return f"{BASE_URI}/body/{slugify(name)}"

def transform_to_jsonld(bodies):
    """Transform pipeline bodies to JSON-LD format."""
    jsonld_context = {
        "@vocab": "https://schema.org/",
        "foi": f"{BASE_URI}/ns/foi#",
        "dct": "http://purl.org/dc/terms/",
        "prov": "http://www.w3.org/ns/prov#"
    }
    items = []
    for body in bodies:
        status = body.get("status", {})
        foi_page = status.get("foi_page", {})
        foi_email = status.get("foi_email", {})
        item = {
            "@context": jsonld_context,
            "@id": get_body_uri(body),
            "@type": "foi:PublicBody",
            "name": body.get("public_body_name"),
            "short_name": body.get("public_body_name"),
            "type": body.get("public_body_category"),
            "website": body.get("public_body_url"),
            "foi_subject": foi_page.get("url") is not None,
            "foi_scope": get_foi_scope(status),
            "sector": "Government",
            "parent_body": None,
            "governing_legislation": None,
            "geographic_coverage": "IE",
            "contact_email": foi_email.get("email"),
            "contact_phone": None,
            "source_public_body_id": body.get("public_body_id")
        }
        items.append({k: v for k, v in item.items() if v is not None})
    return items

def transform_to_csv(bodies):
    """Transform pipeline bodies to CSV format."""
    fieldnames = [
        "id", "name", "short_name", "description", "type", "website",
        "foi_subject", "foi_scope", "sector", "parent_body",
        "governing_legislation", "geographic_coverage", "contact_email", "contact_phone"
    ]
    rows = []
    for body in bodies:
        status = body.get("status", {})
        foi_page = status.get("foi_page", {})
        foi_email = status.get("foi_email", {})
        rows.append({
            "id": get_body_uri(body),
            "name": body.get("public_body_name"),
            "short_name": body.get("public_body_name"),
            "description": None,
            "type": body.get("public_body_category"),
            "website": body.get("public_body_url"),
            "foi_subject": str(foi_page.get("url") is not None).lower(),
            "foi_scope": get_foi_scope(status),
            "sector": "Government",
            "parent_body": None,
            "governing_legislation": None,
            "geographic_coverage": "IE",
            "contact_email": foi_email.get("email"),
            "contact_phone": None
        })
    return fieldnames, rows

def main():
    with open("public/pipeline-data.json", "r") as f:
        source_data = json.load(f)
    bodies = source_data.get("public_bodies", [])
    jsonld_data = transform_to_jsonld(bodies)
    with open("public/public-bodies.jsonld", "w") as f:
        json.dump(jsonld_data, f, indent=2)
    fieldnames, rows = transform_to_csv(bodies)
    with open("public/public-bodies.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Transformed {len(bodies)} public bodies to JSON-LD and CSV")

if __name__ == "__main__":
    main()
