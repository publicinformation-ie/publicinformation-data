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


def engine_string(lang: str = OCR_LANG, psm: int = OCR_PSM, dpi: int = OCR_DPI) -> str:
    """Identify the OCR engine and every setting that changes its output, e.g.
    ``tesseract 5.5.2 lang=eng psm=4 dpi=300``. Used as part of cache keys."""
    import pytesseract

    version = str(pytesseract.get_tesseract_version()).split()[0]
    return f"tesseract {version} lang={lang} psm={psm} dpi={dpi}"


def words_in_points(words: list[dict], dpi: int = OCR_DPI) -> list[dict]:
    """Convert pixel word boxes to the PDF-point word shape used by the SPC
    pipeline: ``{text, x0, x1, top, bottom, conf, line}``, origin top left,
    scaled by 72/dpi and rounded to 2 places. Order is preserved.

    ``line`` numbers Tesseract's own text lines on the page (0, 1, 2, ... in
    the order Tesseract reports them). A scan is rarely perfectly level, so
    two words on one printed line can differ by several points in ``top``;
    consumers group OCR words by ``line`` rather than by ``top``.
    """
    scale = 72.0 / dpi
    line_ids: dict[tuple[int, int, int], int] = {}
    converted = []
    for w in words:
        key = (w.get("block", 0), w.get("par", 0), w.get("line", 0))
        line = line_ids.setdefault(key, len(line_ids))
        converted.append({
            "text": w["text"],
            "x0": round(w["left"] * scale, 2),
            "x1": round((w["left"] + w["width"]) * scale, 2),
            "top": round(w["top"] * scale, 2),
            "bottom": round((w["top"] + w["height"]) * scale, 2),
            "conf": w["conf"],
            "line": line,
        })
    return converted


def ocr_page_words(page, lang: str = OCR_LANG, psm: int = OCR_PSM,
                   dpi: int = OCR_DPI) -> list[dict]:
    """OCR one ``pymupdf`` page: render at ``dpi``, recognise with the given
    settings, and return words in PDF points (see ``words_in_points``)."""
    from PIL import Image

    pix = page.get_pixmap(dpi=dpi)
    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return words_in_points(ocr_words(image, lang=lang, config=f"--psm {psm}"), dpi)


def mean_confidence(words: list[dict]) -> float | None:
    """Mean word confidence (0-100), or None when there are no words."""
    if not words:
        return None
    return sum(w["conf"] for w in words) / len(words)
