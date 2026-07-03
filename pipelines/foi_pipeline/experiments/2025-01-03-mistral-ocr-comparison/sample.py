#!/usr/bin/env python3
"""Select 10 verified PDFs for the Mistral OCR comparison experiment."""
import hashlib
import json
import random
from pathlib import Path

SEED = 42
SAMPLE_SIZE = 10

# Paths relative to repository root
# Find repo root by looking for .git/ directory (unique to repo root)
REPO_ROOT = Path(__file__).resolve()
while REPO_ROOT.exists() and not (REPO_ROOT / ".git").is_dir():
    REPO_ROOT = REPO_ROOT.parent
VERIFY_OUTPUT = REPO_ROOT / "pipelines/foi_pipeline/steps/verify_disclosure_files/output.json"
TRANSFORM_CACHE = REPO_ROOT / "pipelines/foi_pipeline/steps/transform_disclosure_files/cache"
SAMPLE_OUTPUT = Path(__file__).resolve().parent / "sample.json"


def load_verified_pdfs():
    """Load verified PDFs from verify_disclosure_files output."""
    with open(VERIFY_OUTPUT, "r") as f:
        data = json.load(f)
    
    verified_pdfs = []
    for record in data.get("results", []):
        if (record.get("file_type") == "pdf" and 
            record.get("verification_status") == "verified"):
            verified_pdfs.append(record)
    
    return verified_pdfs


def filter_by_cache(verified_pdfs):
    """Filter to PDFs that exist in the transform cache."""
    if not TRANSFORM_CACHE.exists():
        return verified_pdfs
    
    cache_files = {f.name: f for f in TRANSFORM_CACHE.iterdir() if f.is_file()}
    filtered = []
    
    for record in verified_pdfs:
        file_url = record.get("file_url", "")
        # The cache uses SHA256 hash of the URL as filename
        url_hash = hashlib.sha256(file_url.encode()).hexdigest()
        if url_hash in cache_files:
            filtered.append(record)
    
    return filtered


def select_sample(pdfs, size=SAMPLE_SIZE):
    """Randomly select a sample of PDFs."""
    random.seed(SEED)
    return random.sample(pdfs, min(size, len(pdfs)))


def main():
    print(f"Loading verified PDFs from {VERIFY_OUTPUT}")
    verified = load_verified_pdfs()
    print(f"Found {len(verified)} verified PDFs")
    
    cached = filter_by_cache(verified)
    print(f"Found {len(cached)} PDFs in transform cache")
    
    if len(cached) < SAMPLE_SIZE:
        print(f"Warning: Only {len(cached)} PDFs available, need {SAMPLE_SIZE}")
    
    sample = select_sample(cached, SAMPLE_SIZE)
    
    output = {
        "sample_date": "2025-01-03",
        "sample_size": len(sample),
        "seed": SEED,
        "files": []
    }
    
    for record in sample:
        file_entry = {
            "file_url": record.get("file_url"),
            "body_id": record.get("public_body_id"),
            "body_name": record.get("name"),
            "source_url": record.get("disclosure_page_url"),
            "file_type": record.get("file_type"),
            "sha256": hashlib.sha256(record.get("file_url", "").encode()).hexdigest()
        }
        output["files"].append(file_entry)
    
    with open(SAMPLE_OUTPUT, "w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Sample written to {SAMPLE_OUTPUT}")
    print(f"Selected {len(sample)} files:")
    for file_entry in output["files"]:
        print(f"  - {file_entry['body_name']}: {file_entry['file_url']}")


if __name__ == "__main__":
    main()
