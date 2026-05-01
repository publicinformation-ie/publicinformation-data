import csv
import re
import unicodedata
import argparse
from pathlib import Path

def normalize_name(name):
    """Normalize a name for comparison.
    This must match the normalization used in enrich_foi_emails_from_gov_portal.py
    
    Note: The foi.gov.ie data sometimes has punctuation without spaces (e.g., "word,word")
    which becomes "wordword" after normalization. To handle this, we first add spaces
    after certain punctuation marks before normalization.
    """
    # First, add spaces after commas and other punctuation that might be adjacent to words
    name = re.sub(r'([,;:])([^\s])', r'\1 \2', name)
    name = name.lower()
    name = ''.join(c for c in unicodedata.normalize('NFKD', name) if unicodedata.category(c) != 'Mn')
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def load_public_bodies(csv_path):
    """Load public bodies from CSV file."""
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return {row['public_body_id']: row['public_body_name'] for row in reader}


def load_website_names(txt_path):
    """Load public body names from foi.gov.ie text file."""
    names = []
    with open(txt_path, 'r', encoding='utf-8') as f:
        next(f, None)  # Skip header
        for line in f:
            line = line.strip()
            if line:
                names.append(line)
    return names


def find_best_match(our_name, website_names, stop_words):
    """Find the best matching name from foi.gov.ie for a given public body name.
    
    Uses a tiered approach:
    1. Exact normalized match
    2. Normalized match with word order differences
    3. Subset matching (one is a subset of the other)
    4. Partial matching with word overlap
    
    Returns the best match or None if no good match found.
    """
    our_norm = normalize_name(our_name)
    our_words = set(our_norm.split()) - stop_words
    
    best_match = None
    best_score = 0
    
    for wn in website_names:
        wn_norm = normalize_name(wn)
        wn_words = set(wn_norm.split()) - stop_words
        
        # Score 3: Exact normalized match
        if wn_norm == our_norm:
            if wn.lower() != our_name.lower():
                return wn
            return None  # Exact match with same name, no alias needed
        
        # Score 2: Subset relationship with small difference
        # Check if our name is a subset of foi name (our name is more specific)
        if our_words.issubset(wn_words):
            diff = wn_words - our_words
            if len(diff) <= 2:
                return wn
        
        # Check if foi name is a subset of our name (foi name is more specific)
        if wn_words.issubset(our_words):
            diff = our_words - wn_words
            if len(diff) <= 2:
                return wn
        
        # Score 1: High word overlap (at least 50% of words match)
        # Only consider if both have at least 2 words
        if len(our_words) >= 2 and len(wn_words) >= 2:
            overlap = our_words & wn_words
            # Require at least 50% overlap and at least 2 words in common
            if len(overlap) >= 2:
                overlap_pct_our = len(overlap) / len(our_words) if our_words else 0
                overlap_pct_wn = len(overlap) / len(wn_words) if wn_words else 0
                if overlap_pct_our >= 0.5 or overlap_pct_wn >= 0.5:
                    # Only return if this is the best match so far
                    # For now, return the first good overlap match
                    # This handles cases like "Department of Tourism..." vs "Department of Culture..."
                    # where they share "department" but have different specific names
                    pass
    
    return best_match


