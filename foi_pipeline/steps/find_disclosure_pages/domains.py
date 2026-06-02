from urllib.parse import urlparse

from scripts.http_utils import is_safe_url, validate_url_or_raise


def _gov_ie_query(name: str) -> str:
    return f'"{name}" publications foi disclosure log site:gov.ie'


def find_disclosure_page(
    name: str, foi_url: str, batch_results: dict | None = None
) -> str | None:
    netloc = urlparse(foi_url).netloc
    if netloc.endswith("gov.ie"):
        return _find_gov_ie(name, batch_results or {})
    return None


def _find_gov_ie(name: str, batch_results: dict) -> str | None:
    query = _gov_ie_query(name)
    results = batch_results.get(query, [])
    for result in results:
        link = result.get("link", "")
        if not is_safe_url(link):
            continue
        try:
            validate_url_or_raise(link, context=f"gov_ie_apify_{name}")
        except ValueError:
            continue
        return link
    return None
