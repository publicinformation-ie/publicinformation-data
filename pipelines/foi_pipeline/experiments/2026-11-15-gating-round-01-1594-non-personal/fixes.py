"""Round 1 fixes: a scorer hypothesis, not an extractor change.

Hypothesis: lib.value_kinds._is_date does not read DD-Mon-YY ("04-Jan-18"), so
those cells count as `reference` and every date_received cell looks foreign.
The gate below widens `_is_date` for the duration of one score_table call only.
Nothing under src/lib or steps/ is changed.
"""
import re
from contextlib import contextmanager

from experiments.gating.downstream import Gate
from experiments.gating.fixes import Fix, register
from lib import value_kinds
from lib.table_structure import DEFAULT_THRESHOLDS, failed_checks, score_table

_DMY_MON = re.compile(
    r"^\d{1,2}[-\s]+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-\s,]+(\d{2}|\d{4})$",
    re.IGNORECASE,
)


@contextmanager
def _wider_dates():
    orig = value_kinds._is_date
    value_kinds._is_date = lambda text: bool(_DMY_MON.match(text)) or orig(text)
    try:
        yield
    finally:
        value_kinds._is_date = orig


def gate_dd_mon_yy(rows, role_map) -> tuple:
    with _wider_dates():
        score = score_table(rows, role_map=role_map)
    return score, failed_checks(score, DEFAULT_THRESHOLDS)


_: Gate = gate_dd_mon_yy
register(Fix(name="gate-dd-mon-yy", kind="gate", rows_from="current", gate=gate_dd_mon_yy, scope="global"))
