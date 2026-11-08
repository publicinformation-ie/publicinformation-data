"""Shared, deterministic Tesseract helper.

Renders nothing itself: callers hand in a PIL image (or anything
`pytesseract` accepts) and get back word-level results with bounding boxes and
confidences. Settings are fixed (language, page segmentation mode) so the same
pixels always produce the same words.

Used by document_pipeline's `extract_pages` OCR fallback. minutes_pipeline's
`ocr_minutes_files` has its own plain-text `ocr_pdf_bytes`; it is deliberately
not switched over here, but may adopt this module later.
"""
from __future__ import annotations

OCR_LANG = "eng"
OCR_DPI = 300
OCR_PSM = 3     # fully automatic page segmentation, no OSD
OCR_CONFIG = f"--psm {OCR_PSM}"


def ocr_words(image, lang: str = OCR_LANG, config: str = OCR_CONFIG) -> list[dict]:
    """Recognised words in reading order, as
    `{text, conf, left, top, width, height, block, par, line, word}` dicts
    (pixel coordinates). Empty strings and Tesseract's conf == -1 layout rows
    are dropped. Raises if Tesseract fails."""
    import pytesseract

    data = pytesseract.image_to_data(image, lang=lang, config=config,
                                     output_type=pytesseract.Output.DICT)
    words = []
    for i, raw in enumerate(data["text"]):
        text = str(raw).strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        words.append({
            "text": text, "conf": conf,
            "left": int(data["left"][i]), "top": int(data["top"][i]),
            "width": int(data["width"][i]), "height": int(data["height"][i]),
            "block": int(data["block_num"][i]), "par": int(data["par_num"][i]),
            "line": int(data["line_num"][i]), "word": int(data["word_num"][i]),
        })
    return words


def mean_confidence(words: list[dict]) -> float | None:
    """Mean word confidence (0-100), or None when there are no words."""
    if not words:
        return None
    return sum(w["conf"] for w in words) / len(words)
