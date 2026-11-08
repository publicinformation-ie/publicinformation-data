"""Repair ligature character widths in PyMuPDF's table character list.

PyMuPDF expands a ligature glyph into one full-width character followed by
zero-width characters at the glyph's right edge; ``Table.extract()`` sorts a
cell's characters by ``x0``, so kerning can put a neighbour before a
zero-width component ("batet ry"). Spreading the glyph's width evenly over its
components keeps the order correct. See
docs/superpowers/plans/2026-11-08-table-ligature-repair.md.
"""

ZERO_WIDTH_EPS = 0.01
_MAX_LOOKBACK = 5


def _is_component(c: dict) -> bool:
    return (c["upright"] and c["x1"] - c["x0"] < ZERO_WIDTH_EPS
            and bool(c["text"].strip()))


def _find_base(chars: list, i: int):
    comp = chars[i]
    for j in range(i - 1, max(i - 1 - _MAX_LOOKBACK, -1), -1):
        b = chars[j]
        if (b["upright"] and b["x1"] - b["x0"] >= ZERO_WIDTH_EPS
                and abs(b["x1"] - comp["x0"]) < ZERO_WIDTH_EPS
                and b["top"] == comp["top"] and b["fontname"] == comp["fontname"]):
            return j
    return None


def repair_ligature_widths(chars: list[dict]) -> int:
    """Mutate ``chars`` in place; return the number of glyphs repaired."""
    groups: dict[int, list[int]] = {}
    for i, c in enumerate(chars):
        if _is_component(c):
            base = _find_base(chars, i)
            if base is not None:
                groups.setdefault(base, []).append(i)
    for base_i, comps in groups.items():
        base = chars[base_i]
        x0, x1 = base["x0"], base["x1"]
        slice_w = (x1 - x0) / (len(comps) + 1)
        for k, c in enumerate([base_i] + comps):
            ch = chars[c]
            ch["x0"] = x0 + k * slice_w
            ch["x1"] = x0 + (k + 1) * slice_w
            ch["width"] = ch["adv"] = slice_w
    return len(groups)
