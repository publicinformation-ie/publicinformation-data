import json

import pytest

from lib import llm_extract
from lib.llm_extract import extract_json, motions_session_id


def _fake_opencode(system, user, session_id):
    # A fake backend that asserts the x-opencode-session header is threaded
    # through as the injected api_fn's session_id argument.
    assert session_id == "stable-test-session"
    return json.dumps({"motions": [{"motion_text": "That the council…",
                                    "status_label": "carried"}]})


def test_extract_json_returns_parsed_dict():
    result = extract_json("sys", "user", api_fn=lambda s, u, sid: '{"a": 1}')
    assert result == {"a": 1}


def test_extract_json_none_on_unparseable():
    result = extract_json("sys", "user", api_fn=lambda s, u, sid: "not json")
    assert result is None


def test_extract_json_none_on_exception():
    def boom(s, u, sid):
        raise RuntimeError("nope")
    assert extract_json("sys", "user", api_fn=boom) is None


def test_motions_session_id_stable_per_process(monkeypatch):
    monkeypatch.delenv("MOTIONS_LLM_SESSION_ID", raising=False)
    a = motions_session_id()
    b = motions_session_id()
    assert a == b
    import uuid
    uuid.UUID(a)  # is a valid uuid4


def test_motions_session_id_from_env(monkeypatch):
    monkeypatch.setenv("MOTIONS_LLM_SESSION_ID", "stable-test-session")
    assert motions_session_id() == "stable-test-session"


def test_motions_provider_default():
    assert llm_extract.motions_provider() == "opencode"


def test_opencode_sends_session_header_on_request(monkeypatch):
    """The opencode provider must send x-opencode-session on the actual
    HTTP request, asserted against a mocked requests.post."""
    captured = {}

    class FakeResp:
        ok = True

        def json(self):
            return {"choices": [{"message": {"content": '{"motions": []}'}}]}

    import lib.llm_extract as mod

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setenv("MOTIONS_LLM_SESSION_ID", "session-abc")
    monkeypatch.setattr(mod, "motions_provider", lambda: "opencode")
    monkeypatch.setattr(mod, "_opencode_api_key", lambda: "test-key")
    monkeypatch.setattr("requests.post", fake_post)

    result = mod.extract_json("sys", "user")
    assert result == {"motions": []}
    assert captured["headers"]["x-opencode-session"] == "session-abc"


def test_opencode_responses_path_for_zen_v1_base(monkeypatch):
    """With MOTIONS_LLM_BASE_URL=https://opencode.ai/zen/v1 the client must
    use the Responses API (instructions/input payload, output_text parsing)
    and still send x-opencode-session (required for the free tier)."""
    captured = {}

    class FakeResp:
        ok = True
        status_code = 200
        text = "{}"

        def json(self):
            return {"status": "completed",
                    "output": [{"type": "message",
                                "content": [{"type": "output_text",
                                             "text": '{"motions": []}'},
                                            {"type": "reasoning",
                                             "text": "ignored"}]}]}

    import lib.llm_extract as mod

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = json
        return FakeResp()

    monkeypatch.setenv("MOTIONS_LLM_BASE_URL", "https://opencode.ai/zen/v1")
    monkeypatch.setenv("MOTIONS_LLM_SESSION_ID", "session-abc")
    monkeypatch.setattr(mod, "motions_provider", lambda: "opencode")
    monkeypatch.setattr(mod, "_opencode_api_key", lambda: "test-key")
    monkeypatch.setattr("requests.post", fake_post)

    result = mod.extract_json("sys", "user")
    assert result == {"motions": []}
    assert captured["url"] == "https://opencode.ai/zen/v1/responses"
    assert captured["headers"]["x-opencode-session"] == "session-abc"
    assert captured["payload"]["instructions"] == "sys"
    assert captured["payload"]["input"] == "user"


def test_extract_json_forwards_model_effort_to_backend(monkeypatch):
    import lib.llm_extract as mod
    captured = {}

    def fake_backend(system, user, model, effort=None):
        captured.update(model=model, effort=effort)
        return '{"motions": []}'

    monkeypatch.setattr(mod, "_call_backend_with_effort", fake_backend)
    assert mod.extract_json("s", "u", model="m", effort="none") == {"motions": []}
    assert (captured["model"], captured["effort"]) == ("m", "none")


def test_extract_json_rejects_untransmittable_effort():
    import lib.llm_extract as mod
    with pytest.raises(ValueError):
        mod.extract_json("s", "u", model="m", effort="low")


def _capture_chat_post(monkeypatch, model):
    """Run extract_json against a mocked chat/completions POST; return the
    (url, payload) the client sent for the given model id."""
    import lib.llm_extract as mod
    captured = {}

    class FakeResp:
        ok = True

        def json(self):
            return {"choices": [{"message": {"content": '{"motions": []}'}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        return FakeResp()

    monkeypatch.delenv("MOTIONS_LLM_BASE_URL", raising=False)
    monkeypatch.setattr(mod, "motions_provider", lambda: "opencode")
    monkeypatch.setattr(mod, "_opencode_api_key", lambda: "test-key")
    monkeypatch.setattr("requests.post", fake_post)
    assert mod.extract_json("s", "u", model=model) == {"motions": []}
    return captured


def test_opencode_go_strips_provider_prefix_on_wire(monkeypatch):
    """Provider-qualified opencode-go/<id> must go on the wire as the bare
    id: the /zen/go/v1 gateway rejects the prefixed form with 400
    'Model is unavailable' (observed 2026-10-07)."""
    captured = _capture_chat_post(monkeypatch, "opencode-go/deepseek-v4.1-flash")
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["model"] == "deepseek-v4.1-flash"


def test_opencode_go_bare_and_foreign_ids_pass_through(monkeypatch):
    """Bare ids are sent unchanged; unknown prefixes are NOT rewritten
    (the gateway rejects them and the caller fails closed downstream)."""
    captured = _capture_chat_post(monkeypatch, "deepseek-v4.1-flash")
    assert captured["payload"]["model"] == "deepseek-v4.1-flash"
    captured = _capture_chat_post(monkeypatch, "other-provider/some-model")
    assert captured["payload"]["model"] == "other-provider/some-model"
