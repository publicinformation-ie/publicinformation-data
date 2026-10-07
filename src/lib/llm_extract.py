# Effort plumbing (Task 1 probes rounds 1-2 + 1b, 2026-10-07, 9 live calls on
# opencode-go/deepseek-v4.1-flash via POST /zen/go/v1/chat/completions):
# - Gradient DEAD: suffix `model:low` -> 400; top-level `effort`, header
#   `x-opencode-effort`, and documented top-level `reasoning_effort`
#   (low vs max, trivial + hard prompts) all 200 with no effort effect.
#   Cause: DeepSeek P6 forces max when the agent profile (tools + session
#   headers, completed by the Go proxy even for minimal payloads) is
#   present; upstream valid values are low/high/max only.
# - Toggle LIVE (1b, 1 call): top-level `thinking: {"type": "disabled"}`
#   (SDK extra_body) -> reasoning_tokens 0 vs baseline 82, answer still
#   correct. ONLY the "none" level is implementable. Task 3: model axis +
#   binary thinking on/off; do NOT add reasoning_effort levels (ignored).
"""LLM structured JSON extraction for prose documents.

Given a system prompt and a user prompt, asks an LLM to return a JSON object
(generally a list of extracted records). Used by `extract_motions` to pull
motions out of council meeting minutes.

Dependency-light: the default backend is the Opencode OpenAI-compatible
gateway via plain ``requests`` (no ``openai`` SDK required), mirroring
``llm_verify.py``. It is env-configurable and **fails closed**: on any error,
missing key, or unparseable JSON the caller receives ``None`` and must log the
document to ``errors.json`` — never guess a partial record.

Configuration (env):
    MOTIONS_LLM_PROVIDER    "opencode" (default) | "openai" | "anthropic" | "mistral"
    MOTIONS_LLM_MODEL       model id (default "deepseek-v4-flash" for opencode)
    MOTIONS_LLM_BASE_URL    OpenAI-compatible base URL (default "https://opencode.ai/zen/go/v1").
                            Point it at "https://opencode.ai/zen/v1" for models that only
                            speak the Responses API (e.g. "muse-spark-1.3-contributor-free").
    MOTIONS_LLM_API_KEY     API key (default: read from ~/.local/share/opencode/auth.json -> opencode-go)
    MOTIONS_LLM_SESSION_ID  stable session id (default: uuid4 generated once per process)
"""
import json
import os
import uuid
from pathlib import Path

MOTIONS_TEMPERATURE = 0.0

_OPENCODE_DEFAULT_BASE = "https://opencode.ai/zen/go/v1"
_OPENCODE_DEFAULT_MODEL = "deepseek-v4-flash"

_DEFAULT_MODELS = {
    "opencode": _OPENCODE_DEFAULT_MODEL,
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "mistral": "mistral-small-latest",
}

MOTIONS_PROVIDERS = ("opencode", "openai", "anthropic", "mistral")

_session_id: str | None = None


def motions_provider() -> str:
    return os.environ.get("MOTIONS_LLM_PROVIDER", "opencode")


def motions_model() -> str:
    provider = motions_provider()
    return os.environ.get("MOTIONS_LLM_MODEL") or _DEFAULT_MODELS.get(provider, "unknown")


def motions_session_id() -> str:
    """Stable session id for the whole run: MOTIONS_LLM_SESSION_ID if set,
    else a uuid4 generated once per process (sent as x-opencode-session)."""
    global _session_id
    env = os.environ.get("MOTIONS_LLM_SESSION_ID")
    if env:
        return env
    if _session_id is None:
        _session_id = str(uuid.uuid4())
    return _session_id


def _opencode_api_key() -> str | None:
    key = os.environ.get("MOTIONS_LLM_API_KEY") or os.environ.get("OPENCODE_API_KEY")
    if key:
        return key
    auth = Path.home() / ".local/share/opencode/auth.json"
    if auth.exists():
        data = json.loads(auth.read_text())
        for prov in ("opencode-go", "opencode"):
            if data.get(prov, {}).get("key"):
                return data[prov]["key"]
    return None


