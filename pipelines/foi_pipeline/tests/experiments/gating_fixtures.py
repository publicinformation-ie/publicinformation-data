"""Shared builders for a tiny fake steps tree (imported by gating tests)."""
import json
from pathlib import Path

GATED_URL = "https://x.test/gated.pdf"
HALF_ERRORS_URL = "https://x.test/half.pdf"
CLEAN_URL = "https://x.test/clean.pdf"


def _w(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def _score(**kw):
    base = {"n_rows": 10, "worst_role_contamination": 0.0, "worst_role": "date_received",
            "anchored_row_share": 1.0}
    base.update(kw)
    return base


def make_steps(root: Path, gated_records=0) -> Path:
    items = []
    for url, name in ((GATED_URL, "Gated"), (HALF_ERRORS_URL, "Half"), (CLEAN_URL, None)):
        it = {"public_body_id": 7, "file_url": url, "file_type": "pdf", "pdf_extractor": "pdfplumber",
              "pdf_table_selection": {"chosen": "pdfplumber", "scores": {
                  "pdfplumber": _score(), "camelot": {"error": "boom"}}}}
        if name:
            it["name"] = name
        items.append(it)
    _w(root / "transform_disclosure_files/output.json", {"metadata": {}, "results": items})
    assessed = []
    for it in items:
        a = dict(it)
        if it["file_url"] == GATED_URL:
            a["table_structure"] = _score(worst_role_contamination=0.9, anchored_row_share=0.1,
                                          worst_role="requester_type")
            a["table_structure_unreliable"] = True
        assessed.append(a)
    _w(root / "assess_table_structure/output.json", {"metadata": {}, "results": assessed})
    _w(root / "assess_table_structure/errors.json", [{"error_type": "TableStructureUnreliable", "context": {
        "file_url": GATED_URL, "failed_checks": ["role_contamination", "anchored_row_share"]}}])
    rows = [{"file_url": HALF_ERRORS_URL}] + [{"file_url": CLEAN_URL}] * 5
    rows += [{"file_url": GATED_URL}] * gated_records
    _w(root / "extract_disclosures_canonicalize_rows/output.json", {"metadata": {}, "results": rows})
    _w(root / "extract_disclosures_canonicalize_rows/errors.json", [
        {"error_type": "UnrecognizedDecisionStatus", "error_message": "x",
         "context": {"file_url": HALF_ERRORS_URL, "raw_decision_status": "zzz qqq"}}])
    _w(root / "extract_disclosures_canonicalize/column_mappings.json", {})
    _w(root / "extract_disclosures_normalize_header/override.json", [])
    return root


def make_pdf(pages=1, text="", password=None) -> bytes:
    import pymupdf
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page()
        if text:
            page.insert_textbox(pymupdf.Rect(20, 20, 580, 800), text, fontsize=8)
    if password:
        return doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=password, owner_pw=password)
    return doc.tobytes()
