#!/usr/bin/env python3
"""Gold review server: a small LAN page for checking chapter lists.

Serves one page listing every gold file, its rendered contents pages and each
chapter's start page, and an editor for the chapter list. Saves straight back
to `steps/detect_structure/eval/gold/<doc_slug>.json`, so the review does not
have to be transcribed by hand.

Standard library only (PyMuPDF is used to render pages, as `annotate.py` does).

    cd pipelines/document_pipeline
    PYTHONPATH=".:../../src" python steps/detect_structure/eval/review_server.py
    # → http://<your LAN address>:8765

The page is read/write and has no authentication: bind it to your LAN, not the
internet. It writes only inside the gold directory and the gitignored
`.scratch/structure-review/` directory.
"""
import argparse
import ipaddress
import json
import socket
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))

import gold as gold_module  # noqa: E402

APP_DIR = _HERE / "review_app"
GOLD_DIR = _HERE / "gold"
SNAPSHOT_PATH = _HERE / "input.json"
DOC_PIPELINE = _HERE.parents[2]
REPO_ROOT = DOC_PIPELINE.parents[1]
SCRATCH = REPO_ROOT / ".scratch" / "structure-review"
IMAGES_DIR = SCRATCH / "images"
AUDIT_LOG = SCRATCH / "audit.log"
FETCH_PDFS_OUTPUT = DOC_PIPELINE / "steps" / "fetch_pdfs" / "output.json"
DPI = 110


