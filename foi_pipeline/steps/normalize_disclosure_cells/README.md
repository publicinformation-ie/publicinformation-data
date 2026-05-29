# normalize_disclosure_cells

Normalizes string cell values in extracted disclosure log data.

**Input:** `transform_disclosure_files/output.json`
**Output:** `output.json` (same structure as input), `changes.json` (audit log of every changed cell)

## Rules applied

| Rule | Applies to | Trigger | Action |
|---|---|---|---|
| `cid_stripped` | PDF only | `(cid:\d+)` in cell | Remove the pattern |
| `newline_to_space` | PDF only | `\n` or `\r` in cell | Replace with `" "` |
| `collapse_spaces` | PDF only | Two or more consecutive spaces | Collapse to `" "` |
| `strip_whitespace` | All types | Leading/trailing whitespace | `.strip()` |

PDF rules apply in order: `cid_stripped` → `newline_to_space` → `collapse_spaces` → `strip_whitespace`.
XLSX/XLS: only `strip_whitespace` applies. Excel newlines (intentional multi-line content) are preserved.

## Querying `changes.json`

```bash
# Count changed cells by rule
jq '[.[].rules_applied[]] | group_by(.) | map({rule: .[0], count: length})' changes.json

# All files with CID artifacts
jq '[.[] | select(.rules_applied | contains(["cid_stripped"])) | .file_url] | unique' changes.json
```
