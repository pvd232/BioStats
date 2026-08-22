# VIPER provenance tests

`tests/` verifies the protocol models, cross-record provenance checks, artifact
loaders, metric implementations, and exact training resume behavior.

## Test layers

| File | Contract verified |
|---|---|
| [protocol tests](test_protocol.py) | Individual Pydantic models reject invalid fields, paths, identifiers, stage relationships, and checkpoint declarations. |
| [verifier tests](test_verifier.py) | The verifier retrieves referenced bytes and enforces relationships among run plans, stages, inputs, artifacts, attempts, measurements, and benchmarks. |
| [verifier acceptance tests](test_verifier_acceptance.py) | A complete synthetic provenance chain passes through the public verifier; targeted mutations prove that broken hashes, timing, snapshots, and lineage fail. |
| [authoring tests](test_authoring.py) | Canonical experiment, variant, stage, and run-plan files are written at identity-based paths, and each frozen stage reference matches the exact serialized bytes. |
| [parameter-model tests](test_parameter_models.py) | Project Pydantic classes are byte-bound, loaded from a top-level symbol, checked against the correct stage base, and invoked in a dedicated worker. |
| [command tests](test_cli.py) | The installed command dispatches to the public validation surface and reports the validated protocol type. |
| [execution acceptance test](test_execution_acceptance.py) | A real stage entrypoint runs with the canonical command and every declared output file receives an exact hash and byte count. |
| [runner acceptance test](test_runner_acceptance.py) | A real two-stage local run freezes a project parameter model, preflights, executes, publishes, verifies, and rejects a tampered artifact. |
| [resume tests](test_resume.py) | Python, NumPy, PyTorch, optimizer, and stateful DataLoader state round-trip so resumption selects the same next batch with zero or multiple workers. |
| [artifact-loader tests](test_artifact_loaders.py) | A user-owned loader reconstructs its declared JSON artifact. |
| [metric tests](test_metrics.py) | Metric implementations compute their declared values and reject nonfinite inputs. |
| [shared fixtures](fixtures.py) | Independent test modules construct the same valid metric and resume records without importing from another test module. |

`test_verifier_acceptance.py` exercises the verifier with an in-memory document
store. `test_execution_acceptance.py` crosses the process boundary and inspects
the files produced by a real stage command.

## Verification flow

The test layers follow the same boundary as the package:

```text
record verification

Pydantic model validation
        |
        v
canonical plan authoring
        |
        v
referenced-file retrieval and hash checks
        |
        v
cross-record verifier relationships
        |
        v
complete synthetic provenance chain

stage execution

frozen stage spec
        |
        v
real stage process
        |
        v
declared output hashes
```

Runtime resumption and artifact loaders have separate tests because they
operate on live Python objects and materialized files, not only protocol
records.

## Running the tests

From the repository root, activate the `mantra` Conda environment and run:

```text
python -m pytest tests -q
```

A successful run reports every test passing. To check the package and test
documentation contract as well:

```text
ruff check viper tests examples/project/src tools
```

The Ruff command enforces imports, supported Python syntax, and public
docstrings. The pytest command establishes behavioral contracts.

## Adding coverage

Place a test beside the narrowest contract it proves. Reuse
[shared fixtures](fixtures.py) when several modules need the same valid record.
Import production classes from `viper`; never import a
production dependency through another test module. Give every test a docstring
that states the accepted behavior or rejected failure.
