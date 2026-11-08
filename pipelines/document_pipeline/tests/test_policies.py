from pathlib import Path

import pytest

import policies
from policies import POLICIES_PATH, load_policies, strip_footnote

HEADER = ("| Policy / Strategy Title | Primary Issuing Authority | Current Policy Horizon "
          "| Scope & Strategic Pillar | Core Statutory & Framework Linkages |\n"
          "| :---- | :---- | :---- | :---- | :---- |\n")
URL_HEADER = "| # | Policy / strategy | Official URL |\n| -- | -- | -- |\n"


def _md(master_rows, url_rows):
    return ("## **Master**\n\n" + HEADER + "".join(master_rows) + "\nprose here\n\n"
            "## URLs\n\n" + URL_HEADER + "".join(url_rows) + "\n[image](https://x.test/i.png)\n+7\n")


GOOD_MASTER = [
    "| **Alpha Plan (*Moving*)** | DoT | 2022–2030 | Scope A | NSMP, Project Ireland 20406 |\n",
    "| **Code of Practice for Boats (\\<15m)** | DoT | 2022 (Rev 3\\) | Scope B | Acts38 |\n",
]
GOOD_URLS = [
    "| 1 | Alpha | [Page](https://example.org/a) |\n",
    "| 2 | Boats | [One](https://example.org/b1), [Two](https://example.org/b2) |\n",
]


@pytest.fixture
def load(tmp_path, monkeypatch):
    """Load a fixture inventory. The real CODE_OF_PRACTICE_NUMBERS is {20, 21};
    these small fixtures put the code of practice at #2, so patch it."""
    def _load(master=GOOD_MASTER, urls=GOOD_URLS, codes=frozenset({2})):
        monkeypatch.setattr(policies, "CODE_OF_PRACTICE_NUMBERS", codes)
        path = tmp_path / "plans.md"
        path.write_text(_md(master, urls), encoding="utf-8")
        return load_policies(path)
    return _load


@pytest.mark.parametrize("raw,expected", [
    ("Common Appraisal Framework (CAF)1", "Common Appraisal Framework (CAF)"),
    ("Greenways Strategy27", "Greenways Strategy"),
    ("Climate Action Plan10", "Climate Action Plan"),
    ("Project Ireland 20406", "Project Ireland 2040"),       # year + footnote 6
    ("Project Ireland 204010", "Project Ireland 2040"),      # year + footnote 10
    ("Project Ireland 2040", "Project Ireland 2040"),        # no footnote: keep the year
    ("Act 2008, NSMP", "Act 2008, NSMP"),                    # no trailing digits
    ("Strategy 12", "Strategy 12"),                          # space-separated number is not a footnote
])
def test_strip_footnote(raw, expected):
    assert strip_footnote(raw) == expected


def test_strip_footnote_rejects_ambiguous_three_digit_run():
    with pytest.raises(ValueError, match="ambiguous"):
        strip_footnote("Strategy100")


def test_load_policies_cleans_markup_and_joins_urls(load):
    alpha, boats = load()
    assert alpha["title"] == "Alpha Plan (Moving)"            # bold + italics removed
    assert alpha["policy_id"] == "alpha-plan-moving"
    assert alpha["linkages"] == "NSMP, Project Ireland 2040"  # footnote 6 cut, year kept
    assert alpha["kind"] == "policy" and alpha["number"] == 1
    assert alpha["source_urls"] == ["https://example.org/a"]
    assert boats["title"] == "Code of Practice for Boats (<15m)"   # markdown escape removed
    assert boats["kind"] == "code-of-practice"
    assert boats["horizon"] == "2022 (Rev 3)"
    assert boats["linkages"] == "Acts"                        # glued footnote 38 cut
    assert boats["source_urls"] == ["https://example.org/b1", "https://example.org/b2"]


