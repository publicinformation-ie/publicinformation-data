"""Unit tests for scripts/migrate_foi_ids_to_cso.py.

These tests exercise the pure, file-I/O-free core (fold, crosswalk-build,
resolve-name->id, remap-one-record) with in-memory dicts. They never touch or
mutate the real pipeline output.json files.
"""

import sys
from pathlib import Path

import pytest

# Bootstrap sys.path: src/ for lib.file_utils, scripts/ for the migration module.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import migrate_foi_ids_to_cso as mig  # noqa: E402


# A small in-memory canonical body table covering every alias target plus a
# couple of already-canonical bodies. Mirrors find_public_bodies/output.json's
# per-record shape (name + public_body_id).
CANONICAL_BODIES = [
    {"public_body_id": 1679, "name": "Rásaíocht Con Éireann"},
    {"public_body_id": 1052, "name": "Bord Bia"},
    {"public_body_id": 1298, "name": "Fiosrú Oifig an Ombudsman Poilíneachta"},
    {"public_body_id": 1156, "name": "Competition and Consumer Protection Commission"},
    {"public_body_id": 1782, "name": "The Data Protection Commission (DPC)"},
    {"public_body_id": 1197, "name": "Department of Children, Disability and Equality"},
    {"public_body_id": 1018, "name": "Department of Transport"},
]


@pytest.fixture
def crosswalk():
    return mig.build_crosswalk(CANONICAL_BODIES)


# --------------------------------------------------------------------------- #
# fold()
# --------------------------------------------------------------------------- #

class TestFold:
    def test_strips_accents(self):
        assert mig.fold("Rásaíocht Con Éireann") == "rasaiocht con eireann"

    def test_lowercases(self):
        assert mig.fold("Bord Bia") == "bord bia"

    def test_punctuation_to_space_and_collapse(self):
        assert mig.fold("Bord Bia (Irish Food Board)") == "bord bia irish food board"

    def test_collapses_repeated_separators(self):
        assert mig.fold("Fiosrú - the  Office") == "fiosru the office"

    def test_strips_leading_trailing(self):
        assert mig.fold("  Department of Transport  ") == "department of transport"

    def test_none_is_empty(self):
        assert mig.fold(None) == ""


# --------------------------------------------------------------------------- #
# build_crosswalk() + alias resolution
# --------------------------------------------------------------------------- #

class TestCrosswalk:
    def test_direct_names_resolve(self, crosswalk):
        name_to_id, _ = crosswalk
        assert name_to_id[mig.fold("Department of Transport")] == 1018
        assert name_to_id[mig.fold("Bord Bia")] == 1052

    def test_id_to_name_populated(self, crosswalk):
        _, id_to_name = crosswalk
        assert id_to_name[1018] == "Department of Transport"

    @pytest.mark.parametrize(
        "stale_name,expected_id",
        [
            ("Greyhound Racing Ireland (GRI)", 1679),
            ("Bord Bia (Irish Food Board)", 1052),
            ("Fiosrú - the Office of the Police Ombudsman", 1298),
            ("Competition and Consumer Protection Commission (CCPC)", 1156),
            ("Data Protection Commission", 1782),
        ],
    )
    def test_all_five_aliases_resolve(self, crosswalk, stale_name, expected_id):
        name_to_id, _ = crosswalk
        assert mig.resolve_name(stale_name, name_to_id) == expected_id

    def test_unresolvable_name_raises(self, crosswalk):
        name_to_id, _ = crosswalk
        with pytest.raises(mig.MigrationError):
            mig.resolve_name("Totally Unknown Body", name_to_id)

    def test_missing_alias_target_aborts_loudly(self):
        # Canonical table missing the Greyhound target -> build must abort.
        bodies = [b for b in CANONICAL_BODIES if b["public_body_id"] != 1679]
        with pytest.raises(mig.MigrationError):
            mig.build_crosswalk(bodies)


# --------------------------------------------------------------------------- #
# remap_record() idempotence
# --------------------------------------------------------------------------- #

