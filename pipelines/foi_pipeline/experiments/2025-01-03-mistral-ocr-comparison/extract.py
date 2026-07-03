#!/usr/bin/env python3
"""Extraction functions for Mistral OCR and pdfplumber comparison."""
import io
import os
import time
from pathlib import Path

import pdfplumber
import requests

# Mistral OCR API configuration
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
MISTRAL_OCR_MODEL = "mistral-ocr-latest"

# Try to import mistralai client
try:
    from mistralai.client import Mistral
    MISTRAL_CLIENT_AVAILABLE = True
except ImportError:
    MISTRAL_CLIENT_AVAILABLE = False
    Mistral = None

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
    if not MISTRAL_CLIENT_AVAILABLE:
        print("mistralai client library not installed. Install with: uv pip install mistralai")
        return None
    if not MISTRAL_API_KEY:
        print("MISTRAL_API_KEY environment variable not set")
        return None
    
    for attempt in range(max_retries):
        try:
            # Use the Mistral client
            client = Mistral(api_key=MISTRAL_API_KEY)
            
            # Save bytes to temp file and use DocumentURLChunk with file:// URL
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(pdf_bytes)
                tmp_path = tmp_file.name
            
            try:
                from mistralai.client.models import DocumentURLChunk
                
                # Use file:// URL for local file
                document_chunk = DocumentURLChunk(
                    type="document_url",
                    document_url=f"file://{tmp_path}"
                )
                
                ocr_response = client.ocr.process(
                    model=MISTRAL_OCR_MODEL,
                    document=document_chunk,
                    table_format="markdown",
                    extract_header=True,
                    confidence_scores_granularity="page",
                )
            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            
            # Extract markdown from tables
            markdown_parts = []
            if hasattr(ocr_response, 'tables') and ocr_response.tables:
                for table in ocr_response.tables:
                    if hasattr(table, 'markdown'):
                        markdown_parts.append(table.markdown)
            
            # Also check pages for tables
            if hasattr(ocr_response, 'pages'):
                for page in ocr_response.pages:
                    if hasattr(page, 'tables') and page.tables:
                        for table in page.tables:
                            if hasattr(table, 'markdown'):
                                markdown_parts.append(table.markdown)
            
            if markdown_parts:
                return "\n\n".join(markdown_parts)
            else:
                print("No tables found in OCR response")
                return ""
                
        except Exception as e:
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
