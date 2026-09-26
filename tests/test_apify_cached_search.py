import pytest

from lib.apify_search import (ApifyBudgetExceeded, cached_search, estimate_cost_usd)
from lib.response_cache import ResponseCache


def fake_raw(calls):
    def _raw(queries):
        calls.append(list(queries))
        return {q: {"searchQuery": {"term": q}, "organicResults": [{"url": f"https://{i}.ie/"}]}
                for i, q in enumerate(queries)}
    return _raw


def test_estimate_cost():
    assert estimate_cost_usd(0) == 0
    assert estimate_cost_usd(100) == pytest.approx(0.451)


def test_second_call_is_free(tmp_path):
    calls = []
    cache = ResponseCache(tmp_path)
    items, paid = cached_search(["q1", "q2"], cache, raw_fn=fake_raw(calls), budget_fn=lambda: 5.0)
    assert paid == 2 and items["q1"]["organicResults"]
    items2, paid2 = cached_search(["q1", "q2"], cache, raw_fn=fake_raw(calls), budget_fn=lambda: 5.0)
    assert paid2 == 0 and len(calls) == 1 and items2 == items


def test_only_misses_are_fetched(tmp_path):
    calls = []
    cache = ResponseCache(tmp_path)
    cached_search(["q1"], cache, raw_fn=fake_raw(calls), budget_fn=lambda: 5.0)
    _, paid = cached_search(["q1", "q2"], cache, raw_fn=fake_raw(calls), budget_fn=lambda: 5.0)
    assert paid == 1 and calls[-1] == ["q2"]


def test_refresh_bypasses_cache(tmp_path):
    calls = []
    cache = ResponseCache(tmp_path)
    cached_search(["q1"], cache, raw_fn=fake_raw(calls), budget_fn=lambda: 5.0)
    _, paid = cached_search(["q1"], cache, refresh=True, raw_fn=fake_raw(calls), budget_fn=lambda: 5.0)
    assert paid == 1 and len(calls) == 2


def test_budget_exceeded_refuses_before_calling(tmp_path):
    calls = []
    with pytest.raises(ApifyBudgetExceeded):
        cached_search([f"q{i}" for i in range(200)], ResponseCache(tmp_path), reserve_usd=0.5,
                      raw_fn=fake_raw(calls), budget_fn=lambda: 1.0)
    assert calls == []


def test_query_with_no_item_is_cached_as_none(tmp_path):
    calls = []
    cache = ResponseCache(tmp_path)
    raw = lambda qs: (calls.append(qs) or {})
    items, paid = cached_search(["empty"], cache, raw_fn=raw, budget_fn=lambda: 5.0)
    assert items == {"empty": None} and paid == 1
    _, paid2 = cached_search(["empty"], cache, raw_fn=raw, budget_fn=lambda: 5.0)
    assert paid2 == 0 and len(calls) == 1