def test_a_row_with_the_wrong_number_of_cells_is_fatal(load):
    with pytest.raises(ValueError, match="expected 5"):
        load(master=GOOD_MASTER[:1] + ["| Only | four | cells | here |\n"])


def test_missing_url_row_is_fatal(load):
    with pytest.raises(ValueError, match="disagree"):
        load(urls=GOOD_URLS[:1])


def test_duplicate_policy_number_in_url_tables_is_fatal(load):
    with pytest.raises(ValueError, match="duplicate policy number"):
        load(urls=GOOD_URLS + ["| 2 | again | [x](https://example.org/x) |\n"])


def test_duplicate_policy_id_is_fatal(load):
    dup = [GOOD_MASTER[0], GOOD_MASTER[0].replace("Alpha Plan (*Moving*)", "Alpha Plan (Moving)")]
    with pytest.raises(ValueError, match="duplicate policy_id"):
        load(master=dup, codes=frozenset())


def test_a_code_of_practice_in_the_wrong_position_is_fatal(load):
    with pytest.raises(ValueError, match="CODE_OF_PRACTICE_NUMBERS"):
        load(master=[GOOD_MASTER[1], GOOD_MASTER[0]])


def test_a_row_without_a_closing_pipe_is_fatal(load):
    with pytest.raises(ValueError, match="malformed table row"):
        load(master=GOOD_MASTER[:1] + ["| broken | row\n"])


# ---- the real file -------------------------------------------------------

EXPECTED_IDS = [
    "national-investment-framework-for-transport-in-ireland-nifti",
    "national-sustainable-mobility-policy-nsmp",
    "ndp-sectoral-investment-plan-for-transport",
    "national-demand-management-strategy-moving-together",
    "all-island-strategic-rail-review-aisrr",
    "national-roads-2040-nr2040",
    "national-cycle-network-ncn-plan",
    "electric-vehicle-charging-infrastructure-strategy",
    "nta-statement-of-strategy",
    "tii-sustainability-implementation-plan-sip",
    "greater-dublin-area-transport-strategy",
    "busconnects-programme-strategies",
    "connecting-ireland-rural-mobility-plan",
    "cycleconnects-plan",
    "gda-cycle-network-plan",
    "regional-spatial-economic-strategies-rses",
    "local-transport-plans-ltp-frameworks",
    "national-ports-policy",
    "maritime-safety-strategy",
    "code-of-practice-for-small-fishing-vessels-15m",
    "code-of-practice-for-safe-operation-of-recreational-craft",
]


def test_the_real_inventory_has_the_21_permanent_policy_ids_in_order():
    policies = load_policies(POLICIES_PATH)
    assert [p["policy_id"] for p in policies] == EXPECTED_IDS     # permanent: never edit casually
    assert [p["number"] for p in policies] == list(range(1, 22))


def test_the_real_inventory_kinds_and_footnotes():
    by_n = {p["number"]: p for p in load_policies(POLICIES_PATH)}
    assert {n for n, p in by_n.items() if p["kind"] == "code-of-practice"} == {20, 21}
    assert by_n[3]["linkages"].endswith("Project Ireland 2040")    # row 3: year 2040 + footnote 6
    assert by_n[1]["linkages"].endswith("(CAF)")
    for p in by_n.values():
        # a trailing digit is only legitimate as the end of a 4-digit year
        assert not p["linkages"][-1].isdigit() or p["linkages"][-4:].isdigit(), p["linkages"]
        assert "*" not in p["title"] and "\\" not in p["title"]
        assert p["source_urls"], p["policy_id"]


def test_the_real_inventory_multi_url_and_directory_url_rows():
    by_n = {p["number"]: p for p in load_policies(POLICIES_PATH)}
    assert len(by_n[16]["source_urls"]) == 3                      # EMRA / Southern / NWRA
    assert by_n[17]["source_urls"] == ["https://www.localgov.ie/"]


# ---- multi-domain merge --------------------------------------------------

