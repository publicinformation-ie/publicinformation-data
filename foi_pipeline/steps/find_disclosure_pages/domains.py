from urllib.parse import urlparse

from scripts.http_utils import is_safe_url, search_serper, validate_url_or_raise


def find_disclosure_page(name: str, foi_url: str) -> str | None:
    netloc = urlparse(foi_url).netloc
    if netloc.endswith("gov.ie"):
        return _find_gov_ie(name, foi_url)
    return None


def _find_gov_ie(name: str, foi_url: str) -> str | None:
    query = f'"{name}" foi disclosure log site:gov.ie'
    results = search_serper(query)
    for result in results:
        link = result.get("link", "")
        if not is_safe_url(link):
            continue
        try:
            validate_url_or_raise(link, context=f"gov_ie_serper_{name}")
        except ValueError:
            continue
        return link
    return None
