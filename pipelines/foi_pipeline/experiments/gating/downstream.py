"""Real downstream chain on in-memory items, plus the reproduction check.

A fix's rows are fed, as transform_disclosure_files-shaped items, through the
real step functions in pipeline.json order (assess gate, then
normalize_disclosure_cells .. extract_disclosures_canonicalize_rows). Every
step gets its own scratch step_dir under `scratch/<variant>/`; the config files
a step reads from its step_dir are copied there from the real step directory,
so nothing under steps/ is ever written.

Unlike assess_table_structure, a failed gate does not empty the rows: records
and errors are what the file would publish if it passed.

CLI: uv run python -m experiments.gating.downstream --urls-file F [--steps-dir D]
"""
import argparse
import contextlib
import io
import json
import shutil
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from experiments.gating.paths import SCRATCH, STEPS, load_results
from experiments.gating.scope import file_stats  # also puts BAKEOFF on sys.path

from cause_ledger import classify_error  # noqa: E402  # pyright: ignore[reportMissingImports]

from lib.file_utils import IncrementalWriter, write_json  # noqa: E402
from lib.table_structure import DEFAULT_THRESHOLDS, StructureScore, failed_checks, score_table  # noqa: E402
from steps.assess_table_structure.process import _load_override_role_maps  # noqa: E402
import steps.normalize_disclosure_cells.process as _cells_mod  # noqa: E402
from steps.filter_phantom_rows.process import process as filter_phantom  # noqa: E402
from steps.extract_disclosures_detect_header_row.process import process as detect_header  # noqa: E402
from steps.extract_disclosures_normalize_header.process import process as normalize_header  # noqa: E402
from steps.extract_disclosures_split_combined_columns.process import split_file  # noqa: E402
from steps.extract_disclosures_normalize_rows.process import process as normalize_rows  # noqa: E402
from steps.extract_disclosures_canonicalize.process import (  # noqa: E402
    _load_column_mappings, load_column_swaps, process as canonicalize)
from steps.extract_disclosures_canonicalize_rows.process import process_records  # noqa: E402

Gate = Callable[[list[list], dict[int, str] | None], tuple[StructureScore, list[str]]]

TRANSFORM = "transform_disclosure_files"
ASSESS = "assess_table_structure"
CANON = "extract_disclosures_canonicalize"
CANON_ROWS = "extract_disclosures_canonicalize_rows"
# Writer-based steps, in pipeline.json order. Each main() builds its
# IncrementalWriter with override_path=step_dir/"override.json" (the writer
# also reads output_schema.json beside it to validate override records).
WRITER_STEPS = ["normalize_disclosure_cells", "filter_phantom_rows",
                "extract_disclosures_detect_header_row", "extract_disclosures_normalize_header",
                "extract_disclosures_split_combined_columns", "extract_disclosures_normalize_rows"]
WRITER_CONFIG = ["override.json", "output_schema.json"]
CANON_CONFIG = ["column_swaps.json", "column_mappings.json"]


def default_gate(rows: list[list], role_map: dict[int, str] | None) -> tuple[StructureScore, list[str]]:
    score = score_table(rows, role_map=role_map)
    return score, failed_checks(score, DEFAULT_THRESHOLDS)


@dataclass
class FileOutcome:
    file_url: str
    gate_pass: bool
    failed_checks: list[str] = field(default_factory=list)
    score: dict = field(default_factory=dict)
    records: int = 0
    errors: int = 0
    error_classes: dict[str, int] = field(default_factory=dict)
    override_bound: bool = False


def transform_index(steps_dir: Path = STEPS) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for it in load_results(Path(steps_dir) / TRANSFORM / "output.json"):
        out.setdefault(it["file_url"], it)
    return out


def item_for(stored: dict, rows: list[list], fix_name: str) -> dict:
    return {**json.loads(json.dumps(stored)), "rows": rows, "pdf_extractor": fix_name}


