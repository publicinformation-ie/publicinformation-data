"""Shared text normalization utilities for the FOI pipeline."""
import re

_CID_RE = re.compile(r'\(cid:\d+\)')
_MULTI_SPACE_RE = re.compile(r' {2,}')


def normalize_text(value, file_type="", for_header=False):
    """Normalize text for consistent processing across pipeline steps.
    
    Args:
        value: The text value to normalize
        file_type: Optional file type hint ("pdf", "xlsx", "xls")
        for_header: If True, also lowercase and remove trailing punctuation
        
    Returns:
        Normalized string value, or original if not a string
    """
    if not isinstance(value, str):
        return value
    
    result = value
    
    # PDF-specific normalizations (CID artefacts, newlines, multi-spaces)
    if file_type == "pdf":
        result = _CID_RE.sub("", result)
        result = result.replace("\n", " ").replace("\r", " ")
        result = _MULTI_SPACE_RE.sub(" ", result)
    
    # Always strip whitespace
    result = result.strip()
    
    # Header-specific normalizations (for canonical matching)
    if for_header:
        result = result.lower()
        result = re.sub(r'[\s.:]+$', '', result)
    
    return result


def normalize_cell(value, file_type=""):
    """Normalize a cell value.
    
    This is the normalization used by normalize_disclosure_cells step.
    Handles newlines, CID artefacts, and multi-spaces for PDFs.
    """
    return normalize_text(value, file_type=file_type, for_header=False)


def normalize_header(value):
    """Normalize a header string for canonical column matching.

    This is the normalization used by extract_disclosures_canonicalize step.
    Handles newlines, underscores, and whitespace; lowercases for matching.
    """
    if not isinstance(value, str):
        return value
    # Normalize all whitespace (including newlines, underscores) to single spaces
    result = re.sub(r'[\s_]+', ' ', value.strip())
    # Lowercase and remove trailing punctuation
    return re.sub(r'[\s.:/]+$', '', result.lower())
