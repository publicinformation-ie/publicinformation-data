from steps.filter_phantom_rows.eval.evaluate import run_eval


def _item(url, rows, ftype="pdf", stats=None):
    d = {"file_url": url, "file_type": ftype, "rows": rows}
    if stats:
        d["filter_stats"] = stats
    return d


def test_clean_file_scores_clean():
    items = [_item("u1", [["h1", "h2", "h3"], ["a", "b", "c"]],
                   stats={"blank_rows_dropped": 2, "fragments_merged": 1})]
    results, issues = run_eval(items, input_hash="x")
    primary = results.metrics[0]
    assert primary.name == "post_filter_clean_rate"
    assert primary.value == 1.0
    assert issues == []


def test_leaked_split_row_flags_file():
    # a surviving single-value row across >=3 cols = a leaked phantom
    items = [_item("u1", [["h1", "h2", "h3"], ["a", "b", "c"], [None, "frag", None]])]
    results, issues = run_eval(items, input_hash="x")
    assert results.metrics[0].value == 0.0
