# Process startup

## Status

Runner-launched stages already receive process-start environment variables and
run-wide library controls. A shared startup contract for the Python and CLI
interfaces is approved for VIPER 0.1.

## Required claim

Every VIPER-governed stage callable executes in a child process whose start-time
environment and runtime controls derive from the frozen `RunSpec`.

## Current gap

[`execute_stage_process()`](../../viper/stage_execution.py) derives environment
variables through `process_environment()` and supplies them when launching
`viper.stage_worker`. [`stage_worker.main()`](../../viper/stage_worker.py) then
applies library controls before executing the project script.

This path supports runner-launched scripts. The public package lacks the
decorated callable and `viper.run(stage_callable)` interfaces. The worker also
records only the local CPU runtime.

## Project interface

The project declares one stage callable:

```python
import viper


@viper.train_stage(parameter_model=TrainParameters)
def train(context: viper.StageContext[TrainParameters]) -> None:
    ...


if __name__ == "__main__":
    viper.run(train)
```

The user starts the program with ordinary Python execution:

```text
python train.py --run <run-spec> --stage train
```

During that initial invocation, `viper.run(stage_callable)` reads `--run` and
`--stage`, confirms that the callable represents the selected frozen stage, and
submits the run to the application coordinator. The coordinator follows the
complete order stored in `RunSpec.stages`. The stage argument binds the launched
callable to its stage specification. Each remaining stage is loaded from its
own frozen implementation reference.

The installed command supplies a whole-plan adapter:

```text
viper run <run-spec>
```

Both interfaces call the same application coordinator.

The Python form preserves a project's normal executable module. The CLI form
gives agents, CI jobs, and automation a generic complete-plan command.

## Startup sequence

The coordinator performs this sequence for each stage:

```text
load and verify RunSpec and selected stage spec
-> validate the decorated callable and parameter model
-> derive the start-time environment from RunSpec.reproducibility
-> launch one child process with that environment
-> apply library-level controls inside the child
-> observe the active host and numerical runtime
-> construct the typed StageContext
-> invoke the decorated callable
-> write the invocation and runtime evidence
-> publish and verify the stage result
```

The start-time environment contains every control that the operating system,
Python interpreter, or numerical runtime consumes during process startup. The
current mapping includes `PYTHONHASHSEED`, `OMP_NUM_THREADS`,
`MKL_NUM_THREADS`, and the selected `CUBLAS_WORKSPACE_CONFIG`.

Python uses an integer `PYTHONHASHSEED` to fix hash randomization for the
process: [Python command-line and environment documentation](https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED).

The child then applies the supported Python, NumPy, PyTorch, CUDA,
determinism, precision, and thread controls through
[`apply_reproducibility()`](../../viper/runtime.py).

## Direct-script boundary

Ordinary Python execution imports the project module before its `__main__`
block calls `viper.run(stage_callable)`. A conforming stage module limits its
import phase to imports, definitions, and decorator registration. Data access,
accelerator initialization, model construction, and training occur inside the
decorated callable.

The coordinator launches that callable in the controlled child process. The
child receives `VIPER_CONTEXT_PATH`, which identifies one versioned context
document containing the run, attempt, stage, and path bindings. Absence of
`VIPER_CONTEXT_PATH` selects coordination mode. A coordinator-launched child
validates the context document and invokes the callable exactly once.

VIPER's execution claim begins with the controlled child process. The initial
module import performed by `python train.py` belongs to trusted project setup in
0.1. The installed `viper run` command starts coordination before importing a
project stage module.

## Persisted evidence

`ResolvedBaseSpec` stores the stage invocation receipt defined by
[Stage invocation](STAGE_INVOCATION.md). The resolved stage also stores the
`ExecutionContext` observed inside the child process.

The receipt binds the callable identity and typed context to one process
outcome. `ExecutionContext` records the applied controls and realized runtime.

## Verification

| Check | Rule |
|---|---|
| `startup.plan` | The child context identifies the frozen run and selected stage. |
| `startup.environment` | The child receives the canonical start-time environment derived from the run controls. |
| `startup.callable` | The child invokes the exact decorated callable frozen by the stage spec. |
| `startup.context` | The callable receives the typed context bound to the selected stage. |
| `startup.runtime` | The resolved stage contains the runtime context observed inside the child. |
| `startup.outcome` | One successful resolved stage contains one successful child-process receipt. |

## Propagation

| Surface | Required change |
|---|---|
| Public package | Export stage decorators, typed contexts, and `viper.run`. |
| Application | Expose one host-neutral complete-run coordinator. |
| Worker | Load the frozen callable and invoke it with the typed context. |
| Stage execution | Use the same child-process startup path for Python and CLI callers. |
| Persistence | Store the startup, invocation, and runtime evidence on the resolved stage. |
| Verification | Apply the six startup checks above. |
| Tests | Exercise direct Python execution, CLI execution, start-time controls, one invocation, and import-phase violations represented by fixture modules. |

## Acceptance case

`TrainSpec.params.epochs` equals `3`. The user runs `python train.py` with the
frozen run path and stage ID. The coordinator starts a controlled child, the
decorated function receives `TrainParameters(epochs=3)`, and the resolved stage
records the child environment, callable identity, context digest, and successful
outcome.

The rejection case changes the child context to another stage ID. The
`startup.plan` check rejects the invocation before the project callable runs.

## Implementation order

1. Add the stage decorators and callable metadata.
2. Add the direct `viper.run(stage_callable)` adapter.
3. Generalize the application coordinator and CLI command to `run`.
4. Invoke every callable through the controlled child-process path.
5. Persist and verify the startup evidence.
6. Add direct-Python and CLI acceptance tests for the same frozen run.
