# Cloud execution

## Status

GCE environment declarations and resolved host models are implemented. Remote
execution on a pre-provisioned GCE instance is approved for VIPER 0.1.

## Required claim

VIPER executes a frozen run plan on a selected GCE instance and verifies that
the realized host satisfies the plan's `GCEEnvironmentSpec`.

## Current gap

[`GCEEnvironmentSpec`](../../viper/protocol.py),
[`ResolvedGCEEnvironment`](../../viper/protocol.py), and
[`GCEHostContext`](../../viper/protocol.py) define requested and realized GCE
state. [`run_local()`](../../viper/runner.py) accepts only the trusted-local
environment. The application surface currently ends at local execution.

The protocol can describe and verify a remote result. The runner produces local
results only.

## Execution target

```python
class GCEExecutionTarget(ProtocolModel):
    project: NonEmptyStr
    zone: NonEmptyStr
    instance: NonEmptyStr
    remote_root: NonEmptyStr


class RunGCERequest(ProtocolModel):
    repository_root: Path
    run_spec: Path
    target: GCEExecutionTarget
    result_transfer: Literal["remote", "pull"] = "remote"
    timeout_seconds: float | None = Field(default=None, gt=0)
```

The target is operational input. It selects one host on which the frozen plan
may run. The scientific run plan continues to describe the permitted runtime
environment.

The run plan fixes the permitted environment through `GCEEnvironmentSpec`,
including the machine image, machine type, compute requirements, and dependency
lockfile. The selected host supplies one realized runtime state from that
permitted set.

## Alpha transport

The first transport uses `gcloud compute scp` to transfer one verified execution
bundle and `gcloud compute ssh` to invoke the installed VIPER command on an
existing Linux VM. Google documents both operations: [Transfer files to Linux
VMs](https://docs.cloud.google.com/compute/docs/instances/transfer-files) and
[Connect to Linux
VMs](https://docs.cloud.google.com/compute/docs/connect/standard-ssh).

The execution bundle contains one archive of the exact source commit, the
frozen run documents, each referenced local-store revision, and a manifest of
their paths, SHA-256 digests, and byte counts. Git and Hugging Face references
remain immutable remote references and are materialized by the remote runner.

```text
local viper run-gce
-> preflight the frozen plan
-> build and verify the execution bundle
-> transfer the bundle to an attempt-specific remote directory
-> invoke the remote VIPER runner
-> verify the bundle manifest
-> query realized GCE host metadata
-> execute and verify the run on the VM
-> return the terminal result identity and remote location
```

The remote bootstrap reads instance identity and image information from the GCE
metadata service. Compute Engine provides each instance with a dedicated
metadata server that is accessible from the instance: [View and query VM
metadata](https://docs.cloud.google.com/compute/docs/metadata/querying-metadata).

## Persisted evidence

The remote runner writes the normal attempt journal, stage snapshots, artifacts,
measurements, logs, and terminal `resolved.yaml` beneath persistent storage on
the VM. `ResolvedGCEEnvironment` and `GCEHostContext` record the realized host.

The remote command writes one JSON result document. The local transport retrieves
that document and verifies its byte identity. The application result contains
the run ID, attempt ID, terminal result digest, and remote result location. A
successful application result requires a completed SSH command and verified
terminal run.

With `result_transfer="pull"`, the transport also retrieves the terminal
`resolved.yaml` and every immutable local-store revision it references. It
writes those revisions beneath the caller's configured local store and repeats
terminal verification locally. With `result_transfer="remote"`, the evidence
stays on the VM's persistent disk and the result reports its location.

## Verification

| Check | Rule |
|---|---|
| `gce.target` | The remote execution reports the requested project, zone, and instance. |
| `gce.bundle` | Every transferred source, plan, and local-store file matches the execution-bundle manifest. |
| `gce.machine_image` | The realized boot image satisfies the frozen environment. |
| `gce.machine_type` | The realized machine type satisfies the frozen environment. |
| `gce.compute` | The realized CPU, memory, accelerator, and driver values satisfy the frozen compute requirements. |
| `gce.lockfile` | The installed dependency environment matches the frozen lockfile identity. |
| `gce.result` | The terminal remote result passes ordinary run verification. |
| `gce.transfer` | A pulled result contains every referenced revision and passes local verification. |

## Propagation

| Surface | Required change |
|---|---|
| Application | Add `run_gce` request, success, failure, and capability discovery. |
| CLI | Add `viper run-gce` with human and JSON output. |
| Transport | Add a bounded `gcloud compute ssh` adapter. |
| Remote bootstrap | Query host metadata and invoke the backend-neutral run coordinator. |
| Persistence | Keep terminal evidence on persistent remote storage; pull and verify it when requested. |
| Verification | Apply the GCE target, bundle, environment, and result checks before reporting success. |
| Tests | Add a deterministic transport test and one live GCE smoke profile. |

## Acceptance case

A frozen run requests one supported GCE machine image, machine type, accelerator,
and lockfile. `run_gce` selects a pre-provisioned instance, executes the existing
multi-stage acceptance project, verifies the terminal run on that host, pulls
the referenced revisions, and verifies the result locally.

A second case selects a host with a different machine type. Preflight or remote
environment verification fails with `gce.machine_type` before a successful run
is reported.

## Alpha boundary

VIPER 0.1 assumes a trusted, pre-provisioned GCE VM with the required source,
credentials, persistent disk, Python environment, and accelerator software.
Cloud-resource creation and deletion stay with the user's infrastructure
tooling.

OCI confinement, automatic provisioning, distributed workers, durable object
storage publication, cancellation acknowledgement, and remote crash adoption
extend this contract after the single-host path passes live validation.

## Implementation order

1. Extract the local orchestration body into a backend-neutral coordinator.
2. Add GCE request and result types to the application API.
3. Implement the SSH transport and remote bootstrap.
4. Record and verify realized GCE state.
5. Add deterministic transport coverage.
6. Run the advertised live GCE smoke test.
