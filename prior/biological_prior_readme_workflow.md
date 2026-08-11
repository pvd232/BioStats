---
description: Build the canonical README for any biological prior used by the project.
---
// turbo-all

1.  **Define the Prior and README Contract**
    *   Create the canonical README for one biological prior or coherent prior family.
    *   State the biological phenomenon, organism, biological context, unit of observation, intended modeling role, repository location, and prior class.
    *   Distinguish the prior from a label, outcome, ground truth, or causal claim.
    *   Use this order: `# <Prior name>`; `## Prior identity`; `## Biological context`; `## From biological evidence to the file/API interface`; `## Source and artifact summary`; `## Source-to-prior transformation`; `## Derived artifact contract`; `## Exact file and API keys used`; one `### Input: <concrete identity>` per build-time input; `## Provenance and integrity`; `## Verification`; `## Interpretation limits and failure modes`.

2.  **Establish the Biological and Historical Context**
    *   Explain the entities, mechanisms, measurements, and relationships required to understand the prior.
    *   Include the relevant biological scale, time, disease, treatment, and environment.
    *   Identify values that are directly measured, curated, normalized, aggregated, imputed, inferred, or model-generated.
    *   Define zero, absence, non-detection, below-threshold, uncovered, unresolved, and missing states when present.
    *   Explain uncertainty, confidence, quality, and replicate semantics when applicable.
    *   Identify the responsible institution, resource, publication, platform, or model; explain its purpose and material version differences.
    *   Cite primary publications, official resource documentation, and authoritative specifications.
    *   State the biological assumptions supporting use as a prior and the interpretations the data does not support.

3.  **Connect Biology to the File and API Interface**
    *   Map the complete chain:

        ```text
        biological entity, relationship, or measurement
            -> authoritative host and source identity
            -> release, accession, query, or catalogue record
            -> acquired or registered representation
            -> exact fields, keys, columns, arrays, or operations
            -> transformation and alignment
            -> derived prior field or tensor
        ```

    *   Include this table:

        | Biological concept | Source/host | Source identity | Representation | Keys or fields used | Derived representation |
        | --- | --- | --- | --- | --- | --- |

    *   Distinguish acquisition-time APIs from build-time file access.
    *   Define host, version, accession, query, retrieval identity, checksum, local path, license, and source-set membership.
    *   Define applicable identifiers, ontologies, assemblies, coordinate conventions, versions, aliases, and mapping rules.
    *   Link every representation to its authoritative format or API specification.

4.  **Define the Artifacts and Source-to-Prior Transformation**
    *   Include this summary:

        | Artifact type | Files or endpoints | Biological role | Computational role |
        | --- | --- | --- | --- |

    *   Represent every source, manifest, cache, intermediate, output, build record, and diagnostic.
    *   Distinguish numerical inputs, identity references, provenance-only records, validation records, and outputs.
    *   Explain value-changing transformations: filtering, identifier or coordinate conversion, normalization, weighting, aggregation, thresholding, imputation, and inference.
    *   Give formulas, units, parameters, defaults, and ordering rules where required for an unambiguous implementation.
    *   Define handling of replicates, duplicates, conflicts, isoforms, contexts, and one-to-many mappings.

5.  **Define the Derived Artifact Contract**
    *   Enumerate every field, array, column, tensor, metadata object, and index.
    *   State shapes, shape relationships, dtypes, units, valid ranges, ordering, row and column identities, primary keys, and uniqueness expectations.
    *   Define sparse, dense, compressed, indexed, or chunked representation where applicable.
    *   Define the meanings of zero, null, `NaN`, masked, absent, uncovered, filtered, and unresolved values.
    *   Make every value traceable to its source, transformation, and build record.

6.  **Enumerate Every Concrete Input and Exact Key**
    *   Include this summary:

        | Input file or endpoint | Loader or client | File/API keys used |
        | --- | --- | --- |

    *   Enumerate exact keys, columns, attributes, nested paths, archive members, request and response fields, and access operations.
    *   Distinguish numerical, identity, alignment, filtering, provenance, and validation uses.
    *   Give every concrete build-time input exactly one dedicated section:

        `### Input: <repository-relative path, accession, or endpoint>`

    *   Include this table in every dedicated section:

        | Key, field, column, or operation | Location/type | Biological meaning | Usage and access pattern |
        | --- | --- | --- | --- |

    *   Add units, conventions, required status, derived output, and examples where useful.
    *   A directory, wildcard, provider, or source family does not replace concrete input identities.
    *   Inputs with identical schemas remain distinct when their provenance or biological role differs.
    *   Identify registered artifacts that the build does not open.

7.  **Define Provenance, Verification, and Interpretation Limits**
    *   Define version, accession, host, retrieval identity, checksum, path, license, source set, build configuration, output identity, and diagnostics.
    *   Make every derived artifact traceable to its inputs and transformation declaration.
    *   Include validation commands and the schema, shape, ordering, missingness, provenance, and reproducibility assertions they enforce.
    *   Cover drift, context mismatch, coordinate errors, batch and selection bias, leakage, absence or missingness errors, inferred values mistaken for measurements, and association mistaken for causation.
    *   Pair detectable risks with a field, provenance record, diagnostic, or test.

