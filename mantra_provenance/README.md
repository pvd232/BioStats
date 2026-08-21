# MANTRA provenance

`mantra_provenance/` defines the records and cross-file verifier for frozen
MANTRA run plans, realized stage results, artifact lineage, evaluation, and
benchmark confirmation.

## Directory map

| File or directory | Role | Principal interface |
|---|---|---|
| [v3 protocol](ProvenanceS1_v3.md) | Defines the active formal and record contract | Sections 1–23 |
| [models](models_v4.py) | Validates protocol records and their internal invariants | `RunSpec`, `ResolvedRun`, `Spec`, `ResolvedSpec`, `BenchmarkSpec` |
| [verifier](verifier.py) | Retrieves referenced files and checks cross-record relationships | `verify_run_result()`, `verify_benchmark_result()` |
| [YAML loading](yaml_io.py) | Parses stage records and rejects duplicate mapping keys | `load_spec()`, `load_resolved_spec()` |
| [examples](examples/provenance/) | Supplies loadable v4 stage and resolved-stage records | Download and build examples |
| [identifiers](ids.py) | Defines run and human-readable identifier types | `RunId`, `HumanId` |
| [serialization](serialization.py) | Produces deterministic JSON bytes and their SHA-256 | `canonical_json_bytes()`, `resolved_spec_sha256()` |
| [package exports](__init__.py) | Exposes package modules and serialization helpers | `models_v4`, `canonical_json_bytes()` |
| [supporting documents](docs/) | Contains execution and GPU-residency explanations used by the project | Markdown documents and figures |
| [archive](archive/) | Retains prior model drafts and protocol documents | Reference material |
| [v1 protocol](ProvenanceS1.md)<br>[v2 protocol](ProvenanceS1_v2.md) | Retains earlier protocol specifications | Reference material |

The focused model, verifier, and acceptance checks live in the
[repository test directory](../tests/).

## Record and verification flow

The [models](models_v4.py) divide requested state from realized state. A
`RunSpec` and its ordered stage specs form the frozen run plan. Each completed
stage publishes one `ResolvedStageRef` containing a resolved stage spec and all
declared artifact files at one immutable snapshot.

```text
RunSpec + ordered stage specs
              │
              ▼
    permitted runtime-state set
              │
              ▼
RunAttempt.resolved_stages[]
              │
              ▼
ResolvedStageRef.snapshot
├── resolved stage spec
└── exact files for every named artifact
              │
              ▼
          ResolvedRun
              │
              ▼
      verify_run_result()
```

The [verifier](verifier.py) starts from `ResolvedRun.spec`, verifies the exact
RunSpec bytes, loads experiment and variant records, retrieves every stage
spec, and checks the realized environment, command, inputs, artifacts,
measurements, logs, and terminal estimator. Artifact loaders are selected by
`ArtifactSpec.loader` from the exact Git commit recorded by `RunSpec.source`.

`verify_benchmark_result()` verifies a second successful attempt, its complete
input lineage, estimator and prediction file parity, metric criteria, and
result status. `verify_promoted_artifact()` verifies the selected producer run
and any benchmark result required to authorize estimator promotion.

## Public operations

- `load_spec(path)` parses a `DownloadSpec`, `BuildSpec`, `EmbedSpec`,
  `TrainSpec`, or `EvaluateSpec` through the discriminated `Spec` union.
- `load_resolved_spec(path)` parses the corresponding realized record through
  `ResolvedSpec`.
- `verify_run_result(resolved_run, fetcher=...)` verifies one terminal run and
  returns its connected run plan, successful resolved stages, and measurements.
- `verify_benchmark_result(result, fetcher=...)` verifies the benchmark record,
  selected run, confirmation attempt, parity, and metric thresholds.
- `verify_promoted_artifact(pointer, fetcher=...)` verifies a promoted
  artifact's producer lineage and benchmark authorization when required.
- A custom `fetcher` receives a `GitFileRef` or `HuggingFaceFileRef` and returns
  bytes. Omitting it uses the package Git and Hugging Face retrieval functions.

## Validation

Run these commands from the repository root after activating the `mantra`
Conda environment:

```bash
ruff check mantra_provenance tests
pyright
python -m pytest -q
```

Ruff checks active Python source, Pyright checks the v4 model and verifier type
contracts, and Pytest exercises model invariants, active YAML examples,
cross-file relationships, the complete provenance fixture, and tampered-byte
rejection.

## Current boundaries

- `GCEEnvironmentSpec` is the implemented environment type.
- `BuildParams` and `EmbedParams` currently admit no fields. New scientific
  parameters require explicit typed fields before those stages can record them.
- Artifact loaders execute Python from the Git commit named by `RunSpec.source`.
  Verification therefore accepts only run sources trusted to execute in the
  verifier process.
- The verifier validates recorded executions and artifact reconstruction. The
  executor that provisions environments and runs stage scripts is outside this
  package.
