import argparse

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


from scripts.cli_utils import add_common_args


def test_add_common_args_parses_all_flags():
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    args = parser.parse_args(
        ["--input", "in.json", "--output", "out.json", "--force",
         "--verbose", "--public-body", "1001"]
    )
    assert args.input == "in.json"
    assert args.output == "out.json"
    assert args.force is True
    assert args.verbose is True
    assert args.public_body == 1001


def test_add_common_args_defaults():
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    args = parser.parse_args(["--input", "in.json", "--output", "out.json"])
    assert args.force is False
    assert args.verbose is False
    assert args.public_body is None


def test_add_common_args_public_body_must_be_int():
    parser = argparse.ArgumentParser()
    add_common_args(parser)
    with pytest.raises(SystemExit):
        parser.parse_args(["--input", "i", "--output", "o", "--public-body", "abc"])
