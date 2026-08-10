from lib.cli_utils import filter_by_doc
from lib.file_utils import IncrementalWriter


def test_filter_by_doc_keeps_only_the_named_document():
    data = {"metadata": {"step": "x"},
            "results": [{"doc_slug": "a"}, {"doc_slug": "b"}]}
    assert filter_by_doc(data, "a") == {"metadata": {"step": "x"},
                                        "results": [{"doc_slug": "a"}]}


def test_filter_by_doc_returns_input_unchanged_when_slug_is_none():
    data = {"results": [{"doc_slug": "a"}]}
    assert filter_by_doc(data, None) is data


def test_filter_by_doc_does_not_mutate_its_input():
    data = {"results": [{"doc_slug": "a"}, {"doc_slug": "b"}]}
    filter_by_doc(data, "a")
    assert len(data["results"]) == 2


def test_target_key_evicts_only_that_record(tmp_path):
    from lib.file_utils import write_json
    output = tmp_path / "output.json"
    write_json(output, {"metadata": {}, "results": [
        {"doc_slug": "a", "n": 1}, {"doc_slug": "b", "n": 2}]})

    writer = IncrementalWriter(output, "s", key_field="doc_slug", target_key="a")

    assert writer.processed_keys == {"b"}
    assert [r["doc_slug"] for r in writer.results] == ["b"]


def test_target_key_is_a_no_op_when_the_key_is_absent(tmp_path):
    from lib.file_utils import write_json
    output = tmp_path / "output.json"
    write_json(output, {"metadata": {}, "results": [{"doc_slug": "b", "n": 2}]})

    writer = IncrementalWriter(output, "s", key_field="doc_slug", target_key="a")

    assert writer.processed_keys == {"b"}
