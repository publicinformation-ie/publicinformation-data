import pytest

from scripts.cli_utils import filter_by_public_body


def test_filter_results_key():
    data = {"results": [{"public_body_id": 1001}, {"public_body_id": 1002}]}
    out = filter_by_public_body(data, 1001)
    assert out == {"results": [{"public_body_id": 1001}]}


def test_filter_public_bodies_key():
    data = {"public_bodies": [{"public_body_id": 1001}, {"public_body_id": 1002}]}
    out = filter_by_public_body(data, 1002)
    assert out == {"public_bodies": [{"public_body_id": 1002}]}


def test_filter_none_returns_unchanged():
    data = {"results": [{"public_body_id": 1001}]}
    assert filter_by_public_body(data, None) is data


def test_filter_no_match_gives_empty_array():
    data = {"results": [{"public_body_id": 1001}]}
    assert filter_by_public_body(data, 9999) == {"results": []}


def test_filter_preserves_metadata():
    data = {"metadata": {"step": "s"}, "results": [{"public_body_id": 1001}, {"public_body_id": 1002}]}
    out = filter_by_public_body(data, 1001)
    assert out["metadata"] == {"step": "s"}
    assert out["results"] == [{"public_body_id": 1001}]


def test_filter_does_not_mutate_input():
    data = {"results": [{"public_body_id": 1001}, {"public_body_id": 1002}]}
    filter_by_public_body(data, 1001)
    assert len(data["results"]) == 2
