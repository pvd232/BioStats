# VIPER contracts

This directory owns the implementation contracts that connect one VIPER claim
to its protocol fields, runtime operation, persisted evidence, verifier rule,
and acceptance test.

## Naming

Each filename names one contract subject. The `contracts/` directory supplies
the shared document class, so filenames omit a repeated `_CONTRACT` suffix.

Each contract uses one status:

| Status | Meaning |
|---|---|
| Implemented | Code and acceptance tests establish the required claim. |
| Approved | The design is approved for implementation. |
| Proposed | The design awaits review. |

## Contract index

| Contract | Status | Release gate |
|---|---|---|
| [Parameter models](PARAMETER_MODELS.md) | Implemented | Project parameter identity and validation |
| [Stage invocation](STAGE_INVOCATION.md) | Approved | Typed delivery of validated stage parameters and paths |
| [Process startup](PROCESS_STARTUP.md) | Approved | Run-wide controls applied before each stage callable executes |
| [HTTP retrieval](HTTP_RETRIEVAL.md) | Approved | Controlled delivery of verified HTTP response bytes |
| [Metric provenance](METRIC_PROVENANCE.md) | Approved | Exact metric dependencies, execution, and recomputation |
| [Artifact validation](ARTIFACT_VALIDATION.md) | Approved | File identity, loadability, and reserved semantic validation |
| [Attempt execution](ATTEMPT_EXECUTION.md) | Approved | Failed attempts, successive attempt IDs, and retry |
| [Benchmark execution](BENCHMARK_EXECUTION.md) | Approved | Independent confirmation produced from a frozen run plan |
| [Cloud execution](CLOUD_EXECUTION.md) | Approved | Execution on a pre-provisioned GCE instance |
| [Package release](PACKAGE_RELEASE.md) | Approved | Installed-distribution and publication acceptance |

The [publication roadmap](../PUBLICATION_TODO.md) orders these contracts. The
[protocol](../ProvenanceS1_v3.md) remains the authority for serialized VIPER
documents.