def _call_opencode_responses(base: str, key: str, system: str, user: str, model: str,
                             effort: str | None = None) -> str:
    """Call the Zen Responses API (https://opencode.ai/zen/v1/responses).

    Used for models that don't speak chat/completions (e.g.
    "muse-spark-1.3-contributor-free"). The free tier requires the
    x-opencode-session header; without it the gateway returns
    MissingSessionID.

    The thinking on/off toggle is unverified on this path, so any
    non-None effort fails closed with ValueError.
    """
    if effort is not None:
        raise ValueError(f"effort={effort!r} is unverified on the Responses API path")
    import requests  # lazy import
    resp = requests.post(
        f"{base}/responses",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "x-opencode-session": motions_session_id(),
        },
        json={
            "model": model,
            "instructions": system,
            "input": user,
        },
        timeout=180,
    )
    if not resp.ok:
        raise RuntimeError(f"Opencode HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    if data.get("status") not in (None, "completed"):
        raise RuntimeError(f"Opencode response status: {data.get('status')}")
    texts = [
        chunk.get("text", "")
        for item in data.get("output", [])
        if item.get("type") == "message"
        for chunk in item.get("content", [])
        if chunk.get("type") == "output_text"
    ]
    return "".join(texts)


def _call_opencode(system: str, user: str, model: str, effort: str | None = None) -> str:
    import requests  # lazy import
    base = os.environ.get("MOTIONS_LLM_BASE_URL", _OPENCODE_DEFAULT_BASE).rstrip("/")
    key = _opencode_api_key()
    if not key:
        raise RuntimeError("no Opencode API key found")
    if base.endswith("/zen/v1"):
        return _call_opencode_responses(base, key, system, user, model, effort)
    if model.startswith("opencode-go/"):
        # The /zen/go/v1 gateway addresses models by bare id (as listed by
        # GET /models); the provider-qualified form is rejected with
        # 400 "Model is unavailable" (observed 2026-10-07: prefixed ids that
        # returned 200 earlier the same day started 400ing). Strip the
        # routing prefix client-side; anything else passes through untouched
        # and fails closed downstream if the gateway rejects it.
        model = model.removeprefix("opencode-go/")
    body = {
        "model": model,
        "temperature": MOTIONS_TEMPERATURE,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if effort is None:
        pass
    elif effort == "none":
        body["thinking"] = {"type": "disabled"}
    else:
        raise ValueError(f"untransmittable effort={effort!r}: only None or 'none' are supported")
    resp = requests.post(
        f"{base}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "x-opencode-session": motions_session_id(),
        },
        json=body,
        timeout=180,
    )
    if not resp.ok:
        raise RuntimeError(f"Opencode HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json()["choices"][0]["message"]["content"]


def _call_backend(system: str, user: str, model: str) -> str:
    return _call_backend_with_effort(system, user, model)


def _call_backend_with_effort(system: str, user: str, model: str,
                              effort: str | None = None) -> str:
    if effort is not None and effort != "none":
        raise ValueError(f"untransmittable effort={effort!r}: only None or 'none' are supported")
    provider = motions_provider()
    if provider == "opencode":
        return _call_opencode(system, user, model, effort)
    if effort is not None:
        raise ValueError(f"effort={effort!r} is unverified on provider {provider!r}")
    if provider == "openai":
        import openai  # pyright: ignore[reportMissingImports]  # optional EVAL_JUDGE_PROVIDER backend
        client = openai.OpenAI(
            api_key=os.environ.get("MOTIONS_LLM_API_KEY", "not-needed"),
            base_url=os.environ.get("MOTIONS_LLM_BASE_URL"),
        )
        # Ollama-specific: pass num_ctx via extra_body to limit context window
        extra_body = {}
        if os.environ.get("MOTIONS_LLM_NUM_CTX"):
            extra_body["num_ctx"] = int(os.environ["MOTIONS_LLM_NUM_CTX"])
        resp = client.chat.completions.create(
            model=model,
            temperature=MOTIONS_TEMPERATURE,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            extra_body=extra_body if extra_body else None,
        )
        content = resp.choices[0].message.content
        return content if isinstance(content, str) else ""
    if provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("MOTIONS_LLM_API_KEY")
        )
        resp = client.messages.create(
            model=model, max_tokens=4000, temperature=MOTIONS_TEMPERATURE,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return getattr(resp.content[0], "text", "")
    if provider == "mistral":
        from mistralai.client import Mistral
        client = Mistral(api_key=os.environ.get("MISTRAL_API_KEY") or os.environ.get("MOTIONS_LLM_API_KEY"))
        resp = client.chat.complete(
            model=model, max_tokens=4000, temperature=MOTIONS_TEMPERATURE,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        message = resp.choices[0].message
        content = message.content if message else None
        return content if isinstance(content, str) else ""
    raise RuntimeError(f"unknown MOTIONS_LLM_PROVIDER: {provider!r}")


def extract_json(system: str, user: str, api_fn=None, model: str | None = None,
               effort: str | None = None) -> dict | None:
    """Ask the configured LLM for a JSON object; return it parsed, or None.

    Never raises, with one exception: an untransmittable ``effort`` value
    (anything other than None or "none") raises ValueError fail-closed
    instead of being silently ignored. ``model`` defaults to
    ``motions_model()``; ``effort=None`` preserves the current request body
    exactly, while ``effort="none"`` disables thinking on the
    chat/completions path. ``api_fn`` is injectable for tests (signature
    ``(system, user, session_id) -> str``); when omitted the configured
    backend is used. Injected stubs bypass effort honouring (test-only) —
    any other failure (no key, network, bad provider, unparseable JSON)
    degrades to None so the caller fails closed.
    """
    if effort is not None and effort != "none":
        raise ValueError(f"untransmittable effort={effort!r}: only None or 'none' are supported")
    if api_fn is None:
        try:
            text = _call_backend_with_effort(system, user, model if model is not None else motions_model(), effort)
        except ValueError:
            raise
        except Exception:
            return None
    else:
        # Injected stubs are test-only and bypass effort honouring: any stub
        # failure, including ValueError, degrades to None like any other.
        try:
            text = api_fn(system, user, motions_session_id())
        except Exception:
            return None
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        # Tolerate a code-fenced JSON block around the payload.
        fenced = text.strip()
        if fenced.startswith("```"):
            fenced = fenced.split("```", 2)[1]
            fenced = fenced.lstrip("json").strip()
            try:
                return json.loads(fenced)
            except (json.JSONDecodeError, TypeError):
                return None
        return None
