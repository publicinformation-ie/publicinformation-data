"""Judge whether a fetched page is a public body's own website.

Rule short-circuits run first (directory/social domain, CRO number on page),
then an LLM judge: local Ollama by default, escalating ``unsure`` to Haiku.
Fails closed: any backend error yields ``unsure``, which is never accepted.
"""
import json
import os
import re

import requests

from lib.response_cache import ResponseCache
from lib.website_domains import listing_kind

JUDGE_LABELS = {"own_site", "parent_site", "other_entity", "directory", "unsure"}
DEFAULT_PRIMARY = "ollama:" + os.environ.get("WEBSITE_JUDGE_MODEL", "gemma4:latest")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def build_prompt(body: dict, url: str, evidence: dict) -> str:
    return (
        "Decide whether a web page is the OWN official website of a specific Irish public body.\n\n"
        f"Body name: {body.get('name', '')}\n"
        f"Legal status: {body.get('legal_status') or 'unknown'}\n"
        f"Parent organisation: {body.get('parent_name') or 'none'}\n"
        f"Government department: {body.get('government_department') or 'none'}\n"
        f"CRO number: {body.get('cro') or 'unknown'}\n\n"
        f"Page URL: {url}\n"
        f"Page title: {evidence.get('title', '')}\n"
        f"Site name: {evidence.get('site_name', '')}\n"
        f"Meta description: {evidence.get('meta_description', '')}\n"
        f"First heading: {evidence.get('h1', '')}\n"
        f"Footer: {evidence.get('footer_text', '')}\n"
        f"Page text (start): {evidence.get('text_head', '')}\n\n"
        "Labels:\n"
        "- own_site: this page belongs to the body's own website\n"
        "- parent_site: this is the website of the body's parent/group; the body has no site of its own here\n"
        "- other_entity: a different organisation, a namesake, a news article, or unrelated\n"
        "- directory: a company directory or listing site\n"
        "- unsure: the evidence is insufficient\n\n"
        'Return ONLY JSON: {"label": "<one label>", "rationale": "<one sentence>"}'
    )


def parse_judge_response(text: str) -> tuple[str, str]:
    m = _JSON_RE.search(text or "")
    if not m:
        return "unsure", "unparsable response"
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return "unsure", "invalid json"
    label = str(data.get("label", "")).strip().lower()
    if label not in JUDGE_LABELS:
        return "unsure", f"unknown label {label!r}"
    return label, str(data.get("rationale", ""))


def _cro_on_page(cro, evidence: dict) -> bool:
    digits = re.sub(r"\D", "", str(cro or ""))
    if len(digits) < 4:
        return False
    text = f"{evidence.get('footer_text', '')} {evidence.get('text_head', '')}"
    return bool(re.search(rf"(?<!\d){digits}(?!\d)", text))


def _call_ollama(model: str, prompt: str) -> str:
    resp = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={"model": model, "messages": [{"role": "user", "content": prompt}],
              "format": "json", "stream": False, "options": {"temperature": 0}},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _call_backend(backend: str, prompt: str) -> str:
    if backend.startswith("ollama:"):
        return _call_ollama(backend.split(":", 1)[1], prompt)
    raise ValueError(f"backend {backend!r} has no built-in caller; pass api_fn")


def judge(body, url, evidence, backend: str = DEFAULT_PRIMARY, *, api_fn=None,
          cache: ResponseCache | None = None) -> dict:
    if listing_kind(url):
        return {"label": "directory", "rationale": "directory/social domain", "judge": "rule"}
    if evidence is None:
        return {"label": "unsure", "rationale": "no page evidence", "judge": "none"}
    if _cro_on_page(body.get("cro"), evidence):
        return {"label": "own_site", "rationale": "CRO number on page", "judge": "cro_match"}

    prompt = build_prompt(body, url, evidence)
    key = ResponseCache.key("judge", backend, prompt)
    if cache is not None and (hit := cache.get(key)) is not None:
        return hit["result"]
    try:
        text = api_fn(prompt) if api_fn is not None else _call_backend(backend, prompt)
        label, rationale = parse_judge_response(text)
    except Exception as e:  # fail closed
        return {"label": "unsure", "rationale": f"{type(e).__name__}: {str(e)[:150]}",
                "judge": backend}
    result = {"label": label, "rationale": rationale, "judge": backend}
    if cache is not None:
        cache.put(key, {"result": result})
    return result


def judge_cascade(body, url, evidence, *, primary: str = DEFAULT_PRIMARY,
                  fallback: str | None = None, primary_fn=None, fallback_fn=None,
                  cache: ResponseCache | None = None) -> dict:
    first = judge(body, url, evidence, primary, api_fn=primary_fn, cache=cache)
    if first["label"] != "unsure" or not fallback or first["judge"] in ("rule", "none"):
        return first
    return judge(body, url, evidence, fallback, api_fn=fallback_fn, cache=cache)
