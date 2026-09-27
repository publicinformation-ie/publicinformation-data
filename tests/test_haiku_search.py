from lib.haiku_search import build_search_prompt
from lib.website_candidates import interpret_haiku

BODY = {"public_body_id": 1, "name": "Health and Safety Authority", "legal_status": "Agency",
        "parent_name": None, "government_department": "Enterprise", "cro": None}


def response(text, results=None, stop="end_turn", searches=1, error=False):
    content = [{"type": "server_tool_use", "id": "s1", "name": "web_search", "input": {"query": "x"}}]
    if error:
        content.append({"type": "web_search_tool_result", "tool_use_id": "s1",
                        "content": {"type": "web_search_tool_result_error", "error_code": "unavailable"}})
    else:
        content.append({"type": "web_search_tool_result", "tool_use_id": "s1",
                        "content": [{"type": "web_search_result", "url": u, "title": t}
                                    for u, t in (results or [])]})
    content.append({"type": "text", "text": text})
    return {"content": content, "stop_reason": stop,
            "usage": {"input_tokens": 1000, "output_tokens": 80,
                      "server_tool_use": {"web_search_requests": searches}}}


GOOD_TEXT = ('```json\n{"own_site": "https://hsa.ie", "own_site_evidence_url": "https://www.hsa.ie/eng/", '
             '"parent_site": null, "has_own_site": "yes", "defunct": "no", "defunct_source": null, '
             '"notes": "official"}\n```')


def test_prompt_mentions_body():
    assert "Health and Safety Authority" in build_search_prompt(BODY)


def test_cited_own_site_becomes_candidate():
    raw = {"responses": [response(GOOD_TEXT, [("https://www.hsa.ie/eng/", "HSA"),
                                              ("https://www.solocheck.ie/x", "HSA listing")])]}
    out = interpret_haiku(raw)
    assert [c["url"] for c in out["candidates"]] == ["https://hsa.ie"]
    assert out["candidates"][0]["origin"] == "haiku_search"
    assert out["signals"]["has_own_site"] == "yes"
    assert [h["domain"] for h in out["directory_hits"]] == ["solocheck.ie"]
    assert out["search_count"] == 1 and out["usage"]["input_tokens"] == 1000


def test_uncited_own_site_is_rejected():
    text = GOOD_TEXT.replace("https://hsa.ie", "https://www.invented-hsa.ie")
    out = interpret_haiku({"responses": [response(text, [("https://www.hsa.ie/eng/", "HSA")])]})
    assert out["candidates"] == [] and out["rejected_uncited"] == ["https://www.invented-hsa.ie"]


def test_directory_own_site_is_never_a_candidate():
    text = GOOD_TEXT.replace("https://hsa.ie", "https://www.solocheck.ie/x")
    out = interpret_haiku({"responses": [response(text, [("https://www.solocheck.ie/x", "l")])]})
    assert out["candidates"] == []


def test_malformed_text_and_search_error_yield_empty():
    out = interpret_haiku({"responses": [response("no json here", error=True)]})
    assert out["candidates"] == [] and out["signals"]["has_own_site"] is None


def test_empty_raw():
    out = interpret_haiku({"responses": []})
    assert out["candidates"] == [] and out["search_count"] == 0


