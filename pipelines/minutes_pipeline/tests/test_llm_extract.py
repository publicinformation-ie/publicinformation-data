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
