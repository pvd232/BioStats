# Stage invocation

## Status

Project parameter identity and validation are implemented. Decorated callable
identity and typed delivery are approved for VIPER 0.1.

## Required claim

VIPER verifies that the exact stage callable frozen by the plan received the
parameter value, input paths, and artifact paths accepted for that stage.

## Current gap

The parameter worker validates `ParameterizedSpec.params` and writes the
effective mapping. The stage process repeats that validation before launch.
[`stage_worker.py`](../../viper/stage_worker.py) then supplies the stage-spec
path through `sys.argv` and executes `BaseSpec.script` with `runpy.run_path()`.

The project script reloads and interprets the stage document. The completed
stage therefore establishes parameter validity and script execution as separate
facts. The current resolved stage lacks evidence that one identified callable
received the validated value.

## Contract models

`StageImplementationRef` identifies one top-level callable in the project
source:

```python
class StageImplementationRef(ProtocolModel):
    path: PythonRepoRelPath
    symbol: PythonSymbol
    sha256: Sha256
    bytes: int = Field(gt=0)
```

`StageContext` carries one validated stage invocation:

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

`StageImplementationRef` identifies the callable invoked for the stage. At
execution time, VIPER constructs one `StageContext` from the frozen stage
specification and the active run attempt, then passes that context as the
callable's sole argument.

The stage specification and active attempt join the two models:

```text
StageImplementationRef
├── path: project/stages/train.py
└── symbol: train
          │
          ▼
load the function train
          │
          │ receives
          ▼
StageContext[TrainParameters]
├── params: TrainParameters(epochs=3)
├── inputs: materialized input paths
├── artifacts: writable output paths
├── run_id
├── attempt_id
└── stage_id
```

Conceptually, the runner performs this invocation:

```python
train = load_callable(stage.implementation)

params = TrainParameters.model_validate(stage.params)

context = StageContext[TrainParameters](
    run_id=run.run_id,
    attempt_id=attempt.attempt_id,
    stage_id=stage.stage_id,
    parameter_model=stage.parameter_model,
    params=params,
    inputs=materialized_inputs,
    artifacts=writable_artifact_paths,
)

train(context)
```

`StageImplementationRef` remains stable across invocations because it
identifies source code. VIPER creates a new `StageContext` for each run attempt
because the invocation identity, validated values, and workspace paths belong
to that attempt.

Each parameterized stage replaces `BaseSpec.script` with:

```python
implementation: StageImplementationRef
```

The source commit, path, symbol, SHA-256, and byte count identify the callable.

## Project interface

The project decorates an ordinary top-level function:

```python
import viper


@viper.train_stage(parameter_model=TrainParameters)
def train(context: viper.StageContext[TrainParameters]) -> None:
    ...


if __name__ == "__main__":
    viper.run(train)
```

The decorator records the stage kind and parameter-model class for authoring.
Plan freezing resolves the function to `StageImplementationRef` and confirms
that the selected `ParameterModelRef` identifies the same class.

`viper.run(train)` starts the [process-startup contract](PROCESS_STARTUP.md).
The installed `viper run` command reaches the same coordinator when a user or
agent executes a complete plan.

## Execution

The controlled child performs this sequence:

```text
load the frozen stage spec
-> verify callable and parameter-model bytes
-> validate params into the selected project class
-> import the selected top-level callable
-> confirm its decorator metadata
-> construct StageContext with the typed parameter object
-> invoke the callable once
-> record the completed invocation
```

The callable receives validated parameters directly. The same context supplies
the materialized input paths and writable artifact paths selected for that
attempt.

## Persisted evidence

`ResolvedBaseSpec` stores a `StageInvocationReceipt` containing:

```python
class StageInvocationReceipt(ProtocolModel):
    implementation: StageImplementationRef
    parameter_model: ParameterModelRef
    parameter_digest: Sha256
    context_digest: Sha256
    started_at: AwareDatetime
    completed_at: AwareDatetime
    outcome: Literal["succeeded", "failed"]
```

The canonical context replaces each absolute workspace path with its logical
input or artifact path before hashing. Absolute paths exist only in the runtime
`StageContext`.

## Verification

| Check | Rule |
|---|---|
| `stage.implementation` | The receipt identifies the callable frozen by the stage spec and run source. |
| `stage.decorator` | The callable's decorator kind and parameter-model class agree with the frozen stage. |
| `parameter_model.identity` | The receipt identifies the frozen parameter model. |
| `parameter.value` | The delivered parameter digest equals the canonical digest of `stage.params`. |
| `stage.context` | The receipt context digest equals the binding reconstructed from the resolved inputs and artifacts. |
| `stage.outcome` | A successful resolved stage has one successful invocation receipt. |

These checks establish typed delivery to the callable. Project tests establish
how the callable uses each field while producing its scientific result.

## Propagation

| Surface | Required change |
|---|---|
| Protocol | Add `StageImplementationRef` and `StageInvocationReceipt`; replace `BaseSpec.script` on parameterized stages. |
| Decorators | Add one decorator for each stage kind and expose its frozen metadata. |
| Authoring | Resolve the top-level callable and freeze its exact identity. |
| Runtime | Add typed contexts and invoke the callable with the validated project parameter object. |
| Persistence | Store the canonical parameter and context digests in the resolved stage. |
| Verification | Apply the six stage-invocation checks. |
| Tests | Replace constant fixture scripts with callables that assert typed parameters and declared paths. |
| Documentation | Show direct Python execution and the whole-plan CLI adapter. |

## Acceptance case

`TinyTrainParameters.epochs` equals `3`. VIPER calls `train(context)` with
`context.params.epochs == 3`. The fixture writes the value `3` into a declared
artifact, and terminal verification accepts the invocation receipt.

The rejection case changes the delivered canonical mapping to `epochs = 2`
while preserving the frozen stage spec. `parameter.value` fails.

## Implementation order

1. Add the implementation-reference, context, and invocation-receipt models.
2. Add the stage decorators and authoring-time callable resolution.
3. Add callable loading and typed context construction.
4. Route every parameterized stage through the callable interface.
5. Add verifier rules and acceptance coverage.
6. Remove the script-path entrypoint after examples migrate.
