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
STATE_FIELDS = ("fault_kind", "fault_firm", "cluster", "status", "note")
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


def _load_state(path: Path) -> dict:
    p = Path(path)
    return json.loads(p.read_text() or "{}") if p.is_file() else {}


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
        cluster, firm = default_cluster(n, kind), False
        st = state.get(url, {})
        kind = st.get("fault_kind", kind)
        firm = st.get("fault_firm", firm)
        cluster = st.get("cluster", cluster)
        status = st.get("status", status)
        notes = [x for x in (note if "status" not in st and "fault_kind" not in st else None, st.get("note")) if x]
        if notes:
            evidence = f"{evidence}; " + "; ".join(notes)
        data = pdf_bytes(url, cache_dir)
        if data is None:
            status = "no_bytes"
        entries.append(LedgerEntry(
            file_url=url, public_body_id=n.public_body_id, name=n.name,
            sha256=content_sha(data) if data is not None else None, pdf_extractor=n.pdf_extractor,
            worst_role_contamination=n.worst_role_contamination, anchored_row_share=n.anchored_row_share,
            failed_checks=n.failed_checks,
            records_before=b.records if b else 0, errors_before=b.errors if b else 0,
            records_now=n.records, errors_now=n.errors, fault_kind=kind, fault_firm=firm,
            cluster=cluster, status=status, recoverable=recoverable(n, b), evidence=evidence))
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
         "By kind: " + ", ".join(f"{k} {kinds[k]}" for k in sorted(kinds)) + ".",
         "By status: " + ", ".join(f"{k} {statuses[k]}" for k in sorted(statuses)) + ".", "",
         "## Clusters by recoverable records", "",
         "| cluster | kind | files | recoverable | statuses |", "|---|---|---|---|---|"]
    for c, es in ranked:
        kd = "/".join(sorted({e.fault_kind for e in es}))
        st = ", ".join(f"{k} {v}" for k, v in sorted(Counter(e.status for e in es).items()))
        L.append(f"| {c} | {kd} | {len(es)} | {sum(e.recoverable for e in es)} | {st} |")
    for c, es in ranked:
        L += ["", f"## {c}", "", "| file | body | kind | status | before | now | recoverable |",
              "|---|---|---|---|---|---|---|"]
        for e in sorted(es, key=lambda e: -e.recoverable):
            L.append(f"| {e.name} | {e.public_body_id} | {e.fault_kind} | {e.status} | "
                     f"{e.records_before}/{e.errors_before} | {e.records_now}/{e.errors_now} | {e.recoverable} |")
    (out / "LEDGER.md").write_text("\n".join(L) + "\n")


def set_state(file_urls: list[str], state_path: Path = STATE_PATH, **fields) -> None:
    bad = set(fields) - set(STATE_FIELDS)
    if bad:
        raise ValueError(f"unknown state fields {sorted(bad)}")
    if "status" in fields and fields["status"] not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    if "fault_kind" in fields and fields["fault_kind"] not in KINDS:
        raise ValueError(f"fault_kind must be one of {KINDS}")
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
