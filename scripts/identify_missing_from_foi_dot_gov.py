#!/usr/bin/env python3
"""
Identify public bodies that are missing from foi.gov.ie by comparing
no-match.txt (from enrich script) with foi_dot_ie_public_body_names.txt.

Outputs a CSV file: public_bodies_missing_from_foi_dot_gov.csv
"""
import csv
import re
import sys
from pathlib import Path


def parse_no_match_file(no_match_path):
    """Parse no-match.txt to extract public_body_id and public_body_name."""
    entries = {}
    # Pattern: No match for public_body_id=1234 name="Some Name"
    pattern = r'No match for public_body_id=(\d+) name="([^"]+)"'
    
    with open(no_match_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            match = re.search(pattern, line)
            if match:
                pub_id = match.group(1)
                pub_name = match.group(2)
                entries[pub_id] = pub_name
    
    return entries


def load_foi_dot_ie_names(foi_names_path):
    """Load all names from foi_dot_ie_public_body_names.txt."""
    names = set()
    
    with open(foi_names_path, 'r', encoding='utf-8') as f:
        next(f)  # Skip header
        for line in f:
            line = line.strip()
            if line:
                names.add(line.lower())
    
    return names


def normalize_name(name):
    """Normalize a name for comparison (similar to enrich script)."""
    import unicodedata
    import re
    name = name.lower()
    name = ''.join(c for c in unicodedata.normalize('NFKD', name) if unicodedata.category(c) != 'Mn')
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def is_missing(pub_name, foi_names):
    """Check if a public body name is missing from foi.gov.ie."""
    import re
    
    normalized_pub = normalize_name(pub_name)
    pub_words = set(normalized_pub.split())
    
    # Known acronyms and their expansions
    known_acronyms = {
        'hse': ['health service executive'],
        'etb': ['education and training board'],
        'nama': ['national asset management agency'],
        'ntma': ['national treasury management agency'],
        'hetac': ['higher education and training awards council'],
        'fetac': ['further education and training awards council'],
    }
    
    # Extract acronyms from pub_name (e.g., HSE from "Health Service Executive (HSE)")
    pub_acronyms = set(re.findall(r'\(([A-Z]{2,})\)', pub_name))
    
    # Also check if the name contains known acronyms
    pub_lower = pub_name.lower()
    for acronym, expansions in known_acronyms.items():
        for expansion in expansions:
            if expansion in pub_lower:
                pub_acronyms.add(acronym.upper())
    
    for foi_name in foi_names:
        normalized_foi = normalize_name(foi_name)
        foi_words = set(normalized_foi.split())
        foi_lower = foi_name.lower()
        
        # Check for exact match
        if normalized_pub == normalized_foi:
            return False
        
        # Check if one contains the other (for cases like abbreviations)
        if normalized_pub in normalized_foi or normalized_foi in normalized_pub:
            return False
        
        # Check for common variations:
        # - "City and County Council" vs "County Council"
        # - "Institute of Technology" vs "Technological University"
        common_words = pub_words & foi_words
        if len(common_words) > 0:
            # If they share the main name (excluding common terms)
            common_terms = {'the', 'of', 'and', 'a', 'an', 'for', 'in', 'at', 'on', 'ireland', 'irish'}
            meaningful_common = common_words - common_terms
            if len(meaningful_common) >= 2:  # At least 2 meaningful words in common
                return False
        
        # Check if pub_name acronym appears in foi_name
        for acronym in pub_acronyms:
            if acronym.lower() in normalized_foi or acronym.lower() in foi_lower:
                return False
        
        # Check if foi_name contains a known acronym that matches pub_name
        for acronym, expansions in known_acronyms.items():
            if acronym in foi_lower:
                for expansion in expansions:
                    if expansion in pub_lower:
                        return False
    
    return True


def main():
    no_match_path = Path('no-match.txt')
    foi_names_path = Path('foi_dot_ie_public_body_names.txt')
    output_path = Path('public_bodies_missing_from_foi_dot_gov.csv')
    
    if not no_match_path.exists():
        print(f"Error: {no_match_path} not found", file=sys.stderr)
        sys.exit(1)
    
    if not foi_names_path.exists():
        print(f"Error: {foi_names_path} not found", file=sys.stderr)
        sys.exit(1)
    
    # Parse no-match.txt
    no_match_entries = parse_no_match_file(no_match_path)
    
    # Load foi.gov.ie names
    foi_names = load_foi_dot_ie_names(foi_names_path)
    
    # Identify missing bodies
    missing = []
    for pub_id, pub_name in no_match_entries.items():
        if is_missing(pub_name, foi_names):
            missing.append({'public_body_id': pub_id, 'public_body_name': pub_name})
    
    # Write output CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['public_body_id', 'public_body_name'])
        writer.writeheader()
        for entry in missing:
            writer.writerow(entry)
    
    print(f"Identified {len(missing)} public bodies missing from foi.gov.ie")
    print(f"Written to {output_path}")


if __name__ == '__main__':
    main()