CLIMATE_MASTER = ["| **Climate Plan** | DCEE | 2023–2050 | Scope C | Act 2021 |\n"]
CLIMATE_URLS = ["| 1 | Climate | [Page](https://example.org/c) |\n"]
TRANSPORT_MASTER = GOOD_MASTER[:1]
TRANSPORT_URLS = GOOD_URLS[:1]


def _inventory_dir(tmp_path, **domains):
    for domain, (master, urls) in domains.items():
        (tmp_path / f"input_plans_{domain}.md").write_text(_md(master, urls), encoding="utf-8")
    return tmp_path


def test_merged_inventory_carries_each_policys_domain(tmp_path):
    d = _inventory_dir(tmp_path, transport=(TRANSPORT_MASTER, TRANSPORT_URLS),
                       climate=(CLIMATE_MASTER, CLIMATE_URLS))
    merged = load_policies(directory=d)
    by_id = {p["policy_id"]: p for p in merged}
    assert by_id["alpha-plan-moving"]["domain"] == "transport"
    assert by_id["climate-plan"]["domain"] == "climate"
    # `number` is file-scoped row order: both are #1 in their own file
    assert by_id["alpha-plan-moving"]["number"] == by_id["climate-plan"]["number"] == 1


def test_cross_domain_policy_id_collision_is_fatal_and_names_both_files(tmp_path):
    clash = ["| **Alpha Plan (Moving)** | DCEE | 2023 | Scope C | Act |\n"]
    d = _inventory_dir(tmp_path, transport=(TRANSPORT_MASTER, TRANSPORT_URLS),
                       climate=(clash, CLIMATE_URLS))
    with pytest.raises(ValueError) as exc:
        load_policies(directory=d)
    msg = str(exc.value)
    assert "duplicate policy_id 'alpha-plan-moving'" in msg
    assert "input_plans_climate.md" in msg and "input_plans_transport.md" in msg


def test_a_malformed_row_in_any_domain_file_is_fatal(tmp_path):
    d = _inventory_dir(tmp_path, transport=(TRANSPORT_MASTER, TRANSPORT_URLS),
                       climate=(["| only | two |\n"], CLIMATE_URLS))
    with pytest.raises(ValueError, match=r"input_plans_climate\.md:\d+"):
        load_policies(directory=d)


def test_transport_code_of_practice_rule_does_not_apply_to_other_domains(tmp_path, monkeypatch):
    monkeypatch.setattr(policies, "CODE_OF_PRACTICE_NUMBERS", frozenset({2}))
    d = _inventory_dir(tmp_path, transport=(GOOD_MASTER, GOOD_URLS),
                       climate=(CLIMATE_MASTER * 1, CLIMATE_URLS))
    merged = load_policies(directory=d)
    assert [p["kind"] for p in merged if p["domain"] == "climate"] == ["policy"]
    assert [p["kind"] for p in merged if p["domain"] == "transport"] == ["policy", "code-of-practice"]


def test_a_directory_with_no_inventory_files_is_fatal(tmp_path):
    with pytest.raises(ValueError, match="no input_plans_"):
        load_policies(directory=tmp_path)


def test_inventory_filename_must_name_a_domain(tmp_path):
    with pytest.raises(ValueError, match="input_plans_<domain>"):
        policies.domain_of(tmp_path / "plans.md")


def test_the_real_merged_inventory_keeps_transport_numbers_and_adds_climate():
    merged = load_policies()
    transport = [p for p in merged if p["domain"] == "transport"]
    assert [p["policy_id"] for p in transport] == EXPECTED_IDS
    assert [p["number"] for p in transport] == list(range(1, 22))
    climate = [p for p in merged if p["domain"] == "climate"]
    assert [p["policy_id"] for p in climate] == ["climate-action-plan"]    # permanent id
    assert climate[0]["number"] == 1
    assert climate[0]["kind"] == "policy" and climate[0]["source_urls"]
    assert len({p["policy_id"] for p in merged}) == len(merged)
