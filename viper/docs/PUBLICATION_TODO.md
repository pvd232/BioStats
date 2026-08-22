# MANTRA provenance publication checklist

This checklist tracks the work required to publish a usable provenance library
and runner. A checked item has implementation and automated validation in this
repository.

## Protocol foundation

- [x] Define requested stage specs, resolved stage records, run attempts, and
  terminal resolved runs.
- [x] Verify referenced file identity, stage order, input lineage, artifact
  completeness, runtime controls, and benchmark confirmation.
- [x] Capture and restore model continuation state for zero-worker and
  multiprocess stateful data loaders.
- [x] Provide versioned, JSON-shaped stage parameter bases that project models
  can specialize without modifying this package.
- [x] Store evaluation identity, metric IDs, and split inputs directly on
  `EvaluateSpec`.
- [x] Bind benchmarks to an explicit evaluation ID.
- [x] Store perturbation-expression predictions as H5AD with one validated
  loader and schema.
- [x] Bind each metric ID to its role, parameters, and canonical implementation.
- [x] Place metric implementations under
  `src/mantra/metrics/<role>/<metric_id>/compute.py`.
- [x] Place repository maintenance utilities under `tools/`.
- [x] Use `spec.yaml` and `resolved.yaml` inside run and stage identity
  directories.

## Package and test quality

- [x] Remove test-to-test imports and centralize shared fixtures.
- [x] Document every active module, class, function, method, and test.
- [x] Enforce code documentation with Ruff pydocstyle rules.
- [x] Test each metric implementation and artifact loader.
- [x] Add one execution acceptance test that invokes a real stage entrypoint and
  verifies the files it publishes.
- [x] Remove tracked generated package metadata.

## Runner

- [x] Implement plan authoring for experiment, variant, run, and stage files.
- [ ] Materialize stored and same-run inputs from verified artifacts.
- [ ] Apply the run-wide environment and reproducibility controls.
- [x] Invoke each stage entrypoint with its exact stage spec.
- [ ] Publish each stage-result snapshot with its resolved stage record and
  artifacts.
- [ ] Publish attempt measurements and logs after the attempt closes.
- [ ] Write the terminal `resolved.yaml` and select the successful attempt.
- [x] Add the installed `mantra` command for authoring, stage execution, and
  verification.
- [x] Run artifact loaders only for explicitly trusted source repositories.

## Distribution

- [ ] Add the owner-approved license and author metadata.
- [x] Add version policy and release notes.
- [x] Build the source distribution and wheel.
- [x] Run metadata checks on both distributions.
- [x] Install the wheel into an isolated target and run an import smoke test
  against the declared dependencies in the `mantra` environment.
- [x] Add continuous integration for Ruff, Pyright, pytest, build, and installed
  wheel validation.
- [ ] Publish to TestPyPI with an owner-provided token and verify installation.
- [ ] Publish the approved release to PyPI.
