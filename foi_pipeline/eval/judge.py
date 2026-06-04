"""LLM-as-judge client for subjective eval steps.

Provider-agnostic: the backend is selected by environment config, so you can
use a frontier API (Anthropic, OpenAI) or a local OpenAI-compatible server
(Ollama, vLLM, LM Studio) depending on the cost/quality tradeoff. The metric
stays deterministic because judgments are cached by content hash in each step's
judgments.json and human-verified; this module only fills cache misses.
Temperature is pinned to 0 for every backend.

Configuration (env):
    EVAL_JUDGE_PROVIDER  "anthropic" | "openai"        (default "anthropic")
    EVAL_JUDGE_MODEL     model id                       (provider-specific default)
    EVAL_JUDGE_BASE_URL  OpenAI-compatible base URL     (openai provider; local models)
    ANTHROPIC_API_KEY / OPENAI_API_KEY                  (local servers accept any/empty key)
"""
import os

JUDGE_TEMPERATURE = 0.0

_DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
}


class JudgeUnavailable(RuntimeError):
    """Raised when a judgment is needed but no cached value and no usable backend."""


def judge_provider() -> str:
    return os.environ.get("EVAL_JUDGE_PROVIDER", "anthropic")


def judge_model() -> str:
    provider = judge_provider()
    return os.environ.get("EVAL_JUDGE_MODEL") or _DEFAULT_MODELS.get(provider, "unknown")


def judge_model_id() -> str:
    """Provenance string for EvalResults.judge_model, e.g. 'openai:gpt-4o-mini'."""
    return f"{judge_provider()}:{judge_model()}"


def _parse(text: str) -> tuple[str, str]:
    """Parse '<label> | <rationale>' into (label, rationale)."""
    label, _, rationale = text.partition("|")
    return label.strip().lower(), rationale.strip()


def _anthropic_call(prompt: str, model: str) -> str:
    import anthropic  # imported lazily so tests never need any SDK
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", "not-needed"))
    resp = client.messages.create(
        model=model, max_tokens=200, temperature=JUDGE_TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def _openai_call(prompt: str, model: str) -> str:
    # Works for OpenAI and any OpenAI-compatible local server (Ollama, vLLM,
    # LM Studio) via EVAL_JUDGE_BASE_URL; local servers usually accept any key.
    import openai  # imported lazily so tests never need any SDK
    client = openai.OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", "not-needed"),
        base_url=os.environ.get("EVAL_JUDGE_BASE_URL"),  # None -> api.openai.com
    )
    resp = client.chat.completions.create(
        model=model, max_tokens=200, temperature=JUDGE_TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


_BACKENDS = {"anthropic": _anthropic_call, "openai": _openai_call}


def default_api_fn(prompt: str) -> str:
    """Dispatch to the configured provider backend. Raises JudgeUnavailable for
    an unknown provider so the caller's 'cannot judge' path triggers cleanly."""
    backend = _BACKENDS.get(judge_provider())
    if backend is None:
        raise JudgeUnavailable(f"Unknown EVAL_JUDGE_PROVIDER: {judge_provider()!r}")
    return backend(prompt, judge_model())


def judge(key: str, prompt: str, cache: dict, api_fn=default_api_fn) -> tuple[str, str]:
    """Return (label, rationale) for key, using cache first.

    On cache miss, calls api_fn(prompt); writes {label, rationale, verified:'auto'}
    back into cache. Raises JudgeUnavailable if a call is needed but api_fn is None.

    Cache entries with verified='mock' are treated as valid cache hits — they are
    synthetic heuristic labels (not LLM-generated) and are returned as-is without
    making an API call. The evaluate.py caller is responsible for distinguishing
    mock from human-verified entries via the 'verified' field.
    """
    if key in cache:
        entry = cache[key]
        return entry["label"], entry.get("rationale", "")

    if api_fn is None:
        raise JudgeUnavailable(f"No cached judgment for {key!r} and no API available")

    label, rationale = _parse(api_fn(prompt))
    cache[key] = {"label": label, "rationale": rationale, "verified": "auto"}
    return label, rationale
