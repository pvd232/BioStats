# Archive

This directory preserves superseded VIPER and MANTRA provenance designs. These
files document earlier decisions and migrations; they do not define the active
package contract.

## Contents

| File | Historical role |
|---|---|
| [ProvenanceS1.md](ProvenanceS1.md) | Version 1 provenance protocol |
| [ProvenanceS1_v2.md](ProvenanceS1_v2.md) | Version 2 provenance protocol |
| [PROVENANCE_PROTOCOL.md](PROVENANCE_PROTOCOL.md) | Earlier artifact-manifest protocol |
| [2026-08-17-stage-1-handoff.md](2026-08-17-stage-1-handoff.md) | Stage 1 implementation handoff |
| [models.py](models.py) | Initial Pydantic record implementation |
| [models_v2.py](models_v2.py) | Second record-model iteration |
| [models_v3.py](models_v3.py) | Third record-model iteration |
| [models_v3_draft.py](models_v3_draft.py) | Draft preceding the third iteration |
| [legacy-package-readme.md](legacy-package-readme.md) | README for the earlier model package |
| [E2E_ML_training.md](E2E_ML_training.md) | Earlier ML training execution paper |
| [E2E_ML_GPU_resident_full_batch.md](E2E_ML_GPU_resident_full_batch.md) | Earlier full-batch GPU paper |

## Active contract

The active protocol is [ProvenanceS1_v3.md](../docs/ProvenanceS1_v3.md). The
current implementation is the [viper package](../viper/), and its public
overview is the [repository README](../README.md).
