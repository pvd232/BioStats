# Cloud execution

## Status

GCE environment declarations and resolved host models are implemented. In-place
execution on a pre-provisioned GCE instance and migration from machine-image to
boot-image identity are approved for VIPER 0.1.

## Required claim

VIPER executes a frozen run on the host where the user invokes it and verifies
that each realized stage environment satisfies the effective
`GCEEnvironmentSpec`.

## Current gap

[`GCEEnvironmentSpec`](../../viper/protocol.py),
[`ResolvedGCEEnvironment`](../../viper/protocol.py), and
[`GCEHostContext`](../../viper/protocol.py) define the requested and realized GCE
state. [`run_local()`](../../viper/runner.py) accepts only
`LocalEnvironmentSpec`. [`observe_local_execution()`](../../viper/runtime.py)
always records `LocalHostContext` with a CPU backend.

The current runner therefore rejects a valid GCE plan before stage execution.
The runtime observer also lacks the GCE and CUDA evidence required to construct
the corresponding resolved records.

`LocalEnvironmentSpec.compute` currently accepts only `CPUComputeSpec`. A
host-neutral coordinator should permit the existing `ComputeSpec` union for
local and GCE environments so a local CUDA host follows the same runtime path.

The environment model currently selects `GCEMachineImageRef`. Google defines a
machine image as an instance-cloning and multi-disk-backup resource. The VM
metadata server exposes the active boot image at `instance/image`:
[Machine images](https://docs.cloud.google.com/compute/docs/machine-images) and
[VM metadata](https://docs.cloud.google.com/compute/docs/metadata/querying-metadata#querying).
The GCE contract therefore needs boot-image identity.

## Execution location

The user provisions and enters the execution host with their normal
infrastructure tools. VIPER begins inside that host.

```text
local workstation
└── python train.py --run <run-spec> --stage train

GCE terminal
└── python train.py --run <run-spec> --stage train
```

The same Python interface operates in both locations. The whole-plan command
uses the same application operation:

```text
viper run <run-spec>
```

The Python form preserves the project's ordinary stage entrypoint. The CLI
form gives agents, CI jobs, and automation one project-independent command.
Both forms execute the complete ordered plan. In the Python form, `--stage`
binds the launched callable to its frozen stage specification.

VIPER derives the host kind from the effective stage environment and observed
runtime. The user's infrastructure tooling owns VM provisioning, terminal
access, source placement, and cloud-resource lifecycle.

## Environment selection

The protocol migration introduces one immutable boot-image reference:

```python
class GCEBootImageRef(ProtocolModel):
    project: NonEmptyStr
    name: NonEmptyStr
    id: NonEmptyStr
```

`GCEEnvironmentSpec.boot_image` and
`ResolvedGCEEnvironment.boot_image` carry this value. Plan freezing resolves
the image resource ID. During execution, VIPER reads the active project and
image name from VM metadata, then retrieves the server-defined image ID through
the Compute Engine `images.get` operation. That operation returns the image
resource and requires `compute.images.get`:
[Compute Engine `images.get`](https://docs.cloud.google.com/compute/docs/reference/rest/v1/images/get).

For each stage, the stage environment override supplies the selected
environment when present. `RunSpec.environment` supplies the selected
environment for every remaining stage.

When the selected value is `GCEEnvironmentSpec`, the runtime observer reads the
instance metadata and numerical runtime from the active VM. Compute Engine
exposes instance metadata from a server available to the instance:
[View and query VM metadata](https://docs.cloud.google.com/compute/docs/metadata/querying-metadata).

The observer constructs:

```text
ResolvedGCEEnvironment
├── immutable boot-image identity
├── machine type
├── CPU or CUDA compute request
└── resolved lockfile identity

ExecutionContext
├── GCEHostContext
├── CPUContext
├── CPUBackendContext or CUDABackendContext
├── NumericalRuntimeContext
├── RandomnessContext
└── applied reproducibility controls
```

The [process-startup contract](PROCESS_STARTUP.md) applies the run-wide controls
before the stage callable executes.

## Persisted evidence

Each resolved stage stores its `ResolvedGCEEnvironment` and `ExecutionContext`.
The ordinary attempt journal, stage snapshots, artifacts, measurements, logs,
and terminal `resolved.yaml` remain in the repository's configured VIPER
workspace and store on the active host.

The application result returns the run ID, attempt ID, terminal result path,
and journal path. A later storage backend may publish the same immutable files
to durable object storage while preserving the execution contract.

## Verification

| Check | Rule |
|---|---|
| `environment.kind` | The resolved environment and observed host both identify GCE. |
| `gce.boot_image` | The observed boot-image project, name, and server-defined ID equal the frozen request. |
| `gce.machine_type` | The resolved environment and observed host report the requested machine type. |
| `gce.compute` | The observed backend kind, CUDA model, and device count satisfy the frozen compute request. |
| `gce.lockfile` | The resolved lockfile points to the exact lockfile selected by the effective environment. |
| `runtime.controls` | The execution context records the run-wide determinism, precision, parallelism, and randomness controls. |
| `run.result` | The terminal result passes ordinary run verification. |

## Propagation

| Surface | Required change |
|---|---|
| Protocol | Replace `GCEMachineImageRef` with immutable `GCEBootImageRef`; allow `ComputeSpec` on local and GCE environments. |
| Coordinator | Replace the local-environment gate with selection of the effective environment for each stage. |
| Preflight | Accept `LocalEnvironmentSpec` and `GCEEnvironmentSpec`; check the active host against the selected kind. |
| Runtime | Add local CUDA and GCE host observers that construct the existing protocol models. |
| Application | Expose one `run` operation for execution on the active host. |
| Python interface | Route `viper.run(stage_callable)` through the same coordinator and process-startup contract. |
| CLI | Route `viper run` through the application `run` operation. |
| Verification | Apply the seven checks above before returning a successful run result. |
| Tests | Exercise local CPU, local CUDA when available, deterministic GCE fixtures, and one live GCE smoke profile. |

## Acceptance case

A frozen run selects a `GCEEnvironmentSpec` containing one boot image,
machine type, L4 accelerator, and lockfile. The user opens a terminal on the
matching VM and invokes the installed project entrypoint. VIPER executes the
run on that VM, records the GCE and CUDA evidence, publishes the terminal run,
and verifies every environment relationship.

A second case executes the same plan on a VM with another machine type. The
`gce.machine_type` check rejects the resolved stage.

## Release boundary

VIPER 0.1 supports a trusted, pre-provisioned single host containing the frozen
source, credentials, dependency environment, accelerator software, workspace,
and artifact store.

The user's infrastructure tooling owns host provisioning and terminal access.
OCI confinement supplies filesystem and network enforcement in the stable
hardening release. Distributed execution and durable remote publication receive
separate contracts when their first implementations enter scope.

## Implementation order

1. Replace the GCE machine-image fields with immutable boot-image identity and
   permit `ComputeSpec` on local environments.
2. Rename the complete-run operation from `run_local` to `run`.
3. Generalize preflight and the coordinator across local and GCE environments.
4. Implement GCE host, boot-image, and CUDA runtime observation.
5. Apply the environment verification rules to every completed stage.
6. Add deterministic local and GCE coverage.
7. Run the installed-wheel acceptance project on the advertised GCE profile.
