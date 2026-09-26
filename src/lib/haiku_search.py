"""Cached Claude Haiku web search for a public body's website.

The full raw API response (all turns, including web_search_tool_result blocks)
is cached before interpretation, so a search is never paid for twice.
Interpretation lives in lib.website_candidates.interpret_haiku.
"""
from lib.response_cache import ResponseCache

HAIKU_MODEL = "claude-haiku-4-5"
WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 3,
    "user_location": {"type": "approximate", "country": "IE"},
}


def build_search_prompt(body: dict) -> str:
    return (
        "Find the official website of this Irish public body using web search.\n\n"
        f"Name: {body.get('name', '')}\n"
        f"Legal status: {body.get('legal_status') or 'unknown'}\n"
        f"Parent organisation: {body.get('parent_name') or 'none'}\n"
        f"Government department: {body.get('government_department') or 'none'}\n"
        f"CRO number: {body.get('cro') or 'unknown'}\n\n"
        "Notes:\n"
        "- Many of these bodies are administrative subsidiaries of a parent public body and have NO "
        "website of their own. That is an acceptable answer.\n"
        "- Company directories (solocheck, vision-net, opencorporates, etc.) and social media are NOT "
        "the body's website, but they can show whether the company is dissolved.\n"
        "- Only give a URL you saw in the search results.\n\n"
        "Finish with ONLY this JSON:\n"
        '{"own_site": "url or null", "own_site_evidence_url": "search result url or null", '
        '"parent_site": "url or null", "has_own_site": "yes|no|unknown", '
        '"defunct": "yes|no|unknown", "defunct_source": "url or null", "notes": "one sentence"}'
    )


def fetch_raw(body: dict, cache: ResponseCache, *, client=None, refresh: bool = False,
              max_continuations: int = 2) -> tuple[dict, bool]:
    prompt = build_search_prompt(body)
    key = ResponseCache.key("haiku", HAIKU_MODEL, WEB_SEARCH_TOOL, prompt)
    if not refresh and (hit := cache.get(key)) is not None:
        return hit, False

    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    messages = [{"role": "user", "content": prompt}]
    dumps = []
    for _ in range(max_continuations + 1):
        msg = client.messages.create(model=HAIKU_MODEL, max_tokens=2000,
                                     tools=[WEB_SEARCH_TOOL], messages=messages)
        dumps.append(msg.model_dump(mode="json"))
        if msg.stop_reason != "pause_turn":
            break
        messages = messages + [{"role": "assistant", "content": msg.content}]
    record = cache.put(key, {"model": HAIKU_MODEL, "prompt": prompt, "responses": dumps})
    return record, True
