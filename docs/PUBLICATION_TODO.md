# VIPER provenance publication checklist

This checklist tracks the work required to publish a usable provenance library
and runner. A checked item has implementation and automated validation in this
repository.

## Protocol foundation

- [x] Define requested stage specs, resolved stage records, run attempts, and
  terminal resolved runs.
- [x] Verify referenced file identity, stage order, input lineage, artifact
  completeness, runtime controls, and benchmark confirmation.
- [x] Capture and restore model resume state for zero-worker and
  multiprocess stateful data loaders.
- [x] Provide versioned, JSON-shaped stage parameter bases that project models
  can specialize without modifying this package.
- [x] Store evaluation identity, metric IDs, and split inputs directly on
  `EvaluateSpec`.
- [x] Bind benchmarks to an explicit evaluation ID.
- [x] Reserve `predictions` while allowing its declared artifact format and
  loader to be project-defined.
- [x] Bind each metric ID to its role, parameters, and exact
  repository-relative implementation path.
- [x] Resolve stage scripts, metric implementations, and artifact loaders from
  exact repository-relative paths without prescribing a user source tree.
- [x] Place repository maintenance utilities under `tools/`.
- [x] Use `spec.yaml` and `resolved.yaml` inside run and stage identity
  directories.
- [x] Define data-use roles and the permitted flows among training, validation,
  evaluation, and benchmark inputs. Enforce those rules while validating a run
  plan and before materializing stage inputs.

## Package and test quality

- [x] Keep the installable `viper` package limited to runtime Python modules;
  place active documents, historical material, and examples at repository level.
- [x] Consolidate canonical record encoding and duplicate-key-safe YAML parsing
  in `serialization.py`.
- [x] Name single-stage process invocation explicitly as `stage_execution.py`.
- [x] Remove test-to-test imports and centralize shared fixtures.
- [x] Document every active module, class, function, method, and test.
- [x] Enforce code documentation with Ruff pydocstyle rules.
- [x] Test each metric implementation and artifact loader.
- [x] Add one execution acceptance test that invokes a real stage entrypoint and
  verifies the files it publishes.
- [x] Remove tracked generated package metadata.

## Application foundation

Complete this interface before implementing the run-level loop. It prevents the
CLI, Python callers, and agent integrations from acquiring separate behavior.

- [ ] Define machine-readable success and failure records. Each failure must
  identify the failed operation, stable error code, affected record or path,
  and concrete cause.
- [ ] Add a small Python application API whose functions accept validated
  request records and return validated result records.
- [ ] Route every CLI command through the application API and add JSON output
  without removing concise human output.
- [ ] Add schema discovery for every authored and resolved record accepted by
  the installed package.
- [ ] Add capability discovery that reports the installed protocol version,
  supported stage kinds, commands, environment types, and storage types.

## Runner

### Implemented operations

- [x] Implement plan authoring for experiment, variant, run, and stage files.
- [x] Invoke one stage entrypoint with the exact stage spec selected by its
  `RunStageRef`.
- [x] Add the installed `viper` command for authoring, stage execution, and
  verification.
- [x] Run artifact loaders only for explicitly trusted source repositories.

### Remaining implementation order

Implement the remaining runner work in the following order. Each unfinished
step depends on the completed steps above it.

- [ ] Define the runner interfaces that retrieve immutable files, materialize
  stage inputs, and publish immutable files. Define the attempt workspace and
  every path the runner may write.
- [ ] Preflight the complete `RunSpec`: retrieve and verify every authored
  record needed before execution, resolve each stage environment, check input
  availability, and validate every planned output path.
- [ ] Materialize `StoredInputRef` and `FutureInputRef` values from verified
  artifacts at the paths declared by the consuming stage.
- [ ] Apply `RunSpec.reproducibility` to every stage process and select the
  shared `RunSpec.environment` or the stage's declared environment override.
- [ ] Invoke the existing single-stage operation for every stage in
  `RunSpec.stages`, in order.
- [ ] Construct the concrete `ResolvedSpec` from the authored stage spec,
  verified inputs, realized environment, execution context, command, output
  files, and completion time.
- [ ] Publish one stage-result snapshot containing the `ResolvedSpec` and every
  file belonging to each declared artifact. Record the resulting
  `ResolvedStageRef` in the active `RunAttempt`.
- [ ] Invoke each declared metric implementation with its typed context and
  write its `Measurement` records.
- [ ] Close the attempt, then publish its measurement files, standard-output
  log, and standard-error log. Record their exact references in `RunAttempt`.
- [ ] Write the terminal run `resolved.yaml`, retain every attempt, and set
  `successful_attempt_id` only when one attempt completed successfully.
- [ ] Add an acceptance test that executes a complete multi-stage run, verifies
  the terminal `resolved.yaml`, and rejects a tampered stage artifact.

## Agent operations

- [ ] Add `preflight`, `status`, `plan diff`, `lineage`, and `compare runs`
  operations with validated JSON results.
- [ ] Add an optional agent-protocol adapter only after the Python API and JSON
  CLI expose the complete runner and verifier operations.

## Internal modularization

- [ ] Preserve `viper.records` and `viper.verifier` as public import paths.
- [ ] After the complete runner acceptance test passes, divide `records.py`
  into internal modules for shared types, plans, stages, artifacts, runs,
  measurements, and benchmarks. Re-export the supported names from
  `viper.records`.
- [ ] Divide verifier internals by the records they verify: files, plans,
  stages, runs, promoted artifacts, and benchmarks. Keep the existing public
  verification functions available from `viper.verifier`.

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
