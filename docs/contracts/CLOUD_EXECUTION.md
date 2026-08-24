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
state. [`run()`](../../viper/runner.py) accepts only
`LocalEnvironmentSpec`. [`observe_local_execution()`](../../viper/runtime.py)
always records `LocalHostContext` with a CPU backend.

The current runner therefore rejects a valid GCE plan before stage execution.
The runtime observer also lacks the GCE and CUDA evidence required to construct
the corresponding resolved records.

`LocalEnvironmentSpec.compute` currently accepts only `CPUComputeSpec`. The
[process-startup contract](PROCESS_STARTUP.md) now owns the migration to the
existing `ComputeSpec` union and the local CUDA observer. Cloud execution reuses
that compute path after adding GCE host observation.

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


class PythonDistributionSpec(ProtocolModel):
    name: NormalizedDistributionName
    version: NonEmptyStr


class PythonEnvironmentSpec(ProtocolModel):
    python_version: NonEmptyStr
    distributions: tuple[PythonDistributionSpec, ...] = Field(min_length=1)
```

Distribution names use lowercase form with each run of `.`, `_`, or `-`
replaced by `-`. The distribution tuple is sorted by name and contains one
entry per name. This follows the Python packaging name-normalization rule:
[Name normalization](https://packaging.python.org/en/latest/specifications/name-normalization/).

`GCEEnvironmentSpec.boot_image` and
`ResolvedGCEEnvironment.boot_image` carry this value. The author selects the
server-defined image ID before freezing. Plan freezing preserves that immutable
selection. During execution, VIPER reads the active image project and name from
VM metadata, then retrieves the server-defined image ID through the Compute
Engine `images.get` operation. VIPER compares the observed value with the frozen
selection. The API operation requires `compute.images.get`:
[Compute Engine `images.get`](https://docs.cloud.google.com/compute/docs/reference/rest/v1/images/get).

`GCEEnvironmentSpec.python_environment` stores the exact Python version and
the sorted installed-distribution mapping selected by the author. VIPER exposes
an environment-observation helper for authoring. Plan freezing validates the
selected value. The child reconstructs the same mapping through Python package
metadata and stores it as `ResolvedGCEEnvironment.python_environment`.

The lockfile reference identifies the environment-construction input. The
Python environment value constrains the distributions that actually execute
the stage. `ExecutionContext.numerical_runtime` continues to record PyTorch,
NumPy, BLAS, LAPACK, CUDA, and thread-pool facts used by numerical execution.

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
├── resolved lockfile identity
└── resolved Python environment

ExecutionContext
├── GCEHostContext
│   ├── instance project
│   └── observed boot-image identity
├── CPUContext
├── CPUBackendContext or CUDABackendContext
└── NumericalRuntimeContext

ProcessStartupReceipt
├── applied startup environment
├── queried reproducibility controls
└── initialized generator-state digests
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
| `gce.python` | The Python version and installed-distribution mapping observed by the child equal the frozen `python_environment`. |
| `runtime.controls` | The execution context records the run-wide determinism, precision, parallelism, and randomness controls. |
| `run.result` | The terminal result passes ordinary run verification. |

## Propagation

| Surface | Required change |
|---|---|
| Protocol | Replace `GCEMachineImageRef` with immutable `GCEBootImageRef`; add `PythonEnvironmentSpec`; consume the `ComputeSpec` startup contract for GCE stages. |
| Coordinator | Replace the local-environment gate with selection of the effective environment for each stage. |
| Preflight | Accept `LocalEnvironmentSpec` and `GCEEnvironmentSpec`; check the active host against the selected kind. |
| Runtime | Reuse the process-startup compute observer and add the GCE host observer. |
| Application | Expose one `run` operation for execution on the active host. |
| Python interface | Route `viper.run(stage_callable)` through the same coordinator and process-startup contract. |
| CLI | Route `viper run` through the application `run` operation. |
| Verification | Apply the eight checks above before returning a successful run result. |
| Tests | Exercise local CPU, local CUDA when available, deterministic GCE fixtures, and one live GCE smoke profile. |

## Acceptance case

A frozen run selects a `GCEEnvironmentSpec` containing one boot image,
machine type, L4 accelerator, and lockfile. The user opens a terminal on the
matching VM and invokes the installed project entrypoint. VIPER executes the
run on that VM, records the GCE and CUDA evidence, publishes the terminal run,
and verifies every environment relationship.

A second case executes the same plan on a VM with another machine type. The
`gce.machine_type` check rejects the resolved stage. A third case changes one
installed distribution version and fails `gce.python`.

## Release boundary

VIPER 0.1 supports a trusted, pre-provisioned single host containing the frozen
source, credentials, dependency environment, accelerator software, workspace,
and artifact store. Each stage uses one CPU backend or one selected CUDA device.

The user's infrastructure tooling owns host provisioning and terminal access.
OCI confinement supplies filesystem and network enforcement in the stable
hardening release. Distributed execution and durable remote publication receive
separate contracts when their first implementations enter scope.

## Implementation order

1. Replace the GCE machine-image fields with immutable boot-image identity.
2. Use the host-neutral `run` operation for complete-run coordination.
3. Generalize preflight and the coordinator across local and GCE environments.
4. Reuse the process-startup compute observer and implement GCE host and
   boot-image observation.
5. Apply the environment verification rules to every completed stage.
6. Add deterministic local and GCE coverage.
7. Run the installed-wheel acceptance project on the advertised GCE profile.
