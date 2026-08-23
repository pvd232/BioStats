# Package release

## Status

Source and wheel builds, CI, installed-wheel capability checks, and the public
API inventory are implemented. The complete distribution gate is approved for
VIPER 0.1.

## Required claim

Installing `viper-provenance==0.1.0a1` provides the documented Python API and
CLI. A user can create or open a project, execute a decorated stage through
ordinary Python, execute the same frozen plan through the installed command,
and receive equivalent verified results outside the source checkout.

## Current gap

The package builds and passes installed-wheel smoke checks. The release metadata
still needs its final license, authors, project URLs, and pre-release version.
Candidate-wheel execution of the complete user-project path and TestPyPI
publication remain pending.

## Public surface

Release freezes the import names listed in
[`PUBLIC_API.md`](../PUBLIC_API.md), the CLI commands, JSON result schemas,
stable error codes, and capability-discovery output. Every documented name must
exist in the installed wheel.

The public project interface includes the stage decorators, typed stage
contexts, and `viper.run(stage_callable)`. The CLI delegates execution to the
same application coordinator.

## Project scaffold

`viper init PATH --package PROJECT_PACKAGE` creates a small runnable project:

```text
PATH/
├── pyproject.toml
├── experiments/
├── benchmarks/
├── src/<project_package>/
│   ├── stages/
│   ├── metrics/
│   └── artifact_loaders/
└── tests/
```

The generated layout is an example. VIPER accepts every project implementation
through repository-relative paths stored in its specs. The protocol remains
source-layout agnostic.

The generated project must freeze, preflight, execute, and verify one complete
run as generated.

`PATH` must be absent or empty. The command validates every requested path and
package name before writing the first file. An occupied path returns a typed
conflict failure and preserves its contents.

## Distribution gate

The release candidate must satisfy each check:

| Check | Required result |
|---|---|
| Public imports | Every name in `PUBLIC_API.md` imports from the installed wheel. |
| CLI | Every command returns documented human output, JSON, and exit status. |
| Python execution | The generated project's decorated stage executes through `python train.py` and returns a verified result. |
| Metadata | License, authors, URLs, classifiers, and version are complete. |
| Builds | Source distribution and wheel build while generated metadata remains untracked. |
| Wheel acceptance | The generated project passes the complete local acceptance path in a clean environment. |
| Cloud acceptance | The installed wheel passes the advertised live GCE smoke profile. |
| TestPyPI | The candidate installs from TestPyPI and repeats the wheel acceptance path. |
| CI | The exact release commit passes every supported Python version. |
| Release | The signed tag and PyPI files match the validated distributions. |

The Python Packaging User Guide documents the standard build, TestPyPI, and
publication sequence: [Building and
publishing](https://packaging.python.org/en/latest/guides/section-build-and-publish/).

## Propagation

| Surface | Required change |
|---|---|
| Metadata | Add the approved license, authors, project URLs, classifiers, and `0.1.0a1` version. |
| Public API | Freeze imports, result schemas, errors, exit statuses, and capability discovery. |
| Python execution | Export stage decorators, typed contexts, and `viper.run(stage_callable)`. |
| CLI | Implement `viper init` and route every command through the application API. |
| Template | Add one maintained runnable project template. |
| CI | Build, install, and exercise the wheel from outside the checkout. |
| Release | Publish to TestPyPI, validate, tag, and publish the exact artifacts to PyPI. |

## Acceptance case

A clean environment installs the candidate wheel. The command
`viper init tiny-project --package tiny_project` creates the example. The
example freezes and preflights one plan. `python train.py` executes its decorated
stage through `viper.run(stage_callable)`. `viper run` executes the complete
plan through the same coordinator and emits valid JSON. Both results pass
terminal verification. The same wheel completes the live GCE smoke case.

Deleting one documented public import causes the installed-wheel test to fail.

## Implementation order

1. Complete the release-gated contracts in this directory.
2. Freeze public imports, errors, JSON, capabilities, and CLI syntax.
3. Add the project scaffold and acceptance template.
4. Complete package metadata and set version `0.1.0a1`.
5. Build and test the wheel in clean local environments.
6. Repeat the acceptance path from TestPyPI.
7. Tag and publish the exact validated distributions.