def _json_bytes(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def lan_addresses() -> list:
    """Best-effort list of this machine's LAN IPv4 addresses."""
    addresses = []
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect(("8.8.8.8", 80))
            addresses.append(probe.getsockname()[0])
        finally:
            probe.close()
    except OSError:
        pass
    try:
        for name in socket.gethostbyname_ex(socket.gethostname())[2]:
            addresses.append(name)
    except OSError:
        pass
    unique = []
    for address in addresses:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            continue
        if parsed.is_loopback or address in unique:
            continue
        unique.append(address)
    return unique


class ReviewState:
    """Gold files, the snapshot and the rendered page images."""

    def __init__(self, gold_dir=GOLD_DIR, refresh_images=False):
        self.gold_dir = Path(gold_dir)
        self.lock = threading.Lock()
        self.refresh_images = refresh_images
        self.snapshot = {}
        if SNAPSHOT_PATH.exists():
            try:
                documents = _read_json(SNAPSHOT_PATH)["documents"]
                self.snapshot = {document["doc_slug"]: document for document in documents}
            except (KeyError, json.JSONDecodeError):
                self.snapshot = {}
        self.pdfs = {}
        self.titles = {}
        if FETCH_PDFS_OUTPUT.exists():
            records = _read_json(FETCH_PDFS_OUTPUT)["results"]
            for record in records:
                self.pdfs[record["doc_slug"]] = FETCH_PDFS_OUTPUT.parent / record["pdf_path"]
                self.titles[record["doc_slug"]] = record.get("title") or ""

    # -- files ----------------------------------------------------------
    def gold_path(self, slug: str) -> Path:
        return self.gold_dir / f"{slug}.json"

    def load(self, slug: str) -> dict:
        return _read_json(self.gold_path(slug))

    def slugs(self) -> list:
        return sorted(path.stem for path in self.gold_dir.glob("*.json")
                      if path.name != gold_module.NO_TOC_FILENAME)

    # -- images ---------------------------------------------------------
    def _pdf_path(self, slug: str):
        path = self.pdfs.get(slug) or (DOC_PIPELINE / "steps" / "fetch_pdfs" / "pdfs" /
                                       f"{slug}.pdf")
        return path if path.exists() else None

    def ensure_images(self, slug: str, numbers: list) -> dict:
        """Render the requested pages once; return `{page_number: url}`."""
        cache = IMAGES_DIR / slug
        cache.mkdir(parents=True, exist_ok=True)
        wanted = sorted({int(number) for number in numbers if number})
        missing = [number for number in wanted
                   if self.refresh_images or not (cache / f"page-{number:03d}.png").exists()]
        if missing:
            pdf_path = self._pdf_path(slug)
            if pdf_path is not None:
                import pymupdf

                with pymupdf.open(str(pdf_path)) as document:
                    for number in missing:
                        if 1 <= number <= document.page_count:
                            pixmap = document[number - 1].get_pixmap(dpi=DPI)
                            pixmap.save(str(cache / f"page-{number:03d}.png"))
        return {number: f"/images/{slug}/page-{number:03d}.png" for number in wanted
                if (cache / f"page-{number:03d}.png").exists()}

    # -- document state -------------------------------------------------
    def doc_state(self, slug: str) -> dict:
        data = self.load(slug)
        document = self.snapshot.get(slug)
        pages = document["pages"] if document else []
        errors = gold_module.validate_gold(data, expected_slug=slug)
        warnings = []
        mismatch = False
        if not errors:
            gold_doc = gold_module.GoldDocument(
                doc_slug=data["doc_slug"],
                pdf_sha256=data["pdf_sha256"],
                toc_pdf_pages=data["toc_pdf_pages"],
                reviewed=bool(data["reviewed"]),
                chapters=[dict(chapter) for chapter in data["chapters"]],
                annotator=data.get("annotator", ""),
                annotated_on=data.get("annotated_on", ""),
                notes=data.get("notes", ""),
            )
            if document is None:
                warnings.append("document is not in the detection snapshot — page checks skipped")
            else:
                if document.get("source_sha256") != data["pdf_sha256"]:
                    mismatch = True
                warnings = gold_module.consistency_warnings(gold_doc, pages)

        chapter_pages = [chapter.get("pdf_page") for chapter in data["chapters"]]
        images = self.ensure_images(slug, list(data["toc_pdf_pages"]) + chapter_pages)
        return {
            "slug": slug,
            "title": self.titles.get(slug, ""),
            "reviewed": bool(data["reviewed"]),
            "annotator": data.get("annotator", ""),
            "annotated_on": data.get("annotated_on", ""),
            "notes": data.get("notes", ""),
            "toc_pdf_pages": data["toc_pdf_pages"],
            "pdf_sha256": data["pdf_sha256"],
            "source_sha256": (document or {}).get("source_sha256"),
            "page_count": (document or {}).get("page_count"),
            "gold_pdf_mismatch": mismatch,
            "chapters": data["chapters"],
            "errors": errors,
            "warnings": warnings,
            "images": {
                "toc": [images[number] for number in data["toc_pdf_pages"] if number in images],
                "pages": {str(number): url for number, url in images.items()},
            },
        }

    def all_state(self) -> dict:
        documents = []
        for slug in self.slugs():
            try:
                documents.append(self.doc_state(slug))
            except (KeyError, json.JSONDecodeError) as exc:
                documents.append({"slug": slug, "errors": [f"cannot read gold file: {exc}"],
                                  "warnings": [], "chapters": [], "reviewed": False,
                                  "notes": "", "toc_pdf_pages": [], "images": {"toc": [], "pages": {}}})
        return {
            "documents": documents,
            "reviewed": sum(1 for document in documents if document.get("reviewed")),
            "total": len(documents),
        }

    # -- saving ---------------------------------------------------------
    def save(self, payload: dict) -> tuple:
        slug = str(payload.get("slug") or "")
        with self.lock:
            if slug not in self.slugs():
                return 400, {"ok": False, "errors": [f"unknown document {slug!r}"]}
            data = self.load(slug)
            chapters = []
            for index, chapter in enumerate(payload.get("chapters") or [], start=1):
                try:
                    page = int(chapter.get("pdf_page"))
                except (TypeError, ValueError):
                    page = 0
                printed = chapter.get("printed_page")
                chapters.append({
                    "title": str(chapter.get("title") or "").strip(),
                    "printed_page": None if printed in (None, "") else str(printed).strip(),
                    "pdf_page": page,
                })
            reviewed = bool(payload.get("reviewed"))
            annotator = str(payload.get("annotator") or "").strip()
            data["chapters"] = chapters
            data["notes"] = str(payload.get("notes") or "")
            data["reviewed"] = reviewed
            if reviewed:
                if not annotator:
                    return 400, {"ok": False,
                                 "errors": ["add your name before marking the file reviewed"]}
                data["annotator"] = annotator
            elif annotator:
                data["annotator"] = annotator

            errors = gold_module.validate_gold(data, expected_slug=slug)
            if errors:
                return 400, {"ok": False, "errors": errors}

            _write_atomic(self.gold_path(slug), data)
            self._audit(slug, "reviewed" if reviewed else "draft-saved", len(chapters))
        return 200, {"ok": True, "document": self.doc_state(slug)}

    def _audit(self, slug: str, action: str, chapters: int) -> None:
        SCRATCH.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().isoformat(timespec="seconds")
        with AUDIT_LOG.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp}\t{action}\t{slug}\t{chapters} chapters\n")


