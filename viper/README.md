# MANTRA provenance

`viper/` defines the records and cross-file verifier for frozen
MANTRA run plans, realized stage results, artifact lineage, evaluation, and
benchmark confirmation.

## Directory map

| File or directory | Role | Principal interface |
|---|---|---|
| [v3 protocol](docs/ProvenanceS1_v3.md) | Defines the active formal and record contract | Sections 1–23 |
| [publication checklist](docs/PUBLICATION_TODO.md) | Tracks implementation and release work | Protocol, runner, package, and distribution tasks |
| [versioning policy](docs/VERSIONING.md) | Separates software releases from serialized record schemas | Semantic package versions and record `schema_version` values |
| [models](records.py) | Validates protocol records and their internal invariants | `RunSpec`, `ResolvedRun`, `Spec`, `ResolvedSpec`, `BenchmarkSpec` |
| [verifier](verifier.py) | Retrieves referenced files and checks cross-record relationships | `verify_run_result()`, `verify_benchmark_result()` |
| [training continuation](resume.py) | Captures, serializes, restores, and validates optimizer, generator, and stateful-loader state | `capture_resume_state()`, `restore_resume_state()` |
| [plan authoring](authoring.py) | Writes canonical experiment, variant, benchmark, stage, and frozen run-plan files | `freeze_run_plan()`, `write_experiment_spec()`, `write_variant_spec()` |
| [stage execution](execution.py) | Invokes one canonical stage command and hashes every declared output file | `execute_stage_process()` |
| [installed command](cli.py) | Exposes authoring, local validation, and connected verification | `mantra freeze-run`, `mantra validate-stage`, `mantra verify-run` |
| [YAML loading](yaml_io.py) | Parses stage records and rejects duplicate mapping keys | `load_spec()`, `load_resolved_spec()` |
| [examples](examples/provenance/) | Supplies loadable v4 stage and resolved-stage records | Download and build examples |
| [identifiers](ids.py) | Defines run and human-readable identifier types | `RunId`, `HumanId` |
| [package exports](__init__.py) | Exposes the supported authoring, continuation, execution, identifier, and model operations | Public package imports |
| [supporting documents](docs/) | Contains execution and GPU-residency explanations used by the project | Markdown documents and figures |
| [archive](archive/) | Retains prior model drafts and protocol documents | Reference material |
| [v1 protocol](docs/ProvenanceS1.md)<br>[v2 protocol](docs/ProvenanceS1_v2.md) | Retains earlier protocol specifications | Reference material |

The focused model, verifier, and acceptance checks live in the
[repository test directory](../tests/).

## Record and verification flow

The [models](records.py) divide requested state from realized state. A
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
- `verify_run_result(resolved_run, policy=..., fetcher=...)` verifies one
  terminal run and returns its connected run plan, successful resolved stages,
  and measurements.
- `verify_benchmark_result(result, policy=..., fetcher=...)` verifies the benchmark record,
  selected run, confirmation attempt, parity, and metric thresholds.
- `verify_promoted_artifact(pointer, policy=..., fetcher=...)` verifies a promoted
  artifact's producer lineage and benchmark authorization when required.
- `capture_resume_state(...)` captures optimizer state, main-process
  generator state, and the stateful DataLoader state at a training-stage
  boundary.
- `restore_resume_state(...)` restores those values before the next
  DataLoader iterator is created.
- `save_resume_state(path, continuation)` and
  `load_resume_state(path)` write and safely load the reserved
  `resume_state` artifact.
- A custom `fetcher` receives a `GitFileRef` or `HuggingFaceFileRef` and returns
  bytes. Omitting it uses the package Git and Hugging Face retrieval functions.
- `VerificationPolicy` lists the exact source repositories whose artifact
  loader code may execute. Verification fails before loader retrieval when the
  run source is absent from that list.
- `freeze_run_plan(repository_root, draft)` validates and canonicalizes each
  stage spec, records its exact hash and byte count, and writes the sibling
  stage and run `spec.yaml` files.
- `execute_stage_process(...)` verifies the frozen stage-spec bytes, invokes
  the canonical command, and records every produced artifact file.

## Validation

Run these commands from the repository root after activating the `mantra`
Conda environment:

```bash
ruff check viper tests src tools
pyright
python -m pytest -q
```

Ruff checks active Python source and required code documentation. Pyright checks
the v4 model, verifier, authoring, continuation, and execution type contracts.
Pytest exercises model invariants, active YAML examples, plan authoring, command
dispatch, one real stage process, artifact loaders, metrics, continuation,
cross-file relationships, the complete provenance fixture, and tampered-byte
rejection.

## Current boundaries

- `GCEEnvironmentSpec` is the implemented environment type.
- Stage parameter bases preserve versioned JSON values without package
  extension or plugin registration. Projects may apply a local typed model
  before constructing the core parameter record.
- Evaluation predictions use a validated H5AD artifact whose rows identify
  perturbation profiles and whose columns identify genes.
- Each experiment metric records its role, parameters, and exact implementation
  path beneath `src/mantra/metrics/`.
- Artifact loaders execute Python from the Git commit named by `RunSpec.source`.
  Verification therefore accepts only run sources trusted to execute in the
  verifier process.
- The package freezes run plans and invokes individual stage scripts. Full
  attempt orchestration, environment provisioning, snapshot publication, and
  terminal run publication remain on the publication checklist.
