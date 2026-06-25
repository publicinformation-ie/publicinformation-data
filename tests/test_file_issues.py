import pytest
from scripts.file_issues import group_errors, detect_dropped, collect_all_issues


def test_group_errors_by_type():
    errors = [
        {"error_type": "UnrecognizedRequesterType", "context": {"file_url": "https://a.com/1.pdf"}},
        {"error_type": "UnrecognizedRequesterType", "context": {"file_url": "https://a.com/1.pdf"}},
        {"error_type": "UnrecognizedRequesterType", "context": {"file_url": "https://a.com/2.pdf"}},
        {"error_type": "InsufficientColumns",        "context": {"file_url": "https://b.com/3.pdf"}},
    ]
    body_lookup = {
        "https://a.com/1.pdf": "Body A",
        "https://a.com/2.pdf": "Body A",
        "https://b.com/3.pdf": "Body B",
    }
    result = group_errors(errors, body_lookup)

    assert set(result.keys()) == {"UnrecognizedRequesterType", "InsufficientColumns"}
    assert result["UnrecognizedRequesterType"]["Body A"]["https://a.com/1.pdf"] == 2
    assert result["UnrecognizedRequesterType"]["Body A"]["https://a.com/2.pdf"] == 1
    assert result["InsufficientColumns"]["Body B"]["https://b.com/3.pdf"] == 1


def test_detect_dropped_files():
    prev = {"https://a.com/1.pdf", "https://a.com/2.pdf", "https://a.com/3.pdf"}
    nxt  = {"https://a.com/1.pdf", "https://a.com/3.pdf"}
    dropped = detect_dropped(prev, nxt)
    assert dropped == {"https://a.com/2.pdf"}


def test_detect_dropped_files_none_dropped():
    prev = {"https://a.com/1.pdf"}
    nxt  = {"https://a.com/1.pdf", "https://a.com/2.pdf"}
    assert detect_dropped(prev, nxt) == set()


def test_unknown_public_body_fallback():
    errors = [
        {"error_type": "SomeError", "context": {"file_url": "https://unknown.com/x.pdf"}},
    ]
    body_lookup = {}  # URL not present
    result = group_errors(errors, body_lookup)
    assert "(unknown)" in result["SomeError"]
    assert result["SomeError"]["(unknown)"]["https://unknown.com/x.pdf"] == 1


def test_missing_step_output_skipped():
    body_lookup = {"https://a.com/1.pdf": "Body A"}

    # All step outputs return None — should not crash, result should be empty
    result = collect_all_issues(
        body_lookup=body_lookup,
        step_names=["step_a", "step_b"],
        step_config={"step_a": ("results", True, False), "step_b": ("results", False, False)},
        load_output_fn=lambda step_name: None,
        load_errors_fn=lambda step_name: None,
    )
    assert result == {}


def test_collect_all_issues_detects_dropped_files():
    body_lookup = {
        "https://a.com/1.pdf": "Body A",
        "https://a.com/2.pdf": "Body A",
    }
    step_names = ["step_a", "step_b"]
    step_config = {
        "step_a": ("results", False, False),
        "step_b": ("results", False, False),
    }

    def load_output(step_name):
        if step_name == "step_a":
            return {"results": [
                {"file_url": "https://a.com/1.pdf"},
                {"file_url": "https://a.com/2.pdf"},
            ]}
        if step_name == "step_b":
            return {"results": [
                {"file_url": "https://a.com/1.pdf"},
                # https://a.com/2.pdf dropped
            ]}
        return None

    result = collect_all_issues(
        body_lookup=body_lookup,
        step_names=step_names,
        step_config=step_config,
        load_output_fn=load_output,
        load_errors_fn=lambda step_name: None,
    )

    assert "DroppedAt_step_b" in result
    assert "Body A" in result["DroppedAt_step_b"]
    assert "https://a.com/2.pdf" in result["DroppedAt_step_b"]["Body A"]
