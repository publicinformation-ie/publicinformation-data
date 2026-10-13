"""One-off research aid: fetch each policy's official landing page(s) and list
the PDFs they link to, as a review list for the user. Nothing is downloaded or
added to documents.yml here — the user approves candidates first.

Plain GETs through lib.http_utils.fetch (UA, SSRF guard, rate limit, bot
detection). No paid calls.
"""
import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from lib.http_utils import fetch
from policies import load_policies

DEFAULT_OUT = (Path(__file__).resolve().parents[2]
               / "docs" / "superpowers" / "research" / "2026-10-13-transport-pdf-candidates.md")

OPEN_ITEMS = (
    "#6/#7 share one generic TII page — pick the specific publication for each",
    "#16 has three regional URLs — one PDF per assembly, or only the one you want",
    "#12 BusConnects is a multi-document programme — choose which documents count",
    "#8 has a revised 2026-2028 successor — record original and successor separately only if published",
    "#13 Connecting Ireland — confirm the current governing plan",
    "Regional and Local EV Charging Network Plan 2025-2030 — attach to #8 only if verified as its child",
)


class _Anchors(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []          # (href, text)
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.anchors.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def extract_pdf_links(html: str, base_url: str) -> list:
    parser = _Anchors()
    parser.feed(html)
    parser.close()
    seen, links = set(), []
    for href, text in parser.anchors:
        if not href or href.startswith(("#", "mailto:", "javascript:")):
            continue
        url = urljoin(base_url, href)
        if not urlparse(url).path.lower().endswith(".pdf") or url in seen:
            continue
        seen.add(url)
        links.append({"url": url, "text": text})
    return links


def render_review_list(policies: list, results: dict) -> str:
    lines = [
        "# Transport policy PDF candidates — for review",
        "",
        "Generated from the landing pages in `input_plans_transport.md`. **Nothing here is in "
        "`documents.yml` yet.** For each policy, mark the PDFs to curate and the `policy_role` "
        "(`primary` / `action-plan` / `progress-report`).",
        "",
        "## Open items from the spec",
        "",
        *[f"- {item}" for item in OPEN_ITEMS],
        "",
        "## Candidates",
        "",
    ]
    for policy in policies:
        lines += [f"### {policy['number']}. {policy['title']}", f"`policy_id`: `{policy['policy_id']}`", ""]
        pages = results.get(policy["policy_id"], {}).get("pages", [])
        for page in pages:
            lines.append(f"Page: {page['url']}")
            if page["error"]:
                lines.append(f"- FETCH FAILED: {page['error']} (check manually in a browser)")
            elif not page["pdfs"]:
                lines.append("- no PDF links found on this page")
            for pdf in page["pdfs"]:
                lines.append(f"- [ ] {pdf['text'] or '(no link text)'} — {pdf['url']}")
            lines.append("")
        lines.append("Approve / reject: _____")
        lines.append("")
    return "\n".join(lines)


def collect(policies: list) -> dict:
    results = {}
    for policy in policies:
        pages = []
        for url in policy["source_urls"]:
            try:
                response = fetch("GET", url)
                response.raise_for_status()
                pages.append({"url": url, "error": None,
                              "pdfs": extract_pdf_links(response.text, url)})
            except Exception as e:                      # one bad page must not stop the survey
                pages.append({"url": url, "error": f"{type(e).__name__}: {e}", "pdfs": []})
        results[policy["policy_id"]] = {"pages": pages}
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    policies = load_policies()
    text = render_review_list(policies, collect(policies))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"Wrote review list for {len(policies)} policies to {args.out}")


if __name__ == "__main__":
    main()
