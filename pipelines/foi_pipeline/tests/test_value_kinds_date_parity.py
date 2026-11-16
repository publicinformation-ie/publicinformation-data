"""The scorer's D-Mon-YY regex must accept exactly what the normalizer parses."""
import pytest

from lib.value_kinds import _D_MON_YY_RE
from steps.extract_disclosures_normalize_rows.process import _DATE_PATTERNS

NORMALIZER_RE = _DATE_PATTERNS[1][0]

SAMPLES = [
    "04-Jan-18", "4-Jan-2018", "04-JAN-18", "04-jan-18", "04-Jan- 18",
    "04-Jan-  18", "04-Jan 18", "04-Jan-2", "04-Jan-20188", "2 7 - J a n -20",
    "Jan-18", "-Jan-18", "04-January-18", "04-Jan", "04-Foo-18", "123-Jan-18",
    "04/01/2018", "2018-01-04", "", "04-Jan-18 ", "x04-Jan-18",
]


@pytest.mark.parametrize("text", SAMPLES)
def test_regexes_agree(text):
    assert bool(_D_MON_YY_RE.match(text)) == bool(NORMALIZER_RE.match(text))


def test_regex_flags_match():
    assert _D_MON_YY_RE.pattern == NORMALIZER_RE.pattern
    assert _D_MON_YY_RE.flags == NORMALIZER_RE.flags
