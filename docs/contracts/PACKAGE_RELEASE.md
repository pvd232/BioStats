# Package release

## Status

The tiered-validation candidate passes the local repository, distribution,
installed-wheel, external generated-project, and redesigned Python 3.11–3.14
CI gates. Live GCE acceptance remains pending.

## Required claim

Installing `viper-provenance==0.1.0a1` provides the documented Python API and
CLI. A user can create or open a project, execute a decorated stage through
ordinary Python, execute the same frozen plan through the installed command,
and receive equivalent verified results outside the source checkout.

## Current gap

The exact local candidate distributions and their SHA-256 digests are recorded
in the [release-candidate report](../releases/0.1.0a1.md). The generated source
completed the acquisition, five-stage candidate, and benchmark-confirmation
path from the installed wheel. The exact candidate passed the four-version CI
gate. Release requires a GCE result for the exact candidate, owner-selected
license and author metadata, trusted-publisher registration, production
environment approval, and the release-tag signing identity.

## Public surface

Release freezes the import names listed in
[`PUBLIC_API.md`](../PUBLIC_API.md), the CLI commands, JSON result schemas,
stable error codes, and capability-discovery output. Every documented name must
exist in the installed wheel.

The public project interface includes the stage decorators, HTTP transport
decorator, typed contexts, and `viper.run(stage_callable)`. The CLI delegates
execution to the same application coordinator.

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

The generated implementation files must freeze, preflight, execute, and verify
in their generated form. The acceptance driver initializes Git before it
authors the source-bound experiment, benchmark, stage, and run documents.

The runnable example has two plans. The acquisition plan publishes the fixed
evaluation dataset and split, then writes their promoted artifact pointers.
The candidate plan contains the ordered `download`, `build`, `embed`, `train`,
and `evaluate` stages. Its evaluation stage selects the promoted evaluation
inputs and the parameters produced by its training stage. The benchmark
executes one independent confirmation of the candidate plan.

This sequence preserves the data-use contract. The training stages consume
training-role inputs. The evaluation stage receives the evaluation and
benchmark inputs published by the acquisition plan.

`PATH` must be absent or empty. The command validates every requested path and
package name before writing the first file. An occupied path returns a typed
conflict failure and preserves its contents.

## Distribution gate

The release candidate must satisfy each check:

| Check | Required result |
|---|---|
| Public imports | Every name in `PUBLIC_API.md` imports from the installed wheel. |
| Inline types | The installed `viper` package contains `py.typed`, and type checkers use its distributed annotations. |
| CLI | Every command returns documented human output, JSON, and exit status. |
| Python execution | The generated project's decorated stage executes through `python train.py` and returns a verified result. |
| Metadata | License, authors, URLs, classifiers, and version are complete. |
| Builds | Source distribution and wheel build while generated metadata remains untracked. |
| Wheel acceptance | The generated project passes the complete local acceptance path in a clean environment. |
| Cloud acceptance | The installed wheel passes the advertised live GCE smoke profile. |
| TestPyPI | The candidate installs from TestPyPI and repeats the wheel acceptance path. |
| CI | The exact release commit passes every supported Python version. |
| Release | The signed tag verifies against the release owner identity, and the PyPI files match the validated distributions. |

The CI fast job runs lint, formatting, type checking, unit tests, and contract
tests under Python 3.14. Its success starts the integration, release-candidate,
and compatibility jobs. Python 3.14 runs every host-independent test. Python
3.11–3.13 run the unit and contract tiers, build both distributions, and import
the installed wheel.

The Python Packaging User Guide defines the package metadata fields and
recommends SPDX license expressions with distributed license files:
[Writing `pyproject.toml`](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/).
Its publication guide recommends PyPI Trusted Publishing because each upload
uses a short-lived, project-scoped credential:
[Publishing with GitHub Actions](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/).

## Propagation

| Surface | Required change |
|---|---|
| Metadata | Add the approved license, authors, project URLs, classifiers, and `0.1.0a1` version. |
| Public API | Freeze imports, result schemas, errors, exit statuses, and capability discovery. |
| Inline types | Package `viper/py.typed` and verify it from the installed wheel. |
| Python execution | Export stage decorators, typed contexts, and `viper.run(stage_callable)`. |
| CLI | Implement `viper init` and route every command through the application API. |
| Template | Add one maintained runnable project template. |
| CI | Build, install, and exercise the wheel from outside the checkout. |
| Release | Push the signed version tag, publish its files to TestPyPI, validate those indexed files, approve the protected `pypi` environment, and publish the same files to PyPI. |

Tag signing is an owner-supplied release prerequisite. The release report
records the signing identity and the successful signature-verification command.

## Acceptance case

A clean environment installs the candidate wheel. The command
`viper init tiny-project --package tiny_project` creates the example. The
example executes its acquisition plan and promotes the evaluation inputs. It
then freezes and preflights the candidate plan. `python train.py` executes its
decorated stage through `viper.run(stage_callable)`. `viper run` executes the
complete candidate plan through the same coordinator and emits valid JSON. The
benchmark confirmation passes. The same wheel completes the live GCE smoke
case.

Deleting one documented public import causes the installed-wheel test to fail.

## Implementation order

1. Complete the release-gated contracts in this directory.
2. Freeze public imports, errors, JSON, capabilities, and CLI syntax.
3. Add the project scaffold and acceptance template.
4. Complete package metadata and set version `0.1.0a1`.
5. Build and test the wheel in clean local environments.
6. Register `.github/workflows/release.yml` as the trusted publisher for the
   `testpypi` and `pypi` GitHub environments.
7. Create and push the signed version tag. The workflow verifies GitHub's tag
   signature result before building.
8. Publish the workflow's files to TestPyPI and repeat the installed-package
   acceptance path.
9. Approve the protected `pypi` environment and publish the same stored files
   to PyPI.
