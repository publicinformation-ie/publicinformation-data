# Body hierarchy: owning parent vs sponsoring department

The public-bodies dataset carries two distinct relationships:

- `parent_id` — URI of the body's owning/parent body in the state's corporate hierarchy (e.g. Córas Iompair Éireann for Bus Átha Cliath). This is not the sponsoring department.
- `government_department_id` — URI of the sponsoring government department (the body's aegis). This is not the owning parent. For a local authority it is the authority itself.

## Worked example

Córas Iompair Éireann (1186) is the parent of 1073, 1074 and 1443. All four are sponsored by the Department of Transport (1213); none has `parent_id` = 1213. Further groups: daa plc (1192), Shannon Group (1699), Port of Cork (1633).

Local authorities (e.g. Carlow County Council) have `government_department_id` equal to their own `@id`. This is expected and is not a cycle.

## Audit

```bash
uv run python scripts/audit_body_hierarchy.py            # readable report
uv run python scripts/audit_body_hierarchy.py --json     # machine-readable
uv run python scripts/audit_body_hierarchy.py --check    # exit 1 only on hard findings
uv run python scripts/audit_body_hierarchy.py --path FILE  # audit a fixture
```

Hard findings (fail `--check`): `dangling_parent`, `self_parent`, `parent_cycle`.
Soft findings: `department_mismatch` (child and parent have different sponsoring departments).
Informational: `group_without_parent` (a named state-group body lacking `parent_id`).

## Known exceptions

Current soft `department_mismatch` findings, source-backed, not changed without an authoritative CSO correction:

- `First Home Scheme Ireland DAC`
- `Stepping Out (Athlone) Ltd`
