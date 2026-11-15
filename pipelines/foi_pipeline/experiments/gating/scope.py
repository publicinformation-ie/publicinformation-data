"""Per-file stats, scope set and fault proposal for the gating harness."""
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from experiments.gating.paths import BAKEOFF, STEPS, load_results

if str(BAKEOFF) not in sys.path:
    sys.path.insert(0, str(BAKEOFF))
from cause_ledger import classify_error  # noqa: E402

TRANSFORM = "transform_disclosure_files"
ASSESS = "assess_table_structure"
CANON = "extract_disclosures_canonicalize_rows"
ERROR_RATE_MIN = 0.2


@dataclass
class FileStat:
    file_url: str
    public_body_id: int | None
    name: str
    file_type: str | None
    pdf_extractor: str | None
    gated: bool
    failed_checks: list[str] = field(default_factory=list)
    worst_role: str | None = None
    worst_role_contamination: float | None = None
    anchored_row_share: float | None = None
    records: int = 0
    errors: int = 0
    error_classes: dict[str, int] = field(default_factory=dict)
    n_candidates_with_table: int = 0


def _has_table(score) -> bool:
    return isinstance(score, dict) and "error" not in score


def file_stats(steps_dir: Path = STEPS) -> dict[str, FileStat]:
    steps_dir = Path(steps_dir)
    assess = {}
    for r in load_results(steps_dir / ASSESS / "output.json"):
        assess.setdefault(r["file_url"], r)
    failed = {}
    for e in load_results(steps_dir / ASSESS / "errors.json"):
        c = e.get("context", {})
        failed.setdefault(c.get("file_url"), list(c.get("failed_checks") or []))
    records = Counter(r["file_url"] for r in load_results(steps_dir / CANON / "output.json"))
    errors, classes = Counter(), {}
    for e in load_results(steps_dir / CANON / "errors.json"):
        u = e["context"]["file_url"]
        errors[u] += 1
        classes.setdefault(u, Counter())[classify_error(e)] += 1
    out: dict[str, FileStat] = {}
    for it in load_results(steps_dir / TRANSFORM / "output.json"):
        url = it["file_url"]
        if url in out:
            continue
        a = assess.get(url, {})
        ts = a.get("table_structure") or {}
        scores = (it.get("pdf_table_selection") or {}).get("scores") or {}
        gated = bool(a.get("table_structure_unreliable"))
        out[url] = FileStat(
            file_url=url, public_body_id=it.get("public_body_id"),
            name=it.get("name") or url.rstrip("/").rsplit("/", 1)[-1],
            file_type=it.get("file_type"), pdf_extractor=it.get("pdf_extractor"),
            gated=gated, failed_checks=failed.get(url, []) if gated else [],
            worst_role=ts.get("worst_role"), worst_role_contamination=ts.get("worst_role_contamination"),
            anchored_row_share=ts.get("anchored_row_share"),
            records=records[url], errors=errors[url], error_classes=dict(classes.get(url, {})),
            n_candidates_with_table=sum(1 for s in scores.values() if _has_table(s)))
    return out


def error_rate(s: FileStat) -> float:
    n = s.records + s.errors
    return s.errors / n if n else 0.0


def scope_set(stats: dict[str, FileStat]) -> list[str]:
    return sorted(u for u, s in stats.items() if s.gated or error_rate(s) >= ERROR_RATE_MIN)


def override_urls(steps_dir: Path = STEPS) -> set[str]:
    steps_dir = Path(steps_dir)
    urls = set()
    cm = steps_dir / "extract_disclosures_canonicalize" / "column_mappings.json"
    if cm.is_file():
        urls |= {u for u, v in json.loads(cm.read_text() or "{}").items()
                 if isinstance(v, dict) and "column_mapping" in v}
    ov = steps_dir / "extract_disclosures_normalize_header" / "override.json"
    urls |= {r["file_url"] for r in load_results(ov) if "file_url" in r}
    return urls


def propose_fault(now: FileStat, before: FileStat | None, has_override: bool) -> tuple[str, str]:
    if "min_rows" in now.failed_checks:
        return "S", "min_rows failed: too few rows extracted"
    if now.gated and before is not None and before.records + before.errors == 0:
        return "S", "gated; no rows at all before role-aware gate"
    if has_override:
        return "M", "has a column_mapping or header override"
    if not now.gated:
        cls = now.error_classes
        ranked = Counter(cls).most_common(2)
        top = ranked[0][0] if ranked and not (len(ranked) > 1 and ranked[0][1] == ranked[1][1]) else None
        total = sum(cls.values())
        if total and (cls.get("unknown_value", 0) + cls.get("text_variant", 0)) / total >= 0.8:
            return "V", f"vocabulary errors {dict(cls)}"
        if top == "header_mapping":
            return "M", f"header_mapping errors {dict(cls)}"
        return "E", f"error classes {dict(cls)}"
    if (set(now.failed_checks) <= {"role_contamination", "anchored_row_share"} and before is not None
            and before.records >= 20 and error_rate(before) <= 0.05):
        return "G", f"gate-only failure; {before.records} records before at {error_rate(before):.1%} errors"
    return "E", f"gated on {'+'.join(now.failed_checks) or 'unknown'}"


def default_cluster(now: FileStat, kind: str) -> str:
    return f"{now.public_body_id}-{kind}-{'+'.join(sorted(now.failed_checks)) or 'errors'}"


def recoverable(now: FileStat, before: FileStat | None) -> int:
    if now.gated:
        return before.records if before else 0
    return now.errors
