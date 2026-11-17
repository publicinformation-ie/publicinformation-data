"""Gating ledger: one entry per scope file, generated plus manual state overrides.

Run from pipelines/foi_pipeline: uv run python -m experiments.gating.ledger
"""
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from experiments.gating.paths import GATING, PDF_CACHE, SNAPSHOT, STEPS, content_sha, pdf_bytes
from experiments.gating.scope import (default_cluster, error_rate, file_stats, override_urls,
                                      propose_fault, recoverable, scope_set)

STATUSES = ("open", "in_round", "resolved", "parked", "no_bytes")
KINDS = ("E", "M", "G", "S", "V")
TRIAGE_CLASSES = ("not_foi_log", "scan", "hard_table", "small_log")
STATE_FIELDS = ("fault_kind", "fault_firm", "cluster", "status", "note", "triage_class")
STATE_PATH = GATING / "ledger_state.json"


@dataclass
class LedgerEntry:
    file_url: str
    public_body_id: int | None
    name: str
    sha256: str | None
    pdf_extractor: str | None
    worst_role_contamination: float | None
    anchored_row_share: float | None
    failed_checks: list[str]
    records_before: int
    errors_before: int
    records_now: int
    errors_now: int
    fault_kind: str
    fault_firm: bool
    cluster: str
    status: str
    recoverable: int
    evidence: str
    triage_class: str | None = None
    est_rows: int | None = None  # ESTIMATE from the PDF text layer; only filled where recoverable is 0


def _load_state(path: Path) -> dict:
    p = Path(path)
    return json.loads(p.read_text() or "{}") if p.is_file() else {}


def estimate_rows(data: bytes | None) -> int | None:
    """Cheap ESTIMATE of record rows: text-layer lines that start with a date or a reference.

    Not an extraction: scans and wrapped layouts will be off. None if there are no bytes or the PDF is unreadable.
    """
    if data is None:
        return None
    import pymupdf
    from lib.value_kinds import _is_date, _is_reference
    n = 0
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                for line in str(page.get_text()).splitlines():
                    line = line.strip()
                    tok = line.split(None, 1)[0] if line else ""
                    if tok and (_is_date(line) or _is_reference(tok)):
                        n += 1
    except Exception:
        return None
    return n


def build_ledger(steps_dir: Path = STEPS, snapshot_dir: Path = SNAPSHOT,
                 state_path: Path = STATE_PATH, cache_dir: Path = PDF_CACHE) -> list[LedgerEntry]:
    now = file_stats(steps_dir)
    before = file_stats(snapshot_dir) if Path(snapshot_dir).is_dir() else {}
    overrides = override_urls(steps_dir)
    state = _load_state(state_path)
    entries = []
    for url in scope_set(now):
        n, b = now[url], before.get(url)
        kind, evidence = propose_fault(n, b, url in overrides)
        status, note = "open", None
        if kind == "V":
            status, note = "parked", "vocabulary, non-goal"
        firm = False
        st = state.get(url, {})
        proposed = kind
        kind = st.get("fault_kind", kind)
        # Kind S is retired: a file proposed as S takes its cluster from the triaged kind (E or G).
        cluster = default_cluster(n, kind if proposed == "S" else proposed)
        firm = st.get("fault_firm", firm)
        cluster = st.get("cluster", cluster)
        status = st.get("status", status)
        notes = [x for x in (note if "status" not in st and "fault_kind" not in st else None, st.get("note")) if x]
        if notes:
            evidence = f"{evidence}; " + "; ".join(notes)
        data = pdf_bytes(url, cache_dir)
        if data is None:
            status = "no_bytes"
        rec = recoverable(n, b)
        entries.append(LedgerEntry(
            file_url=url, public_body_id=n.public_body_id, name=n.name,
            sha256=content_sha(data) if data is not None else None, pdf_extractor=n.pdf_extractor,
            worst_role_contamination=n.worst_role_contamination, anchored_row_share=n.anchored_row_share,
            failed_checks=n.failed_checks,
            records_before=b.records if b else 0, errors_before=b.errors if b else 0,
            records_now=n.records, errors_now=n.errors, fault_kind=kind, fault_firm=firm,
            cluster=cluster, status=status, recoverable=rec, evidence=evidence,
            triage_class=st.get("triage_class"),
            est_rows=estimate_rows(data) if rec == 0 else None))
    return entries


