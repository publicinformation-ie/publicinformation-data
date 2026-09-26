import csv

import pytest

from website_eval.sample_gold import GOLD_COLUMNS, sample, write_csv
from website_eval.website_metrics import load_gold, score


def body(i, url=None, sub="Commercial Non-Financial Corporations"):
    return {"public_body_id": i, "name": f"B{i}", "parent_name": None, "legal_status": "x",
            "cro": None, "description_for_sub_sector": sub, "official_website_url": url,
            "llm_website_url": None}


def test_sample_sizes_and_determinism():
    bodies = [body(i) for i in range(200)] + [body(1000 + i, f"https://{i}.ie/") for i in range(100)]
    a = sample(bodies, {}, n_unresolved=80, n_resolved=20)
    b = sample(bodies, {}, n_unresolved=80, n_resolved=20)
    assert [r["public_body_id"] for r in a] == [r["public_body_id"] for r in b]
    assert sum(1 for r in a if r["existing_url"]) == 20 and len(a) == 100


def test_sample_prefills_foigovie_and_leaves_gold_blank():
    rows = sample([body(1)], {1: "www.x.ie"}, n_unresolved=1, n_resolved=0)
    assert rows[0]["foigovie_website"] == "www.x.ie"
    assert rows[0]["gold_status"] == "" and rows[0]["gold_url"] == ""


def test_write_csv_refuses_to_overwrite_labels(tmp_path):
    path = tmp_path / "gold.csv"
    rows = sample([body(1)], {}, n_unresolved=1, n_resolved=0)
    write_csv(rows, path, overwrite=False)
    with pytest.raises(FileExistsError):
        write_csv(rows, path, overwrite=False)


def _write_gold(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GOLD_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in GOLD_COLUMNS})


def test_load_gold_rejects_unlabelled_and_missing_url(tmp_path):
    p = tmp_path / "g.csv"
    _write_gold(p, [{"public_body_id": 1, "gold_status": ""},
                    {"public_body_id": 2, "gold_status": "own_site", "gold_url": ""},
                    {"public_body_id": 3, "gold_status": "no_own_site"}])
    with pytest.raises(ValueError) as e:
        load_gold(p)
    assert "1" in str(e.value) and "2" in str(e.value)


def test_score():
    rows = [
        {"gold_status": "own_site", "gold_url": "https://a.ie/", "website_status": "own_site",
         "official_website_url": "https://www.a.ie/"},                      # hit
        {"gold_status": "own_site", "gold_url": "https://b.ie/", "website_status": "own_site",
         "official_website_url": "https://wrong.ie/"},                      # wrong url
        {"gold_status": "own_site", "gold_url": "https://c.ie/", "website_status": "not_found",
         "official_website_url": None},                                      # false not_found
        {"gold_status": "no_own_site", "gold_url": "", "website_status": "no_own_site",
         "official_website_url": None},
        {"gold_status": "defunct", "gold_url": "", "website_status": "no_own_site",
         "official_website_url": None},
        {"gold_status": "unknown", "gold_url": "", "website_status": "own_site",
         "official_website_url": "https://z.ie/"},                          # excluded
    ]
    s = score(rows)
    assert s["n"] == 5
    assert s["own_coverage"] == pytest.approx(1 / 3)
    assert s["own_precision"] == pytest.approx(1 / 2)
    assert s["false_not_found_rate"] == pytest.approx(1 / 3)
    assert s["no_own_recall"] == 1.0 and s["no_own_precision"] == pytest.approx(1 / 2)
    assert s["defunct_recall"] == 0.0


def test_score_does_not_conflate_distinct_gov_ie_organisations():
    # regression: registrable_domain alone would call any gov.ie prediction a hit
    # for any gov.ie gold URL, inflating own_coverage/own_precision.
    rows = [{"gold_status": "own_site", "gold_url": "https://www.gov.ie/en/organisation/dept-a/",
            "website_status": "own_site",
            "official_website_url": "https://www.gov.ie/en/organisation/dept-b/"}]
    s = score(rows)
    assert s["own_coverage"] == 0.0 and s["own_precision"] == 0.0
