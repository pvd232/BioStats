# VIPER project briefing

The next release action is to add the selected license and author metadata,
publish the validated `0.1.0a1` files to TestPyPI, and repeat the installed-package
acceptance test from that registry.

## Why VIPER exists

VIPER gives a machine-learning experiment an executable contract. The contract
fixes the source, inputs, stage definitions, environment, and run-wide
reproducibility controls before execution. VIPER then records what each stage
used and produced. Verification follows those stored relationships from the
terminal run back to the frozen plan.

The frozen-plan and verification chain gives a human or an agent a bounded way
to change experimental code while preserving the evidence needed to inspect
the result. Data-use roles also prevent evaluation and benchmark inputs from
entering a training stage through a valid plan.

## How one run moves through the system

```text
project source + experiment decisions
                  |
                  v
           frozen run plan
                  |
                  v
        complete-plan preflight
                  |
                  v
       ordered stage invocations
                  |
                  v
   immutable attempt and stage files
                  |
                  v
         terminal verification
                  |
                  v
    optional benchmark confirmation
```

The frozen plan identifies exact project-owned callables and parameter classes.
The runner constructs a typed stage context and launches each callable in a
controlled child process. The child records the realized CPU or CUDA runtime,
the applied reproducibility controls, and the files produced by the stage. The
runner publishes those files into content-addressed snapshots and writes one
canonical attempt document. The verifier retrieves each referenced file,
checks its byte identity, and checks every declared relationship.

## Verified current position

The release candidate has crossed its implementation and deployment gates.
The repository marks the parameter, stage-invocation, startup, HTTP, metric,
artifact, attempt, benchmark, and cloud contracts as implemented. The package
release contract remains approved pending registry publication.

The exact candidate passed the complete repository suite under Python 3.14.6:
218 tests passed, six hardware-gated tests were skipped, and 33 subtests passed.
The same commit passed GitHub Actions under Python 3.11 through 3.14. Clean
environments for all four Python versions imported the built wheel from
`site-packages` and passed the public-interface checks.

The installed wheel also completed the generated acquisition run, the
five-stage candidate run, an independent benchmark confirmation, and terminal
verification outside the source checkout. A pre-provisioned GCE instance with
an NVIDIA L4 then ran the same wheel, passed the live CUDA startup checks, and
completed the generated project. The ephemeral VM and its 500 GB SSD were
deleted after the gate; the approved machine image remains available. The
[release-candidate report](releases/0.1.0a1.md) records the exact commit,
distribution digests, commands, environments, and results.

The release process is currently idle. The validated wheel and source archive
remain local release-candidate files.

## Remaining publication gate

Public publication requires the repository owner to supply four values or
authorizations in this order:

1. Add the selected package license and confirmed author metadata. Rebuild the
   distributions because those files change package metadata.
2. Supply TestPyPI credentials. Publish the rebuilt files and rerun the
   generated-project acceptance test from the TestPyPI installation.
3. Authorize publication of those exact files to PyPI. Repeat the installed
   package checks from PyPI.
4. Supply the signing identity. Create and push the signed `v0.1.0a1` tag on the
   validated release commit.

The [publication checklist](PUBLICATION_TODO.md) owns the detailed release
sequence. Completing that sequence converts the validated deployment candidate
into an independently installable public alpha.