def write_ledger(entries: list[LedgerEntry], out_dir: Path = GATING) -> None:
    out = Path(out_dir)
    (out / "ledger.json").write_text(json.dumps([asdict(e) for e in entries], indent=2) + "\n")
    clusters = defaultdict(list)
    for e in entries:
        clusters[e.cluster].append(e)
    ranked = sorted(clusters.items(), key=lambda kv: (-sum(e.recoverable for e in kv[1]), kv[0]))
    kinds = Counter(e.fault_kind for e in entries)
    statuses = Counter(e.status for e in entries)
    L = ["# Gating ledger", "",
         f"Files in scope: {len(entries)}. Recoverable total: {sum(e.recoverable for e in entries)}.",
         f"Estimated rows (text layer, only where recoverable is 0): {sum(e.est_rows or 0 for e in entries)} "
         f"across {sum(1 for e in entries if e.est_rows)} files.",
         "By kind: " + ", ".join(f"{k} {kinds[k]}" for k in sorted(kinds)) + ".",
         "By status: " + ", ".join(f"{k} {statuses[k]}" for k in sorted(statuses)) + ".", "",
         "## Clusters by recoverable records", "",
         "| cluster | kind | files | recoverable | est_rows | statuses |", "|---|---|---|---|---|---|"]
    for c, es in ranked:
        kd = "/".join(sorted({e.fault_kind for e in es}))
        st = ", ".join(f"{k} {v}" for k, v in sorted(Counter(e.status for e in es).items()))
        L.append(f"| {c} | {kd} | {len(es)} | {sum(e.recoverable for e in es)} | {sum(e.est_rows or 0 for e in es)} | {st} |")
    for c, es in ranked:
        L += ["", f"## {c}", "", "| file | body | kind | status | before | now | recoverable | est_rows |",
              "|---|---|---|---|---|---|---|---|"]
        for e in sorted(es, key=lambda e: -e.recoverable):
            L.append(f"| {e.name} | {e.public_body_id} | {e.fault_kind} | {e.status} | "
                     f"{e.records_before}/{e.errors_before} | {e.records_now}/{e.errors_now} | {e.recoverable} | {e.est_rows if e.est_rows is not None else ''} |")
    (out / "LEDGER.md").write_text("\n".join(L) + "\n")


def set_state(file_urls: list[str], state_path: Path = STATE_PATH, **fields) -> None:
    bad = set(fields) - set(STATE_FIELDS)
    if bad:
        raise ValueError(f"unknown state fields {sorted(bad)}")
    if "status" in fields and fields["status"] not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    if "fault_kind" in fields and fields["fault_kind"] not in KINDS:
        raise ValueError(f"fault_kind must be one of {KINDS}")
    if "triage_class" in fields and fields["triage_class"] not in TRIAGE_CLASSES:
        raise ValueError(f"triage_class must be one of {TRIAGE_CLASSES}")
    state = _load_state(state_path)
    for u in file_urls:
        state.setdefault(u, {}).update(fields)
    Path(state_path).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def main() -> None:
    entries = build_ledger()
    write_ledger(entries)
    gated = sum(1 for s in file_stats().values() if s.gated)
    print(f"gated: {gated}; scope size: {len(entries)}")
    print("by kind:", dict(Counter(e.fault_kind for e in entries)))
    print("no_bytes:", sum(1 for e in entries if e.status == "no_bytes"))


if __name__ == "__main__":
    main()
