# Attempt execution

## Status

Successful local execution is implemented. Failed-attempt publication,
successive attempt allocation, and explicit retry are approved for VIPER 0.1.

## Required claim

Every invocation of a frozen run plan produces one durable terminal attempt.
Retry creates a new attempt and preserves the evidence from every earlier
attempt.

## Current gap

[`run_local()`](../../viper/runner.py) assigns attempt ID `1`. It constructs a
`RunAttempt` after every stage succeeds. A stage failure exits before a terminal
attempt is published.

The current runner therefore proves successful execution for one attempt.
Failure reporting, attempt `2` allocation, and retry history remain open.

## Contract models

```python
class AttemptFailure(ProtocolModel):
    code: ErrorCode
    stage_id: StageId | None
    message: NonEmptyStr
    occurred_at: AwareDatetime


class RunAttempt(ProtocolModel):
    attempt_id: int = Field(ge=1)
    status: AttemptStatus
    started_at: AwareDatetime
    completed_at: AwareDatetime
    resolved_stages: tuple[ResolvedStageRef, ...]
    measurement_files: tuple[ResolvedFileRef, ...]
    log_files: tuple[ResolvedFileRef, ...]
    failure: AttemptFailure | None
```

This replaces the current free-text `failure_reason` with one typed failure.
The remaining fields preserve their current meaning.

## Allocation and ownership

The coordinator acquires one operating-system-managed advisory lock for the run.
That lock is released automatically when its process exits. The coordinator
then selects:

```text
max(persisted attempt IDs) + 1
```

The persisted IDs come from terminal run history and every attempt journal
beneath the run workspace. The selected ID is written to the durable journal
before preflight or stage execution begins. One coordinator owns one active
attempt. A second coordinator receives a stable ownership failure.

After acquiring a released lock, the coordinator reconciles any prior
nonterminal journal. It closes that attempt as `failed` with failure code
`coordinator_lost`, publishes the available logs and completed stage snapshots,
and then allocates the next ID.

## Terminal outcomes

An attempt closes with exactly one terminal status:

| Status | Meaning |
|---|---|
| `succeeded` | Every stage and terminal publication completed. |
| `failed` | Preflight, execution, verification, or publication failed. |
| `cancelled` | The coordinator acknowledged an explicit cancellation request. |
| `preempted` | The execution host ended the attempt before completion. |

VIPER publishes the attempt journal and available logs for every outcome. A
failed attempt retains every verified stage snapshot completed before failure.

## Retry

Retry receives the same frozen `RunSpec` and allocates the next attempt ID.
Every earlier attempt remains immutable. A retry policy may limit the number of
attempts and select the terminal statuses eligible for retry.

## Verification

| Check | Rule |
|---|---|
| `attempt.order` | Attempt IDs are unique and strictly increasing. |
| `attempt.terminal` | Every published attempt has exactly one terminal status. |
| `attempt.files` | The attempt file list matches the published journal and logs. |
| `attempt.failure` | A failed attempt has one failure value consistent with its journal. |
| `attempt.retry` | A retry uses the same frozen run plan and a greater attempt ID. |

## Propagation

| Surface | Required change |
|---|---|
| Workspace | Allocate attempt IDs while holding the run lock. |
| Journal | Record allocation and every state transition before the corresponding side effect. |
| Runner | Close and publish attempts on success, failure, cancellation, or preemption. |
| Application | Add explicit retry. |
| Verification | Check attempt ordering, terminal state, failure identity, and preserved files. |
| Tests | Exercise a failed first attempt followed by a successful retry. |

## Acceptance case

A two-stage run completes `download` and fails during `train`. VIPER publishes
attempt `1` as `failed`, including the download snapshot and failure log. An
explicit retry creates attempt `2`, completes both stages, and publishes the
terminal run with both attempts.

Changing attempt `1` after attempt `2` has been published fails file-identity
verification.

## Implementation order

1. Replace the stale-file lock with an operating-system-managed advisory lock.
2. Reconcile an abandoned nonterminal journal after lock acquisition.
3. Allocate successive attempt IDs from persisted attempt history.
4. Close and publish failed attempts with their journals and logs.
5. Add explicit retry through the Python API and JSON CLI.
6. Add attempt-order and terminal-state verifier rules.
7. Add the fail-then-retry acceptance case.

Crash adoption, partial-publication recovery, and remote orphan reconciliation
extend this contract after the first complete retry path works.
