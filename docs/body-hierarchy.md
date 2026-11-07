# Body hierarchy: owning parent vs sponsoring department

The public-bodies dataset carries two distinct relationships:

- `parent_id` — URI of the body's owning/parent body in the state's corporate hierarchy (e.g. Córas Iompair Éireann for Bus Átha Cliath). This is not the sponsoring department.
- `government_department_id` — URI of the sponsoring government department (the body's aegis). This is not the owning parent. For a local authority it is the authority itself.

## Worked example

Córas Iompair Éireann (`coras-iompair-eireann`) is the parent of Irish Rail (`irish-rail-iarnrod-eireann`), Bus Éireann (`bus-eireann`) and Bus Átha Cliath (`bus-atha-cliath`). All four are sponsored by the Department of Transport (`department-of-transport`); none has `parent_id` = `department-of-transport`. Further verified groups, each with `parent_id` set to the group body and the same sponsor (`department-of-transport`): daa plc (`daa-plc`) is the parent of `daa-airport-services-ltd`, `daa-international-ltd`, `daa-operations-ltd`, `daa-finance-plc` and `daa-pension-corporate-trustee-dac`; Shannon Group PLC (`shannon-group-plc`) is the parent of `shannon-airport-authority-dac`, `shannon-airport-authority-financial-services-dac`, `shannon-airport-authority-pension-corporate-trustee-dac` and `shannon-commercial-enterprises-dac`; Port of Cork Company (`port-of-cork-company`) is the parent of `port-of-cork-infrastructure-development-company-dac`. A name alone does not imply group membership: for example `shannon-heritage-designated-activity-company` and `shannon-broadband-ltd` have a different sponsor and no `parent_id`.

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
