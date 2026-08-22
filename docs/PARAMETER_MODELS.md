# Project parameter models

A VIPER stage stores its parameters as a versioned JSON mapping. The project
defines the fields and validation rules for that mapping with a Pydantic
subclass.

## Define a class

Place the class in any Python file tracked by the project repository. The
class must appear at module scope and subclass the core parameter type for its
stage.

```python
from pydantic import Field, model_validator

from viper.protocol import TrainParams


class TransformerTrainParameters(TrainParams):
    epochs: int = Field(gt=0)
    batch_size: int = Field(gt=0)
    learning_rate: float = Field(gt=0)
    warmup_epochs: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_warmup(self) -> "TransformerTrainParameters":
        """Keep warmup within the selected training schedule."""
        if self.warmup_epochs >= self.epochs:
            raise ValueError("warmup_epochs must be smaller than epochs")
        return self
```

Available core bases:

| Stage | Base class |
| --- | --- |
| Build | `BuildParams` |
| Embed | `EmbedParams` |
| Train | `TrainParams` |
| Evaluate | `EvaluateParams` |

## Bind the class

Each internal stage spec includes a `parameter_model` reference.

```yaml
kind: train
script: project/training/fit.py
parameter_model:
  path: project/parameters/transformer.py
  symbol: TransformerTrainParameters
  sha256: 76239c61bfba46604579e47f932b92f5ad8c1ca33e2240bab2b4dbc3cabdcabe
  bytes: 577
params:
  schema_version: 1
  epochs: 20
  batch_size: 64
  learning_rate: 0.0003
  warmup_epochs: 2
```

`path` is relative to the repository root. `RunSpec.source` supplies the
repository and commit. The path, symbol, digest, and byte count identify the
exact class selected by the stage.

## Enforcement

| Operation | Check |
| --- | --- |
| Freeze | Local class bytes match the selected source commit; the class accepts the parameters |
| Preflight | Class identity and parameter validity receive separate check results |
| Execute | A dedicated worker validates the parameters before the stage process starts |
| Verify | Source bytes match the frozen identity and define the selected top-level class |

The worker imports project code inside a separate process. The trusted-local
backend gives that process the same repository and environment access as the
stage command. OCI isolation will apply the same parameter-model interface
inside the release execution boundary.

Validation uses strict Pydantic types. The class output must equal the frozen
JSON mapping exactly. Include every effective default in `params`; this keeps
the plan and the values received by project code identical.