def _bound_urls(config_dir: Path) -> set[str]:
    """URLs whose downstream output is pinned to the stored grid: an index-keyed
    column_mapping in column_mappings.json, or an override.json record (which
    replaces the step's output for that URL wholesale)."""
    urls = set()
    cm = config_dir / CANON / "column_mappings.json"
    if cm.is_file():
        for url, entry in json.loads(cm.read_text() or "{}").items():
            mapping = entry.get("column_mapping") if isinstance(entry, dict) else None
            if mapping and all(str(k).isdigit() for k in mapping):
                urls.add(url)
    for step in WRITER_STEPS:
        for r in load_results(config_dir / step / "override.json"):
            if isinstance(r, dict) and r.get("file_url"):
                urls.add(r["file_url"])
    return urls


def _copy_config(config_dir: Path, step: str, names: list[str], step_dir: Path):
    for name in names:
        src = config_dir / step / name
        if src.is_file():
            shutil.copyfile(src, step_dir / name)


def _gate_items(items: list[dict], gate: Gate, config_dir: Path):
    role_maps = _load_override_role_maps(config_dir / ASSESS)
    gated, verdicts = [], {}
    for it in items:
        url, rows = it["file_url"], it.get("rows")
        if rows is None or rows == []:  # assess passes these through unscored
            verdicts[url] = (True, [], {})
            gated.append(it)
            continue
        score, failed = gate(rows, role_maps.get(url))
        if it.get("file_type") != "pdf":
            failed = []
        verdicts[url] = (not failed, list(failed), asdict(score))
        gated.append({**it, "table_structure": asdict(score)})
    return gated, verdicts


class _BatchWriter(IncrementalWriter):
    """IncrementalWriter that persists only at finalize(). The real append()
    rewrites the whole output.json after every item, which is there for resume
    after a crash and makes a large batch quadratic; a scratch run never resumes."""

    def append(self, items: list):
        self.results.extend(items)
        for item in items:
            if self.key_field in item:
                self.processed_keys.add(item[self.key_field])


def _normalize_cells(inp: dict, step_dir: Path, writer: IncrementalWriter) -> None:
    """normalize_disclosure_cells.process rewrites the whole changes.json after
    every item (quadratic on a large batch). changes.json is a log nothing
    downstream reads, so defer it: keep only the last write, flush it once."""
    pending: dict = {}

    def deferred(path, data):
        if Path(path).name == "changes.json":
            pending["changes"] = (path, data)
        else:
            write_json(path, data)

    real = _cells_mod.write_json
    _cells_mod.write_json = deferred
    try:
        _cells_mod.process(inp, step_dir, writer, force=False, verbose=False)
    finally:
        _cells_mod.write_json = real
    if "changes" in pending:
        write_json(*pending["changes"])


def _run_writer_step(step: str, step_dir: Path, data: list[dict]) -> None:
    ov = step_dir / "override.json"
    writer = _BatchWriter(step_dir / "output.json", step, key_field="file_url", override_path=ov)
    inp = {"results": data}
    if step == "normalize_disclosure_cells":
        _normalize_cells(inp, step_dir, writer)
    elif step == "filter_phantom_rows":
        filter_phantom(inp, writer, verbose=False)
    elif step == "extract_disclosures_detect_header_row":
        detect_header(inp, step_dir, writer, verbose=False)
    elif step == "extract_disclosures_normalize_header":
        normalize_header(inp, step_dir, writer, verbose=False)
    elif step == "extract_disclosures_split_combined_columns":  # mirrors its main() loop
        for item in data:
            if writer.is_processed(item.get("file_url")):
                continue
            updated, _ = split_file(item)
            writer.append([updated])
    elif step == "extract_disclosures_normalize_rows":
        normalize_rows(inp, step_dir, writer, verbose=False)
    else:
        raise ValueError(step)
    writer.finalize()


