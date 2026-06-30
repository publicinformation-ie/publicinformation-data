import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from lib.http_utils import fetch, is_safe_url

FILE_EXTENSIONS = {".pdf": "pdf", ".xlsx": "xlsx", ".xls": "xls"}
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")

_FOI_KEYWORDS = ['disclosure', 'foi-log', 'foi_log', 'published-foi-requests', 'foi-decisions', 'foi-request', 'freedom-of-information']
_NEGATIVE_KEYWORDS = [
    'policy', 'scheme', 'guide', 'minutes', 'report', 'annual', 'agenda',
    'protected-disclosure', 'annual-report', 'debaterecord', 'governance',
    'committee_on', 'strategic-plan', 'climate-action', 'expense',
    'diary', 'mou', 'lrd-opinion', 'planningapplicationsrefused',
    'fiscal', 'committee', 'planning-application', 'code', 'statement', 'plan', 'press', 'elections',
    'strategy', 'leaflet', 'article', 'application form', '-form', '_form', 'assessment', 'tax', 'grants',
    'template', 'award', 'irishstatute', 'conference', 'training', 'guidance',
    'media-release', 'transcript', 'video-transcript', 'video',
    'audit', 'disability', 'complaints', 'procedure', 'customer-charter', 'lobbying',
    'data-privacy', 'data-protection', 'privacy', 'privacy-notice', 'terms-of-reference',
    'model-contract', 'written-resolution', 'board-resolution',
    'circular', 'bill', 'legislation', 'act', 'image', 'exhibit', 'worksheet',
    'book-list', 'booklist', 'newsletter', 'brochure', 'pamphlet', 'poster',
    'presentation', 'slides', 'meeting', 'session',
    'financial-stability-review', 'financial-stability-notes', 'quarterly-bulletin',
    'economic-letter',
    'visitor-numbers', 'heritage',
    'calendar',
    'rent-review', 'carnival',
    '_january_-_march', '_april_-_june', '_july_-_september', '_october_-_december',
]

_NON_IRISH_DOMAINS = {"cookcountystatesattorney.org"}
_GENERIC_LINK_TEXTS = {"download", "pdf", "here", "click here", "view", "open", ""}
_POSITIVE_LINK_TEXTS = [
    "disclosure log", "foi log", "foi disclosure", "foi record",
    "disclosure record", "published requests", "foi request log",
]
_NEGATIVE_LINK_TEXTS = [
    "election result", "visitor number", "financial stability",
    "economic letter", "quarterly bulletin", "heritage services", "emergency number",
    "traveller accommodation", "carnival", "rent scheme",
]


def _score_link(url, link_text):
    """Score a URL + anchor text: returns 1 (accept) or -1000 (reject)."""
    url_lower = str(url).lower()
    url_path = urlparse(url_lower).path
    filename = Path(url_path).name

    # Tier 1 — Hard URL rejects
    if 'protected' in url_lower and 'disclosure' in url_lower:
        return -1000
    if 'irishstatutebook' in url_lower:
        return -1000
    if 'application-form' in url_lower or 'application_form' in url_lower:
        return -1000
    if ('-form' in filename or '_form' in filename) and any(k in url_lower for k in _FOI_KEYWORDS):
        return -1000
    if filename in ('foi-request.pdf', 'foi-application.pdf'):
        return -1000
    domain = urlparse(url_lower).netloc
    if any(domain == d or domain.endswith('.' + d) for d in _NON_IRISH_DOMAINS):
        return -1000

    # Tier 2 — Link text signals
    text_lower = link_text.lower().strip()
    if text_lower not in _GENERIC_LINK_TEXTS:
        if any(pos in text_lower for pos in _POSITIVE_LINK_TEXTS):
            return 1
        if any(neg in text_lower for neg in _NEGATIVE_LINK_TEXTS):
            return -1000

    # Tier 3 — URL keyword scoring
    has_positive = any(k in url_lower for k in _FOI_KEYWORDS)
    if not has_positive:
        for k in _NEGATIVE_KEYWORDS:
            if k in url_path:
                return -1000
    return 1


def find_file_links(html, base_url, follow_year_pages=True):
    soup = BeautifulSoup(html, "html.parser")
    files = []
    year_page_urls = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        full_url = urljoin(base_url, href)

        if not is_safe_url(full_url):
            continue

        link_text = link.get_text(strip=True)
        if _score_link(full_url, link_text) < 0:
            continue

        ext = Path(urlparse(href).path).suffix.lower()

        if ext in FILE_EXTENSIONS:
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                files.append({"file_url": full_url, "file_type": FILE_EXTENSIONS[ext], "link_text": link_text})
        elif follow_year_pages and YEAR_PATTERN.search(link_text):
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                year_page_urls.append(full_url)

    if follow_year_pages:
        for year_url in year_page_urls:
            try:
                resp = fetch("GET", year_url, allow_redirects=True)
                for f in find_file_links(resp.text, year_url, follow_year_pages=False):
                    if f["file_url"] not in seen_urls:
                        seen_urls.add(f["file_url"])
                        files.append(f)
            except Exception:
                pass

    return files
