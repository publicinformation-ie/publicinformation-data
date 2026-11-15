"""Docling runner. Run only as:
    uv run --with docling python experiments/gating/run_docling.py --urls-file F
    uv run python experiments/gating/run_docling.py --seed-from-bakeoff   (no docling needed)

Writes DOCLING_PAGES/<content-sha>.json as {"pages": [...], "seconds": s}.
Conversion matches the bakeoff's run_docling.py. docling is imported inside main().
"""
import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from experiments.gating.paths import BAKEOFF, DOCLING_PAGES, content_sha, pdf_bytes  # noqa: E402


def seed_from_bakeoff() -> int:
    DOCLING_PAGES.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted((BAKEOFF / "results" / "docling").glob("*.json")):
        if f.name.startswith("_"):
            continue
        dest = DOCLING_PAGES / f.name
        if not dest.exists():
            shutil.copyfile(f, dest)
            n += 1
    print(f"seeded {n} new; {len(list(DOCLING_PAGES.glob('*.json')))} total in {DOCLING_PAGES}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-from-bakeoff", action="store_true")
    ap.add_argument("--urls-file")
    a = ap.parse_args(argv)
    if a.seed_from_bakeoff:
        return seed_from_bakeoff()
    if not a.urls_file:
        ap.error("need --seed-from-bakeoff or --urls-file")

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opts = PdfPipelineOptions()
    opts.do_ocr = False
    conv = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})
    DOCLING_PAGES.mkdir(parents=True, exist_ok=True)
    urls = [u.strip() for u in Path(a.urls_file).read_text().splitlines() if u.strip()]
    failures: dict[str, str] = {}
    for i, url in enumerate(urls, 1):
        data = pdf_bytes(url)
        if data is None:
            continue
        sha = content_sha(data)
        out = DOCLING_PAGES / f"{sha}.json"
        if out.exists():
            continue
        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / "in.pdf"  # docling needs a .pdf suffix
            try:
                pdf.write_bytes(data)
                t = time.time()
                doc = conv.convert(str(pdf)).document
                pages: dict[int, list] = {}
                for table in doc.tables:
                    pno = table.prov[0].page_no if table.prov else 0
                    rows = [[c.text.strip() for c in r] for r in table.data.grid]
                    pages.setdefault(pno, []).extend(rows)
                n = len(doc.pages) or max(pages, default=0)
                secs = round(time.time() - t, 2)
                out.write_text(json.dumps({"pages": [pages.get(p, []) for p in range(1, n + 1)], "seconds": secs}))
                print(f"[{i}/{len(urls)}] ok {sha[:10]} {secs}s", flush=True)
            except Exception as e:  # noqa: BLE001
                failures[url] = f"{type(e).__name__}: {e}"[:300]
                print(f"[{i}/{len(urls)}] FAIL {sha[:10]} {failures[url]}", flush=True)
    if failures:
        print(f"{len(failures)} failed:")
        for u, m in failures.items():
            print(" ", u, m)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