def run_downstream(items: list[dict], variant: str, scratch: Path = SCRATCH, gate: Gate = default_gate,
                   config_dir: Path = STEPS) -> dict[str, FileOutcome]:
    urls = [it["file_url"] for it in items]
    dupes = sorted(u for u, n in Counter(urls).items() if n > 1)
    if dupes:
        raise ValueError(f"file_url appears more than once in the batch: {dupes}")
    config_dir, root = Path(config_dir), Path(scratch) / variant
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    wanted = set(urls)

    data = json.loads(json.dumps(items))  # pipeline steps only ever see JSON-shaped data
    data, verdicts = _gate_items(data, gate, config_dir)

    with contextlib.redirect_stdout(io.StringIO()):
        for i, step in enumerate(WRITER_STEPS, start=1):
            step_dir = root / f"{i:02d}_{step}"
            step_dir.mkdir()
            _copy_config(config_dir, step, WRITER_CONFIG, step_dir)
            _run_writer_step(step, step_dir, data)
            # override.json may carry records for URLs outside this batch
            data = [r for r in load_results(step_dir / "output.json") if r.get("file_url") in wanted]

        step_dir = root / f"{len(WRITER_STEPS) + 1:02d}_{CANON}"
        step_dir.mkdir()
        _copy_config(config_dir, CANON, CANON_CONFIG, step_dir)
        canon_results, canon_errors = [], []
        canonicalize({"results": data}, canon_results, canon_errors,
                     column_swaps=load_column_swaps(step_dir),
                     column_mappings=_load_column_mappings(step_dir), verbose=False)
        write_json(step_dir / "output.json", {"metadata": {"step": CANON}, "results": canon_results})
        write_json(step_dir / "errors.json", canon_errors)

        step_dir = root / f"{len(WRITER_STEPS) + 2:02d}_{CANON_ROWS}"
        step_dir.mkdir()
        rows_results, rows_errors = [], []
        process_records({"results": load_results(root / f"{len(WRITER_STEPS) + 1:02d}_{CANON}" / "output.json")},
                        rows_results, rows_errors, verbose=False)
        write_json(step_dir / "output.json", {"metadata": {"step": CANON_ROWS}, "results": rows_results})
        write_json(step_dir / "errors.json", rows_errors)

    records = Counter(r.get("file_url") for r in rows_results)
    errors, classes = Counter(), {}
    for e in rows_errors:
        u = e["context"]["file_url"]
        errors[u] += 1
        classes.setdefault(u, Counter())[classify_error(e)] += 1

    bound = _bound_urls(config_dir) & wanted
    stored = transform_index(config_dir) if bound else {}
    out = {}
    for it in items:
        u = it["file_url"]
        ok, failed, score = verdicts[u]
        out[u] = FileOutcome(
            file_url=u, gate_pass=ok, failed_checks=failed, score=score,
            records=records[u], errors=errors[u], error_classes=dict(classes.get(u, {})),
            override_bound=u in bound and it.get("pdf_extractor") != stored.get(u, {}).get("pdf_extractor"))
    return out


def reproduce(file_urls: list[str], steps_dir: Path = STEPS, scratch: Path = SCRATCH,
              variant: str = "reproduce", config_dir: Path | None = None) -> list[dict]:
    """Feed each stored transform item unchanged; one dict per mismatch."""
    steps_dir = Path(steps_dir)
    index, stats = transform_index(steps_dir), file_stats(steps_dir)
    mismatches = [{"file_url": u, "field": "transform_item", "expected": "present", "got": None}
                  for u in file_urls if u not in index]
    present = [u for u in dict.fromkeys(file_urls) if u in index]
    outcomes = run_downstream([index[u] for u in present], variant, scratch=scratch,
                              config_dir=config_dir or steps_dir)
    for u in present:
        s, o = stats[u], outcomes[u]
        if o.gate_pass != (not s.gated):
            mismatches.append({"file_url": u, "field": "gate_pass", "expected": not s.gated, "got": o.gate_pass})
        if not s.gated:
            for f in ("records", "errors"):
                if getattr(o, f) != getattr(s, f):
                    mismatches.append({"file_url": u, "field": f, "expected": getattr(s, f), "got": getattr(o, f)})
    return mismatches


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Reproduce stored downstream counts for transform items")
    ap.add_argument("--urls-file", required=True, type=Path)
    ap.add_argument("--steps-dir", type=Path, default=STEPS,
                    help="stored outputs to reproduce (and the config read from them)")
    ap.add_argument("--config-dir", type=Path, default=None,
                    help="config source if different from --steps-dir")
    ap.add_argument("--variant", default="reproduce")
    args = ap.parse_args(argv)
    urls = [ln.strip() for ln in args.urls_file.read_text().splitlines() if ln.strip()]
    mism = reproduce(urls, steps_dir=args.steps_dir, variant=args.variant, config_dir=args.config_dir)
    for m in mism:
        print(json.dumps(m))
    print(f"{len(urls)} urls, {len(mism)} mismatches")
    return 1 if mism else 0


if __name__ == "__main__":
    sys.exit(main())
