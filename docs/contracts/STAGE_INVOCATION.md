# Stage invocation

## Status

Project parameter identity and validation are implemented. Typed delivery to
the stage implementation is approved for VIPER 0.1.

## Required claim

VIPER verifies that the selected stage implementation received the exact
parameter value accepted by the stage's frozen parameter model.

## Current gap

The parameter worker validates `ParameterizedSpec.params` and writes the
effective mapping. The stage process performs that validation before launch.
[`stage_worker.py`](../../viper/stage_worker.py) then gives the project script
the stage-spec path through `sys.argv`. The project script loads and interprets
the file itself.

The validated value leaves runner custody before stage invocation. A successful
stage therefore establishes parameter validity and stage execution as separate
facts. Typed delivery remains unsupported.

## Contract models

`StageContext` is the user-facing runtime value for one stage invocation:

```python
ParamsT = TypeVar("ParamsT", bound=ParameterSet)


class StageContext(ProtocolModel, Generic[ParamsT]):
    schema_version: Literal[1] = 1
    run_id: RunId
    attempt_id: int
    stage_id: StageId
    parameter_model: ParameterModelRef
    params: ParamsT
    inputs: dict[InputName, Path]
    artifacts: dict[ArtifactName, Path]
```

`StageCallable` is a top-level project function:

```python
def run(context: StageContext[ProjectParams]) -> None:
    ...
```

The frozen stage identifies the function by repository-relative path and
top-level symbol. The source commit, path, symbol, SHA-256, and byte count fix
the implementation.

## Execution

The stage worker performs this sequence:

```text
load frozen stage spec
-> verify parameter-model bytes
-> validate params into the selected project class
-> load the selected stage callable
-> construct StageContext with the typed parameter object
-> call run(context)
-> record the completed invocation
```

The stage callable receives validated parameters directly. Input and artifact
paths come from the same context.

## Persisted evidence

`ResolvedBaseSpec` stores a `StageInvocationReceipt` containing the stage
implementation identity, parameter-model identity, canonical parameter digest,
canonical binding digest, start time, completion time, and process outcome.

The canonical binding replaces each runtime path with its repository-relative
logical path before hashing. Absolute workspace paths exist only in the
user-facing runtime value.

## Verification

| Check | Rule |
|---|---|
| `stage.implementation` | The receipt identifies the implementation frozen by the stage spec and run source. |
| `parameter_model.identity` | The receipt identifies the frozen parameter model. |
| `parameter.value` | The canonical digest of the delivered mapping equals the digest of `stage.params`. |
| `stage.context` | The receipt binding digest equals the canonical binding reconstructed from the resolved inputs and outputs. |
| `stage.outcome` | A successful resolved stage has one successful invocation receipt. |

These checks establish delivery to the callable. Project tests establish how
the callable uses each parameter.

## Propagation

| Surface | Required change |
|---|---|
| Protocol | Add stage implementation identity and `StageInvocationReceipt`. |
| Authoring | Resolve the top-level callable and freeze its exact bytes. |
| Runtime | Add `StageContext` and invoke the callable with the validated project parameter object. |
| Persistence | Store the canonical parameter and context digests in the resolved stage. |
| Verification | Apply the five stage-invocation checks. |
| Tests | Replace constant fixture scripts with callables that assert typed parameters and declared paths. |
| Documentation | Show the callable interface in the project extension guide. |

## Acceptance case

`TinyTrainParameters.epochs` is `3`. VIPER calls `train(context)` with
`context.params.epochs == 3`. The fixture writes the value `3` into a declared
artifact, and terminal verification accepts the invocation receipt.

The rejection case changes the delivered canonical mapping to `epochs = 2`
while preserving the frozen stage spec. `parameter.value` fails.

## Implementation order

1. Add the context and invocation-receipt models.
2. Add stage-callable loading and typed context construction.
3. Route every parameterized stage through the callable interface.
4. Add verifier rules and acceptance coverage.
5. Remove the script-path argument handoff after examples migrate.
