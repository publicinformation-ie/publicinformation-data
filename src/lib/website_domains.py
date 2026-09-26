"""Domain helpers for website resolution.

Directory and social domains are never website candidates: search results on
them are recorded as evidence (``directory_hits``) instead. Extend the sets as
the experiment surfaces new directory domains.
"""
import re
from urllib.parse import urlparse

_CC_SECOND_LEVEL = {"co", "ac", "org", "net", "com"}

DIRECTORY_DOMAINS = frozenset({
    "solocheck.ie", "vision-net.ie", "cro.ie", "opencorporates.com",
    "duedil.com", "bizapedia.com", "corporationwiki.com", "kompass.com",
    "globaldatabase.com", "dnb.com", "northdata.com", "zoominfo.com",
    "crunchbase.com", "bloomberg.com", "rocketreach.co", "companieshouse.id",
    "irishcompanies.ie", "companyhub.ie", "infobel.com", "cylex.ie",
    "goldenpages.ie",
})

SOCIAL_DOMAINS = frozenset({
    "linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com",
    "youtube.com", "tiktok.com", "wikipedia.org",
})

_DISSOLUTION_RE = re.compile(
    r"\b(dissolved|struck[\s-]+off|strike[\s-]+off|in\s+liquidation|liquidated|ceased\s+trading)\b",
    re.IGNORECASE,
)


def registrable_domain(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    host = host.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    labels = [l for l in host.split(".") if l]
    if len(labels) < 2:
        return ""
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _CC_SECOND_LEVEL:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def root_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/"


def listing_kind(url: str) -> str | None:
    domain = registrable_domain(url)
    if domain in DIRECTORY_DOMAINS:
        return "directory"
    if domain in SOCIAL_DOMAINS:
        return "social"
    return None


def has_dissolution_marker(text: str) -> bool:
    return bool(text) and bool(_DISSOLUTION_RE.search(text))


def site_key(url: str) -> str:
    """Registrable domain, except gov.ie: gov.ie hosts hundreds of unrelated public
    bodies on one domain, so callers that dedupe/match "the same site" by domain
    (candidate dedup, blocked-origin grouping, gold-URL matching) must key gov.ie
    pages by their organisation path instead, or every gov.ie page collapses to one.
    """
    domain = registrable_domain(url)
    if domain != "gov.ie":
        return domain
    segments = [s for s in urlparse(url).path.lower().split("/") if s]
    return f"{domain}/{'/'.join(segments[:3])}"