class TestRemap:
    def test_stale_record_is_rewritten(self, crosswalk):
        name_to_id, id_to_name = crosswalk
        # Stale collision: old id 1002 + a stale-named Bord Bia record.
        rec = {"public_body_id": 1023, "name": "Bord Bia (Irish Food Board)", "x": 1}
        changed = mig.remap_record(rec, name_to_id, id_to_name)
        assert changed is True
        assert rec["public_body_id"] == 1052
        assert rec["name"] == "Bord Bia"
        assert rec["x"] == 1  # other fields untouched

    def test_already_canonical_is_noop(self, crosswalk):
        name_to_id, id_to_name = crosswalk
        rec = {"public_body_id": 1018, "name": "Department of Transport"}
        changed = mig.remap_record(rec, name_to_id, id_to_name)
        assert changed is False
        assert rec == {"public_body_id": 1018, "name": "Department of Transport"}

    def test_remap_twice_equals_once(self, crosswalk):
        name_to_id, id_to_name = crosswalk
        rec = {"public_body_id": 1023, "name": "Bord Bia (Irish Food Board)"}
        mig.remap_record(rec, name_to_id, id_to_name)
        after_once = dict(rec)
        changed_second = mig.remap_record(rec, name_to_id, id_to_name)
        assert changed_second is False
        assert rec == after_once

    def test_record_without_pb_and_name_untouched(self, crosswalk):
        name_to_id, id_to_name = crosswalk
        rec = {"file_url": "http://x", "rows": []}
        assert mig.remap_record(rec, name_to_id, id_to_name) is False
        assert rec == {"file_url": "http://x", "rows": []}

    def test_remap_records_counts_changes(self, crosswalk):
        name_to_id, id_to_name = crosswalk
        records = [
            {"public_body_id": 1018, "name": "Department of Transport"},      # canonical
            {"public_body_id": 9, "name": "Bord Bia (Irish Food Board)"},     # stale
            {"file_url": "http://x"},                                          # skip
        ]
        assert mig.remap_records(records, name_to_id, id_to_name) == 1


# --------------------------------------------------------------------------- #
# dedup helpers
# --------------------------------------------------------------------------- #

class TestDedup:
    def test_pages_one_per_body_prefers_overridden(self):
        records = [
            {"public_body_id": 1, "confidence": "high", "overridden": False},
            {"public_body_id": 1, "confidence": "none", "overridden": True},
            {"public_body_id": 2, "confidence": "high"},
        ]
        out = mig.dedup_disclosure_pages(records)
        assert len(out) == 2
        body1 = next(r for r in out if r["public_body_id"] == 1)
        assert body1["overridden"] is True

    def test_pages_prefers_highest_categorical_confidence(self):
        # Real find_disclosure_pages confidence is categorical: high>medium>low>none.
        records = [
            {"public_body_id": 1, "confidence": "low"},
            {"public_body_id": 1, "confidence": "high"},
            {"public_body_id": 1, "confidence": None},
        ]
        out = mig.dedup_disclosure_pages(records)
        assert len(out) == 1
        assert out[0]["confidence"] == "high"

    def test_files_unique_by_tuple(self):
        records = [
            {"public_body_id": 1, "file_url": "a", "disclosure_page_url": "p"},
            {"public_body_id": 1, "file_url": "a", "disclosure_page_url": "p"},  # dup
            {"public_body_id": 1, "file_url": "b", "disclosure_page_url": "p"},
            {"public_body_id": 2, "file_url": "a", "disclosure_page_url": "p"},
        ]
        out = mig.dedup_disclosure_files(records)
        assert len(out) == 3

    def test_dedup_idempotent(self):
        records = [
            {"public_body_id": 1, "file_url": "a", "disclosure_page_url": "p"},
            {"public_body_id": 1, "file_url": "a", "disclosure_page_url": "p"},
        ]
        once = mig.dedup_disclosure_files(records)
        twice = mig.dedup_disclosure_files(once)
        assert once == twice
        assert len(twice) == 1
