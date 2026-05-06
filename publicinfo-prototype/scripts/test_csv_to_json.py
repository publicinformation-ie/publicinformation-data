import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from csv_to_json import convert_csv_to_json

SAMPLE_CSV = (
    "public_body_id,public_body_name,public_body_short_name,"
    "public_body_url,public_body_category,last_checked,last_modified\n"
    "1001,\"Department of Agriculture, Food and the Marine\",DAFM,"
    "https://www.gov.ie/en/organisation/dafm/,government department,2026-04-27,2026-04-27\n"
    "1002,Department of Finance,DOF,"
    "https://www.gov.ie/en/organisation/dof/,government department,2026-04-27,2026-04-27\n"
)


def test_converts_csv_to_json(tmp_path):
    out = tmp_path / "public_bodies.json"
    with patch("csv_to_json.requests.get") as mock_get, \
         patch("csv_to_json.OUTPUT_PATH", str(out)):
        mock_get.return_value.text = SAMPLE_CSV
        mock_get.return_value.raise_for_status = MagicMock()
        convert_csv_to_json()

    data = json.loads(out.read_text())
    assert len(data) == 2
    assert data[0]["public_body_id"] == 1001
    assert data[0]["public_body_name"] == "Department of Agriculture, Food and the Marine"
    assert data[0]["public_body_url"] == "https://www.gov.ie/en/organisation/dafm/"


def test_writes_empty_list_on_network_error(tmp_path):
    out = tmp_path / "public_bodies.json"
    with patch("csv_to_json.requests.get") as mock_get, \
         patch("csv_to_json.OUTPUT_PATH", str(out)):
        mock_get.side_effect = Exception("network error")
        convert_csv_to_json()

    data = json.loads(out.read_text())
    assert data == []


def test_writes_empty_list_on_missing_columns(tmp_path):
    out = tmp_path / "public_bodies.json"
    with patch("csv_to_json.requests.get") as mock_get, \
         patch("csv_to_json.OUTPUT_PATH", str(out)):
        mock_get.return_value.text = "wrong,columns\nfoo,bar\n"
        mock_get.return_value.raise_for_status = MagicMock()
        convert_csv_to_json()

    data = json.loads(out.read_text())
    assert data == []
