#!/usr/bin/env python3
"""Build the uncommitted forms of the FOI disclosures dataset from the
committed per-body NDJSON files.

Writes (under the repo root):
  public/foi-disclosures.json                       combined array, ordered by (public_body_id, row_id)
  public/latest/foi-disclosures/foi-disclosures.{csv,jsonld,xlsx}
  public/latest/foi-disclosures/bodies/manifest.json

Needs no network. Run it after editing per-body files by hand:
  python scripts/build_foi_combined.py
Never touches the catalog .ttl (dct:modified is stamped by export_status).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts import transform_foi_disclosures as tfd  # noqa: E402
from src.lib import foi_dataset  # noqa: E402


def _commit(root):
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True)
        return out.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def build(root, build_id=None, commit=None):
    """Build all derived forms under `root`. Returns {"total_rows", "total_bodies", "manifest"}."""
    root = Path(root)
    bodies_dir = root / tfd.BODIES_DIR
    problems = foi_dataset.verify_parts(bodies_dir)
    if problems:
        raise ValueError("per-body files failed verification:\n  " + "\n  ".join(problems[:20]))

    rows = foi_dataset.load_parts(bodies_dir)
    pipeline_bodies = json.loads((root / tfd.PIPELINE_DATA_PATH).read_text())["public_bodies"]
    slug_seed = tfd.load_slug_seed(str(root / tfd.SLUG_SEED_PATH))
    jsonld_data, fieldnames, csv_rows = tfd.build_forms(rows, pipeline_bodies, slug_seed)

    counts = {"rows": len(rows), "jsonld": len(jsonld_data["@graph"]), "csv": len(csv_rows)}
    if len(set(counts.values())) != 1:
        raise ValueError(f"row counts disagree: {counts}")

    (root / "public").mkdir(parents=True, exist_ok=True)
    (root / "public" / "foi-disclosures.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tfd.publish(
        jsonld_data, fieldnames, csv_rows,
        jsonld_path=root / tfd.JSONLD_OUTPUT_PATH,
        csv_path=root / tfd.CSV_OUTPUT_PATH,
        xlsx_path=root / tfd.XLSX_OUTPUT_PATH,
    )

    manifest = foi_dataset.build_manifest(
        bodies_dir, schema_version=tfd.DATASET_VERSION, build=build_id,
        commit=commit if commit is not None else _commit(root))
    if manifest["total_rows"] != len(rows):
        raise ValueError("manifest total disagrees with loaded rows")
    (bodies_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"total_rows": len(rows), "total_bodies": manifest["total_bodies"], "manifest": manifest}


def main(argv=None):
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--root", default=str(REPO), help="repo root (default: this checkout)")
    ap.add_argument("--build", default=None, help="release build id to record in the manifest")
    args = ap.parse_args(argv)
    summary = build(Path(args.root), build_id=args.build)
    print(f"Built {summary['total_rows']} rows from {summary['total_bodies']} bodies")


if __name__ == "__main__":
    main()
