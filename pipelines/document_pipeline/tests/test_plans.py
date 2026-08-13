import pytest

from plans import load_plans

VALID = """\
# Current and Future Plans for all government departments in Ireland

## 1. Department of Example

| Plan / Strategy Title | Time Horizon | Key Focus / Scope | Status |
| --- | --- | --- | --- |
| **Statement of Strategy** | **2025–2028** | Core departmental goals. | **Active** |
| **Second Plan** | **2024–2030** | Another focus area. | **Draft** |

---

## 2. Department of Another Example

| Plan / Strategy Title | Time Horizon | Key Focus / Scope | Status |
| --- | --- | --- | --- |
| **Only Plan** | **2023–2025** | Sole focus. | **Active** |
"""


def _write(tmp_path, text):
    path = tmp_path / "input_plans.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_plans_returns_one_record_per_table_row(tmp_path):
    records = load_plans(_write(tmp_path, VALID))
    assert records == [
        {"department": "Department of Example", "title": "Statement of Strategy",
         "time_horizon": "2025–2028", "focus": "Core departmental goals.", "status": "Active"},
        {"department": "Department of Example", "title": "Second Plan",
         "time_horizon": "2024–2030", "focus": "Another focus area.", "status": "Draft"},
        {"department": "Department of Another Example", "title": "Only Plan",
         "time_horizon": "2023–2025", "focus": "Sole focus.", "status": "Active"},
    ]


def test_load_plans_returns_empty_list_for_a_file_with_no_departments(tmp_path):
    text = "# Current and Future Plans for all government departments in Ireland\n"
    assert load_plans(_write(tmp_path, text)) == []


def test_load_plans_rejects_a_heading_not_matching_n_dot_department(tmp_path):
    text = (
        "## Not Numbered Department\n\n"
        "| Plan / Strategy Title | Time Horizon | Key Focus / Scope | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| **A Plan** | **2025** | Focus. | **Active** |\n"
    )
    with pytest.raises(ValueError, match="heading"):
        load_plans(_write(tmp_path, text))


def test_load_plans_rejects_a_table_row_before_any_heading(tmp_path):
    text = "| A Plan | 2025 | Focus | Active |\n"
    with pytest.raises(ValueError, match="before any department heading"):
        load_plans(_write(tmp_path, text))


def test_load_plans_rejects_a_heading_with_no_table(tmp_path):
    text = (
        "## 1. Department A\n\n"
        "## 2. Department B\n\n"
        "| Plan / Strategy Title | Time Horizon | Key Focus / Scope | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| **A Plan** | **2025** | Focus. | **Active** |\n"
    )
    with pytest.raises(ValueError, match="no table"):
        load_plans(_write(tmp_path, text))


def test_load_plans_rejects_a_heading_with_no_table_at_end_of_file(tmp_path):
    text = "## 1. Department A\n"
    with pytest.raises(ValueError, match="no table"):
        load_plans(_write(tmp_path, text))


def test_load_plans_rejects_a_table_row_with_the_wrong_cell_count(tmp_path):
    text = (
        "## 1. Department A\n\n"
        "| Plan / Strategy Title | Time Horizon | Status |\n"
        "| --- | --- | --- |\n"
    )
    with pytest.raises(ValueError, match="4 cell"):
        load_plans(_write(tmp_path, text))