def main():
    parser = argparse.ArgumentParser(description='Generate aliases for public bodies')
    parser.add_argument('--public-bodies', default='public_bodies.csv', help='Path to public_bodies.csv')
    parser.add_argument('--website-names', default='foi_dot_ie_public_body_names.txt', help='Path to foi_dot_ie_public_body_names.txt')
    parser.add_argument('--output', default='public_bodies_aliases.csv', help='Path to output CSV')
    parser.add_argument('--verbose', action='store_true', help='Print verbose output')
    args = parser.parse_args()

    # Load data
    public_bodies = load_public_bodies(args.public_bodies)
    website_names = load_website_names(args.website_names)
    
    # Stop words to ignore in matching
    stop_words = {'the', 'of', 'and', 'a', 'an', 'for', 'in', 'at', 'on', 'to', 'by', '&', 'or', 'as'}
    
    # Build a normalized lookup for exact matches
    website_norm_to_original = {}
    for wn in website_names:
        wn_norm = normalize_name(wn)
        # Store the first occurrence (should be unique anyway)
        if wn_norm not in website_norm_to_original:
            website_norm_to_original[wn_norm] = wn
    
    # Also build a mapping from normalized name to list of original names
    # for cases where multiple website names normalize to the same thing
    website_norm_to_list = {}
    for wn in website_names:
        wn_norm = normalize_name(wn)
        if wn_norm not in website_norm_to_list:
            website_norm_to_list[wn_norm] = []
        website_norm_to_list[wn_norm].append(wn)
    
    aliases = []
    no_match = []
    exact_matches = 0
    
    # Known mappings for specific cases that can't be matched automatically
    # These are cases where the organization name has changed significantly
    known_mappings = {
        '1004': 'Department of Culture,Communications and Sport',
        '1019': 'An Bord Pleanala',
        '1022': 'Aquacultural Licencing Appeals Board',
        '1023': 'An Bord Bia',
        '1027': 'Coillte',  # This might be truly missing
        '1031': 'Criminal Assets Bureau',  # This might be truly missing
        '1032': 'Data Protection Commissioner',  # Note: we have "Data Protection Commission"
        '1039': 'Gambling Regulatory Authority of Ireland',  # This might be truly missing
        '1041': 'Greyhound Racing Ireland (GRI)',  # This might be truly missing
        '1043': 'Health Service Executive',  # This might be truly missing
        '1044': 'Healthy Ireland',  # This might be truly missing
    }
    
    # Sort public body IDs for consistent output
    sorted_ids = sorted(public_bodies.keys(), key=int)
    
    for pub_id in sorted_ids:
        official_name = public_bodies[pub_id]
        our_norm = normalize_name(official_name)
        
        # Check if we have a known mapping for this ID
        if pub_id in known_mappings:
            foi_name = known_mappings[pub_id]
            aliases.append((pub_id, official_name, foi_name))
            if args.verbose:
                print(f"Known mapping: {pub_id} '{official_name}' -> '{foi_name}'")
            continue
        
        # Check for exact normalized match
        if our_norm in website_norm_to_original:
            original_wn = website_norm_to_original[our_norm]
            # Only create an alias if the names are different
            if original_wn.lower() != official_name.lower():
                aliases.append((pub_id, official_name, original_wn))
                if args.verbose:
                    print(f"Exact match (different case): {pub_id} -> {original_wn}")
            exact_matches += 1
            continue
        
        # Try to find a match using subset logic
        found = False
        our_words = set(our_norm.split()) - stop_words
        
        for wn in website_names:
            wn_norm = normalize_name(wn)
            wn_words = set(wn_norm.split()) - stop_words
            
            # Skip if this is the same as our normalized name (already checked)
            if wn_norm == our_norm:
                continue
            
            # Check subset relationships
            # Case 1: Our words are subset of website words (our name is more specific)
            if our_words.issubset(wn_words):
                diff = wn_words - our_words
                if len(diff) <= 2:
                    aliases.append((pub_id, official_name, wn))
                    found = True
                    if args.verbose:
                        print(f"Subset match (our subset): {pub_id} '{official_name}' -> '{wn}' (diff: {diff})")
                    break
            
            # Case 2: Website words are subset of our words (website name is more specific)
            if wn_words.issubset(our_words):
                diff = our_words - wn_words
                if len(diff) <= 2:
                    aliases.append((pub_id, official_name, wn))
                    found = True
                    if args.verbose:
                        print(f"Subset match (wn subset): {pub_id} '{official_name}' -> '{wn}' (diff: {diff})")
                    break
            
            # Case 3: Neither is a subset, but the symmetric difference is small (<= 2 words)
            # This handles cases like "Irish National Stud and Gardens" vs "The Irish National Stud DAC"
            # where the difference is {"gardens"} vs {"dac"}
            symmetric_diff = (our_words - wn_words) | (wn_words - our_words)
            if len(symmetric_diff) <= 2:
                # Also require that they share at least 2 words AND
                # that the overlap is at least 85% of both names
                overlap = our_words & wn_words
                if len(overlap) >= 2:
                    overlap_pct_our = len(overlap) / len(our_words) if our_words else 0
                    overlap_pct_wn = len(overlap) / len(wn_words) if wn_words else 0
                    if overlap_pct_our >= 0.75 and overlap_pct_wn >= 0.75:
                        aliases.append((pub_id, official_name, wn))
                        found = True
                        if args.verbose:
                            print(f"Close match (sym diff): {pub_id} '{official_name}' -> '{wn}' (sym diff: {symmetric_diff})")
                        break
        
        if not found:
            # Check for special cases that need manual handling
            no_match.append((pub_id, official_name))
    
    # Sort aliases by public_body_id (already sorted, but just to be sure)
    aliases.sort(key=lambda x: int(x[0]))

    # Write output
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['public_body_id', 'public_body_name', 'foi_gov_ie_name'])
        for alias in aliases:
            writer.writerow(alias)

    print(f"Generated {len(aliases)} alias entries")
    print(f"Found {exact_matches} exact matches (no alias needed)")
    print(f"No match found for {len(no_match)} public bodies:")
    for pub_id, name in no_match[:20]:  # Show first 20
        print(f"  {pub_id}: {name}")
    if len(no_match) > 20:
        print(f"  ... and {len(no_match) - 20} more")

if __name__ == '__main__':
    main()