class Handler(BaseHTTPRequestHandler):
    server_version = "GoldReview/1.0"
    state: ReviewState  # set by serve()

    def log_message(self, fmt, *args):  # keep the console readable
        if args and str(args[0]).startswith(("4", "5")):
            super().log_message(fmt, *args)

    # -- helpers --------------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # The browser closed the connection (navigation, resize, tab
            # close). Nothing to do, and not an error worth printing.
            pass

    def _json(self, status: int, payload) -> None:
        self._send(status, _json_bytes(payload), "application/json; charset=utf-8")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 4_000_000:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    # -- routes ---------------------------------------------------------
    def do_GET(self):  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            return self._static("index.html", "text/html; charset=utf-8")
        if path == "/app.css":
            return self._static("app.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self._static("app.js", "text/javascript; charset=utf-8")
        if path == "/api/state":
            return self._json(200, self.state.all_state())
        if path == "/api/health":
            return self._json(200, {"ok": True})
        if path.startswith("/images/"):
            return self._image(path[len("/images/"):])
        return self._json(404, {"error": "not found"})

    def do_HEAD(self):  # noqa: N802
        return self.do_GET()

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/save":
            return self._json(404, {"error": "not found"})
        status, payload = self.state.save(self._body())
        return self._json(status, payload)

    # -- static ---------------------------------------------------------
    def _static(self, name: str, content_type: str) -> None:
        path = APP_DIR / name
        if not path.exists():
            return self._json(500, {"error": f"missing {name}"})
        self._send(200, path.read_bytes(), content_type)

    def _image(self, relative: str) -> None:
        parts = relative.split("/")
        # Only /images/<slug>/page-NNN.png — no traversal.
        if (len(parts) != 2 or not parts[0] or not parts[1].endswith(".png")
                or "/" in parts[0] or ".." in parts[1]):
            return self._json(400, {"error": "bad image path"})
        slug, name = parts
        path = (IMAGES_DIR / slug / name).resolve()
        if IMAGES_DIR.resolve() not in path.parents or not path.exists():
            return self._json(404, {"error": "no image"})
        self._send(200, path.read_bytes(), "image/png")


def serve(host: str, port: int, gold_dir: Path, refresh_images: bool) -> None:
    state = ReviewState(gold_dir=gold_dir, refresh_images=refresh_images)
    print("Preparing document state and page images…", flush=True)
    snapshot = state.all_state()
    print(f"{snapshot['reviewed']}/{snapshot['total']} documents reviewed.", flush=True)
    Handler.state = state

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Review page: http://localhost:{port}", flush=True)
    if host in ("0.0.0.0", "::"):
        for address in lan_addresses():
            print(f"             http://{address}:{port}", flush=True)
    print("Ctrl-C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="LAN review page for gold chapter lists")
    parser.add_argument("--host", default="0.0.0.0", help="bind address (default: all interfaces)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--gold", default=str(GOLD_DIR), help="gold directory")
    parser.add_argument("--refresh-images", action="store_true",
                        help="re-render every page image even if cached")
    args = parser.parse_args(argv)
    serve(args.host, args.port, Path(args.gold), args.refresh_images)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
