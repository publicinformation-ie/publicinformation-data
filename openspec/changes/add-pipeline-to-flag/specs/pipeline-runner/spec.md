## Purpose

The shared CLI runner executes a pipeline's steps in declared order, resolving each step's input/output paths and staleness, so operators can run all, part, or a single bounded window of a pipeline without invoking steps by hand.

## ADDED Requirements

### Requirement: Runner can stop after a named step

The runner SHALL accept a `--to STEP` option that stops execution after the named step has completed, with that step included. Steps after `--to` SHALL NOT execute and SHALL NOT be reported as skipped.

#### Scenario: Stop after an intermediate step

- **WHEN** the runner is invoked with `--to <step>` where `<step>` is not the last step
- **THEN** every step up to and including `<step>` is processed (run or skipped per staleness) and no step after `<step>` is run

#### Scenario: Stop after the last step

- **WHEN** `--to` names the final step in the pipeline
- **THEN** the run behaves the same as a full run with no `--to` option

#### Scenario: `--to` is optional

- **WHEN** the runner is invoked without `--to`
- **THEN** the run proceeds to the end of the pipeline exactly as before

### Requirement: `--from` and `--to` define an inclusive window

When both `--from STEP` and `--to STEP` are provided, the runner SHALL process only the steps from `--from` through `--to` inclusive, in declared order.

#### Scenario: Bounded window runs only its steps

- **WHEN** the runner is invoked with `--from <first> --to <last>` where both are valid steps and `<first>` precedes `<last>`
- **THEN** only steps in that inclusive range are processed and steps outside it are not run

#### Scenario: Single-step window

- **WHEN** `--from` and `--to` name the same step
- **THEN** only that step is processed

#### Scenario: Input chain preserved at window start

- **WHEN** the window starts at a step other than the pipeline's first step
- **THEN** the first step in the window receives the prior step's resolved output as its input and staleness baseline, identical to `--from`-only behaviour

### Requirement: Invalid step ranges fail with an explicit error

The runner SHALL exit non-zero with a message naming the offending value when a supplied step name is not present in the pipeline's step list, or when `--to` names a step that appears before `--from` in the step order. It SHALL NOT silently run nothing or run the whole pipeline on invalid input.

#### Scenario: Unknown `--to` step

- **WHEN** `--to` names a step that is not in the pipeline's step list
- **THEN** the runner exits non-zero with an error that includes the unknown step name

#### Scenario: Unknown `--from` step

- **WHEN** `--from` names a step that is not in the pipeline's step list
- **THEN** the runner exits non-zero with an error that includes the unknown step name

#### Scenario: Inverted range

- **WHEN** `--to` names a step that occurs before `--from` in the declared step order
- **THEN** the runner exits non-zero with an error describing the invalid range

### Requirement: `--to` works with existing runner options

The `--to` option SHALL compose with existing runner behaviour, including `--force`, `--stop-on-error`, `--public-body`, `--doc`, absolute-path upstream steps, and `always_run` steps, without changing their semantics.

#### Scenario: Stop-on-error still halts within the window

- **WHEN** `--to` is set and `--stop-on-error` is set and a step in the window fails
- **THEN** the runner halts immediately with that step's exit code and does not proceed

#### Scenario: Force still forces within the window

- **WHEN** `--to` is set and `--force` is set
- **THEN** every step in the window is run regardless of staleness

#### Scenario: Absolute-path upstream step inside the window

- **WHEN** the window includes an absolute-path upstream step (a step name beginning with `/`)
- **THEN** that step keeps its existing behaviour: its upstream output is validated, the input chain is set, and no subprocess is run

#### Scenario: always_run step inside the window

- **WHEN** the window includes a step listed in the pipeline's `always_run` set
- **THEN** that step runs even when it is not stale, matching existing `always_run` behaviour
