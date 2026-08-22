# MANTRA artifact provenance protocol

This directory contains the first executable slice of the MANTRA provenance
protocol. `*spec.yaml` files declare an artifact-producing
operation. MANTRA writes a `*.resolved.spec.yaml` only after the operation has
produced, hashed, and published its one output artifact.

## Two identities

MANTRA records two independent SHA-256 identities:

- `ResolvedFileRef.sha256` identifies exact artifact bytes.
- `ResolvedSpecRef.sha256` identifies the canonical semantic serialization of
  the resolved spec that produced an internal input.

The first verifies content. The second selects its provenance. Both are needed
because identical bytes may be produced by different executions.

## Model relationships

```text
BaseSpec
├── DownloadSpec
├── BuildSpec
├── EmbedSpec
└── TrainSpec

BaseResolvedSpec
├── ResolvedDownloadSpec
├── ResolvedBuildSpec
├── ResolvedEmbedSpec
└── ResolvedTrainSpec

ResolvedInput
├── ExternalResolvedInput
│   └── artifact: ResolvedFileRef
└── ProducedResolvedInput
    ├── artifact: ResolvedFileRef
    └── producer: ResolvedSpecRef
```

`ExternalResolvedInput` is the explicit backward-traversal boundary. A
download spec therefore replaces the earlier `terminal: bool` with a
structural invariant: every resolved download input must be external.

## Record identity

Resolved specs may remain readable YAML files, but their semantic identities
are calculated from a centralized canonical JSON representation:

```text
resolved_spec_sha256 = SHA256(canonical_json(resolved_spec))
```

This keeps YAML formatting, comments, and key ordering out of provenance
identity. The original YAML source is separately identified by
`ResolvedSpecSource.raw_sha256`.

## Golden chain

The fixtures in `examples/provenance` describe the first two-node chain:

```text
ResolvedBuildSpec
    └── raw_data.producer → ResolvedDownloadSpec
                                  └── source → external boundary
```

The build input repeats the download output's SHA-256 and byte count, while its
`producer.sha256` equals the canonical identity of the resolved download spec.

## Current scope

The current package validates protocol claims but performs no external I/O
beyond loading YAML. Hashing actual artifacts, Git snapshot verification,
execution, publication, atomic record writing, graph traversal, and replay are
the next implementation layers.

Run the model tests with:

```text
.venv/bin/python -m unittest discover -v
```