8.  **Apply Formatting and File-Path Etiquette**
    *   Use one H1 and a consistent H2/H3 hierarchy.
    *   Place biological explanation before implementation detail.
    *   Use repository-relative links for repository files and authoritative HTTPS links for external sources.
    *   Use inline code for keys, fenced blocks for commands and structural paths, and warnings for interpretation hazards.
    *   Path-bearing table cells such as `Files`, `Input file`, `Artifact`, `Manifest`, and `YAML file` MUST use short functional Markdown labels with exact relative targets.
    *   Separate multiple links in one table cell with `<br>`.
    *   Use `[batch progress](diagnostics/REGULATORY_TRACK_CENSUS_PROGRESS.json)<br>[status page](diagnostics/REGULATORY_TRACK_CENSUS_STATUS.md)`, not bare full-path strings as table-cell prose.
    *   Keep exact paths in commands, file trees, input headings, schemas, and data-flow diagrams where structure matters.
    *   Validate exact link targets independently of compact display labels.
    *   Avoid process narration, progress commentary, parenthetical asides, and redundant restatements.

9.  **Enforce the Mandatory Validation Contract**
    *   Treat completeness as a pass/fail data contract.
    *   Use [the structural validator](validate_biological_prior_readme.py) for concrete-input coverage and local-link integrity.
    *   Use prior-specific tests for keys, shapes, ordering, and value semantics.

    **Concrete-input coverage**

    ```text
    expected_build_inputs = all concrete files, immutable objects, endpoints, or queries opened by the production build
    documented_input_sections = all dedicated README input headings
    documented_input_sections == expected_build_inputs

    documented_input_sections=<count>
    expected_build_inputs=<count>
    missing_inputs=0
    extra_inputs=0
    duplicate_input_sections=0
    ```

    *   Provenance and configuration files opened by the build count as inputs.
    *   Directories, wildcards, unresolved collections, duplicates, and non-input sections fail the contract.

    **Exact key, shape, and semantic agreement**

    ```text
    documented_keys=<count>
    production_keys=<count>
    undocumented_production_keys=0
    documented_unused_keys=0
    documented_shapes_checked=<count>
    prior_validation_status=pass
    ```

    *   Support every documented key with a production access and an actual input or authoritative schema.
    *   Document every production key contributing to the public data contract.
    *   Match shapes, dtypes, units, ordering, ranges, and missingness to tests or metadata.

    **Relative-link integrity**

    ```text
    markdown_links=<count>
    local_links=<count>
    external_links=<count>
    missing_local_targets=0
    unresolved_local_fragments=0
    ```

    *   Resolve local targets relative to the README and validate fragments.
    *   Reject missing targets, malformed paths, conflicting references, and repository-scope escapes.

    **Enforcement status**

    *   Report `PASS`, `FAIL`, or `NOT RUN` with actionable mismatches.
    *   A failing test or any nonzero mismatch count fails the contract.
    *   A skipped or unavailable check is `NOT RUN`; the README remains incomplete.

10.  **Apply the Relevant Modality Extension**
    *   Apply only clauses matching the prior.
    *   **Genomic/sequence**: organism, reference, assembly, coordinates, chromosome/strand, identifiers, alleles, windows, conversion, ambiguous bases.
    *   **Functional assays**: biosample, context, assay, replicate/control, units, normalization, intervals, aggregation, coverage, non-detection, zero, missingness.
    *   **Expression/single-cell**: counts, normalization, features, batch correction, identity, aggregation, ontologies, donor effects, sampling zeros, dropout, missingness.
    *   **Protein/structure/biochemistry**: identifiers, residues/chains, source, resolution/confidence, missing residues, units, conditions, partners, modifications, experiment versus prediction.
    *   **Networks/pathways**: nodes, edges, direction, sign, weight, evidence, confidence, duplicates, conflicts, disconnected nodes, aggregation.
    *   **Phenotype/clinical/population**: cohort, ancestry, ontology/codes, criteria, time, treatment, ascertainment, censoring, statistics, harmonization, overlap, privacy, generalizability.
    *   **Literature/knowledge bases**: version, records, evidence, curation/extraction, updates, conflicts, retractions, duplicates, confidence, publication bias.
    *   **Model-derived**: model/version, training scope, inputs/outputs, calibration, inference, uncertainty, unsupported domains, drift, leakage, stochasticity.

11.  **Complete the README Without Destructive Changes**
    *   Completion requires all Task 9 checks to pass.
    *   Inputs, sections, keys, links, shapes, provenance, artifacts, diagnostics, and tests must satisfy Task 9 and express one data contract.
    *   Do not delete source files, manifests, derived artifacts, diagnostics, tests, or provenance-bearing README content.
    *   No `rm`, no `git rm`, no `git clean`.
