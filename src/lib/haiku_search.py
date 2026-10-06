"""Haiku web-search prompt shared by the Claude Code exchange (no API calls; spec §11)."""

HAIKU_MODEL = "claude-haiku-4-5"


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
