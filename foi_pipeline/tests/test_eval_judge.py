import pytest

import eval_judge


def test_judge_uses_cache_and_skips_api():
    cache = {"key1": {"label": "yes", "rationale": "looks FOI", "verified": "auto"}}
    calls = []

    def fake_api(prompt):
        calls.append(prompt)
        return "no | should not be called"

    label, rationale = eval_judge.judge(
        "key1", "prompt text", cache, api_fn=fake_api
    )
    assert label == "yes"
    assert calls == []  # cache hit -> no API call


def test_judge_calls_api_on_cache_miss_and_writes_back():
    cache = {}

    def fake_api(prompt):
        return "yes | genuine disclosure"

    label, rationale = eval_judge.judge(
        "key2", "prompt text", cache, api_fn=fake_api
    )
    assert label == "yes"
    assert rationale == "genuine disclosure"
    assert cache["key2"]["label"] == "yes"
    assert cache["key2"]["verified"] == "auto"


def test_judge_raises_when_cache_miss_and_no_api():
    with pytest.raises(eval_judge.JudgeUnavailable):
        eval_judge.judge("key3", "prompt", {}, api_fn=None)


def test_parse_response_splits_label_and_rationale():
    assert eval_judge._parse("YES | because reasons") == ("yes", "because reasons")
    assert eval_judge._parse("__none__|cover page") == ("__none__", "cover page")


def test_judge_model_id_defaults_to_anthropic(monkeypatch):
    monkeypatch.delenv("EVAL_JUDGE_PROVIDER", raising=False)
    monkeypatch.delenv("EVAL_JUDGE_MODEL", raising=False)
    assert eval_judge.judge_model_id() == "anthropic:claude-haiku-4-5-20251001"


def test_judge_model_id_reflects_env_provider_and_model(monkeypatch):
    monkeypatch.setenv("EVAL_JUDGE_PROVIDER", "openai")
    monkeypatch.setenv("EVAL_JUDGE_MODEL", "qwen2.5:7b")
    assert eval_judge.judge_model_id() == "openai:qwen2.5:7b"


def test_default_api_fn_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("EVAL_JUDGE_PROVIDER", "nope")
    with pytest.raises(eval_judge.JudgeUnavailable):
        eval_judge.default_api_fn("prompt")
