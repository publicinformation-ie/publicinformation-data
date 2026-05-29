#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

from scripts.file_utils import read_json, write_json, write_status, IncrementalWriter

STEP_NAME = "normalize_disclosure_cells"

_CID_RE = re.compile(r'\(cid:\d+\)')
_MULTI_SPACE_RE = re.compile(r' {2,}')


def _normalize_cell(file_type, value):
    """Normalize a single cell value. Returns (normalized_value, rules_applied).

    PDF: strip (cid:X) glyphs, replace newlines with spaces, collapse
    multi-spaces, then strip whitespace. XLSX/XLS: strip whitespace only.
    Non-string values pass through unchanged with an empty rules list.
    """
    if not isinstance(value, str):
        return value, []

    rules = []
    result = value

    if file_type == "pdf":
        new = _CID_RE.sub("", result)
        if new != result:
            rules.append("cid_stripped")
            result = new

        new = result.replace("\n", " ").replace("\r", " ")
        if new != result:
            rules.append("newline_to_space")
            result = new

        new = _MULTI_SPACE_RE.sub(" ", result)
        if new != result:
            rules.append("collapse_spaces")
            result = new

    new = result.strip()
    if new != result:
        rules.append("strip_whitespace")
        result = new

    return result, rules
