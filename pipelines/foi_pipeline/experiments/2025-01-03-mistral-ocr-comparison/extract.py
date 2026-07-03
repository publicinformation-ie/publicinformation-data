#!/usr/bin/env python3
"""Extraction functions for Mistral OCR and pdfplumber comparison."""
import io
import os
import time
from pathlib import Path

import pdfplumber
import requests

# Mistral OCR API configuration
MISTRAL_OCR_API_URL = "https://ocr.mistral.ai/api/v1/extract"
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

# Paths
SAMPLE_PATH = Path(__file__).resolve().parent / "sample.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def download_pdf(url, timeout=30):
    """Download a PDF from a URL.
    
    Args:
        url: URL of the PDF
        timeout: Request timeout in seconds
        
    Returns:
        Bytes of the PDF content, or None on failure
    """
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None


def extract_with_pdfplumber(pdf_bytes):
    """Extract tables from PDF using pdfplumber.
    
    Args:
        pdf_bytes: Raw PDF bytes
        
    Returns:
        List of rows in pipeline format: [[cell1, cell2, ...], ...]
        or None if extraction fails
    """
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            all_rows = []
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        # Convert None to empty string for consistency
                        processed_row = [cell if cell is not None else "" for cell in row]
                        all_rows.append(processed_row)
            return all_rows if all_rows else []
    except Exception as e:
        print(f"pdfplumber extraction failed: {e}")
        return None


def extract_with_mistral_ocr(pdf_bytes, max_retries=3):
    """Extract tables from PDF using Mistral OCR API.
    
    Args:
        pdf_bytes: Raw PDF bytes
        max_retries: Maximum number of API retry attempts
        
    Returns:
        Raw markdown string from Mistral OCR, or None on failure
    """
    if not MISTRAL_API_KEY:
        print("MISTRAL_API_KEY environment variable not set")
        return None
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                MISTRAL_OCR_API_URL,
                headers={
                    "Authorization": f"Bearer {MISTRAL_API_KEY}",
                    "Content-Type": "application/pdf"
                },
                data=pdf_bytes,
                params={
                    "table_format": "markdown",
                    "extract_header": "true"
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json().get("markdown", "")
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                backoff = (2 ** attempt) * 1  # Exponential backoff
                print(f"Mistral OCR attempt {attempt + 1} failed, retrying in {backoff}s: {e}")
                time.sleep(backoff)
            else:
                print(f"Mistral OCR failed after {max_retries} attempts: {e}")
                return None
    
    return None


def extract_file(file_entry, results_dir):
    """Extract a single file with both methods.
    
    Args:
        file_entry: Dict with file_url, sha256, etc.
        results_dir: Path to results directory
        
    Returns:
        Dict with extraction results for both methods
    """
    file_url = file_entry["file_url"]
    file_id = file_entry["sha256"]
    
    print(f"Extracting {file_id[:8]}... from {file_url}")
    
    # Download PDF
    pdf_bytes = download_pdf(file_url)
    if not pdf_bytes:
        return {
            "file_id": file_id,
            "file_url": file_url,
            "mistral_raw": None,
            "pdfplumber_raw": None,
            "error": "Failed to download PDF"
        }
    
    # Extract with pdfplumber
    pdfplumber_rows = extract_with_pdfplumber(pdf_bytes)
    
    # Extract with Mistral OCR
    mistral_markdown = extract_with_mistral_ocr(pdf_bytes)
    
    # Convert Mistral markdown to rows
    # Import here to avoid circular imports
    import importlib.util
    _CONVERT_PATH = Path(__file__).parent / "convert.py"
    spec = importlib.util.spec_from_file_location("convert_mod", _CONVERT_PATH)
    assert spec is not None and spec.loader is not None
    convert_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(convert_mod)
    mistral_rows = convert_mod.markdown_to_rows(mistral_markdown) if mistral_markdown else []
    
    # Save raw outputs
    results_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "file_id": file_id,
        "file_url": file_url,
        "body_name": file_entry.get("body_name"),
        "mistral_raw": mistral_markdown,
        "mistral_rows": mistral_rows,
        "pdfplumber_raw": pdfplumber_rows,
        "extraction_time_ms": 0  # Will be set by caller
    }


def load_sample():
    """Load the sample from sample.json."""
    import json
    with open(SAMPLE_PATH, "r") as f:
        return json.load(f)
