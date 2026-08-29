"""LLM verification gate for candidate website URLs.

Given an Irish public body's name and a candidate website URL, asks an LLM whether
the URL is actually that body's official website (not a similarly-named different
entity and not an unrelated organisation). Used by `resolve_website_urls` to reject
false-positive URLs before they are written to `official_website_url`.

Dependency-light: the default backend is the Opencode OpenAI-compatible gateway via
plain ``requests`` (no ``openai`` SDK required), mirroring ``eval/judge.py``. It is
env-configurable and **fails open**: on any error, missing key, or ``unsure`` verdict
the caller is told to keep the candidate URL so CI without a key is never broken.

Configuration (env):
    VERIFY_PROVIDER   "opencode" (default) | "openai" | "anthropic" | "mistral"
    VERIFY_MODEL      model id (default "deepseek-v4-flash" for opencode)
    VERIFY_BASE_URL   OpenAI-compatible base URL (default "https://opencode.ai/zen/go/v1")
    VERIFY_API_KEY    API key (default: read from ~/.local/share/opencode/auth.json -> opencode-go)
"""
import json
import os
from pathlib import Path

VERIFY_TEMPERATURE = 0.0

_OPENCODE_DEFAULT_BASE = "https://opencode.ai/zen/go/v1"
_OPENCODE_DEFAULT_MODEL = "deepseek-v4-flash"

_DEFAULT_MODELS = {
    "opencode": _OPENCODE_DEFAULT_MODEL,
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "mistral": "mistral-small-latest",
}

_LABELS = {"correct", "incorrect", "unsure"}


def verify_provider() -> str:
    return os.environ.get("VERIFY_PROVIDER", "opencode")


def verify_model() -> str:
    provider = verify_provider()
    return os.environ.get("VERIFY_MODEL") or _DEFAULT_MODELS.get(provider, "unknown")


def _opencode_api_key() -> str | None:
    key = os.environ.get("VERIFY_API_KEY") or os.environ.get("OPENCODE_API_KEY")
    if key:
        return key
    auth = Path.home() / ".local/share/opencode/auth.json"
    if auth.exists():
        data = json.loads(auth.read_text())
        for prov in ("opencode-go", "opencode"):
            if data.get(prov, {}).get("key"):
                return data[prov]["key"]
    return None


def _call_opencode(prompt: str, model: str) -> str:
    import requests  # lazy import
    base = os.environ.get("VERIFY_BASE_URL", _OPENCODE_DEFAULT_BASE).rstrip("/")
    key = _opencode_api_key()
    if not key:
        raise RuntimeError("no Opencode API key found")
    resp = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": VERIFY_TEMPERATURE,
            "max_tokens": 40,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    if not resp.ok:
        raise RuntimeError(f"Opencode HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json()["choices"][0]["message"]["content"]


def _call_backend(prompt: str, model: str) -> str:
    provider = verify_provider()
    if provider == "opencode":
        return _call_opencode(prompt, model)
    if provider == "openai":
        import openai
        client = openai.OpenAI(
            api_key=os.environ.get("VERIFY_API_KEY", "not-needed"),
            base_url=os.environ.get("VERIFY_BASE_URL"),
        )
        resp = client.chat.completions.create(
            model=model, temperature=VERIFY_TEMPERATURE, max_tokens=40,
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.choices[0].message.content
        return content if isinstance(content, str) else ""
    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        resp = client.messages.create(
            model=model, max_tokens=40, temperature=VERIFY_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
        )
        return getattr(resp.content[0], "text", "")
    if provider == "mistral":
        from mistralai.client import Mistral
        client = Mistral(api_key=os.environ.get("MISTRAL_API_KEY"))
        resp = client.chat.complete(
            model=model, max_tokens=40, temperature=VERIFY_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}],
        )
        message = resp.choices[0].message
        content = message.content if message else None
        return content if isinstance(content, str) else ""
    raise RuntimeError(f"unknown VERIFY_PROVIDER: {provider!r}")


def _build_prompt(name: str, url: str) -> str:
    return (
        "You are verifying whether a website URL is the official website of a "
        "specific Irish public body (not a similarly-named different entity, and "
        "not an unrelated organisation).\n\n"
        f"Public body name: {name}\n"
        f"Candidate URL: {url}\n\n"
        "Answer strictly as: <correct|incorrect|unsure> | <one-line rationale>"
    )


def verify_website_url(name: str, url: str, api_fn=None) -> str:
    """Return 'correct' | 'incorrect' | 'unsure' for (body name, candidate url).

    Never raises: any failure (no key, network, bad provider, unrecognised label)
    degrades to 'unsure' so the caller fails open. ``api_fn`` is injectable for
    tests/experiments (signature ``(prompt) -> str``); when omitted the configured
    backend is used.
    """
    if not name or not url:
        return "unsure"
    try:
        if api_fn is None:
            text = _call_backend(_build_prompt(name, url), verify_model())
        else:
            text = api_fn(_build_prompt(name, url))
    except Exception:
        return "unsure"
    label, _, _ = text.partition("|")
    label = label.strip().lower()
    return label if label in _LABELS else "unsure"
