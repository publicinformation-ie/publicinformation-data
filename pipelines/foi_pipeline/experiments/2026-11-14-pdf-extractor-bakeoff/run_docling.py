"""Isolated docling run over sample.json (text layer only, OCR off).

    uv run --with docling python experiments/2026-11-14-pdf-extractor-bakeoff/run_docling.py

Never touches requirements.txt. Writes results/docling/<sha256>.json as
{"pages": [[row, ...], ...]} where each page entry is the concatenated rows of
the tables docling found on that page (padded to the PDF page count).
Note: docling downloads its layout/table model weights from HuggingFace on first use. Failures go to results/docling/_failures.json.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE.parents[1] / "steps" / "verify_disclosure_files" / "cache"
OUT = HERE / "results" / "docling"


def main() -> int:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.do_ocr = False
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    OUT.mkdir(parents=True, exist_ok=True)
    sample = json.loads((HERE / "sample.json").read_text())
    failures, timings = {}, {}
    for s in sample:
        sha = s["sha256"]
        path = CACHE / (hashlib.sha256(s["file_url"].encode()).hexdigest() + ".bytes")
        if not path.exists():
            failures[sha] = "not on disk"
            continue
        pdf = OUT / f".{sha}.pdf"  # docling needs a .pdf suffix
        try:
            pdf.write_bytes(path.read_bytes())
            t = time.time()
            doc = conv.convert(str(pdf)).document
            pages: dict[int, list] = {}
            for table in doc.tables:
                pno = table.prov[0].page_no if table.prov else 0
                grid = table.data.grid
                rows = [[c.text.strip() for c in r] for r in grid]
                pages.setdefault(pno, []).extend(rows)
            n = len(doc.pages) or max(pages, default=0)  # pad to document page count
            out = {"pages": [pages.get(i, []) for i in range(1, n + 1)]}
            (OUT / f"{sha}.json").write_text(json.dumps(out))
            timings[sha] = round(time.time() - t, 2)
            print("ok", sha[:10], timings[sha], flush=True)
        except Exception as e:  # noqa: BLE001
            failures[sha] = f"{type(e).__name__}: {e}"[:300]
            print("FAIL", sha[:10], failures[sha], flush=True)
        finally:
            pdf.unlink(missing_ok=True)
    (OUT / "_summary.json").write_text(json.dumps({"timings": timings, "failures": failures}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
