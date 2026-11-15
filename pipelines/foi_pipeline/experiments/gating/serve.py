"""Stdlib LAN server for a round's review page. Serves round_dir/review, cached PDFs of round files, saves verdicts.

  uv run python -m experiments.gating.serve --round-dir D [--host H] [--port 8765]
"""
import argparse
import json
import re
import socket
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from experiments.gating.paths import pdf_bytes

MAX_BODY = 64 * 1024
_PDF = re.compile(r"^/pdf/([0-9a-f]{64})\.pdf$")
_TYPES = {".html": "text/html; charset=utf-8", ".png": "image/png", ".json": "application/json"}


def lan_address() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.0.2.1", 9))  # no packet is sent
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return "127.0.0.1"


def make_server(round_dir: Path, host: str, port: int) -> ThreadingHTTPServer:
    round_dir = Path(round_dir).resolve()
    review = (round_dir / "review").resolve()
    vpath = round_dir / "verdicts.json"
    lock = threading.Lock()

    def read_verdicts() -> dict:
        return json.loads(vpath.read_text()) if vpath.is_file() else {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code: int, body: bytes = b"", ctype: str = "text/plain"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == "/verdicts":
                with lock:
                    return self._send(200, json.dumps(read_verdicts()).encode(), "application/json")
            if path == "/":  # the page's links are relative to /review/
                self.send_response(302)
                self.send_header("Location", "/review/index.html")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if path.startswith("/review/"):
                rel = path[len("/review/"):]
                p = (review / rel).resolve()
                if p != review and review not in p.parents or not p.is_file():
                    return self._send(404, b"not found")
                return self._send(200, p.read_bytes(), _TYPES.get(p.suffix, "application/octet-stream"))
            m = _PDF.match(path)
            if m:
                try:
                    files = json.loads((round_dir / "results.json").read_text())["files"]
                except (OSError, ValueError, KeyError):
                    return self._send(404, b"not found")
                url = next((u for u, f in files.items() if f.get("sha256") == m.group(1)), None)
                data = pdf_bytes(url) if url else None
                if data is None:
                    return self._send(404, b"not found")
                return self._send(200, data, "application/pdf")
            self._send(404, b"not found")

        def do_POST(self):
            if urlsplit(self.path).path != "/verdict":
                return self._send(404, b"not found")
            origin = self.headers.get("Origin")
            if origin is not None and urlsplit(origin).netloc != self.headers.get("Host"):
                return self._send(403, b"forbidden origin")
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                return self._send(400, b"content-type must be application/json")
            try:
                n = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._send(400, b"bad length")
            if n <= 0 or n > MAX_BODY:
                return self._send(400, b"bad size")
            try:
                d = json.loads(self.rfile.read(n))
                key, text, tags = d["key"], d["text"], d["tags"]
                ok = (isinstance(key, str) and key and isinstance(text, str)
                      and isinstance(tags, list) and all(isinstance(t, str) for t in tags))
            except (ValueError, KeyError, TypeError):
                ok = False
            if not ok:
                return self._send(400, b"bad verdict")
            with lock:
                v = read_verdicts()
                v[key] = {"text": text, "tags": tags, "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                with tempfile.NamedTemporaryFile("w", dir=round_dir, suffix=".tmp", delete=False) as t:
                    t.write(json.dumps(v, indent=1))
                Path(t.name).replace(vpath)
            self._send(200, b"{}", "application/json")

    return ThreadingHTTPServer((host, port), H)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round-dir", required=True)
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    host = a.host or lan_address()
    srv = make_server(Path(a.round_dir), host, a.port)
    print(f"http://{host}:{srv.server_address[1]}/")
    srv.serve_forever()


if __name__ == "__main__":
    main()
