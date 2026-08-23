# Project parameter models

## Status

Project parameter identity and validation are implemented. Typed delivery to
the stage callable is governed by [Stage invocation](STAGE_INVOCATION.md).

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
| Download | `DownloadParams` |
| Build | `BuildParams` |
| Embed | `EmbedParams` |
| Train | `TrainParams` |
| Evaluate | `EvaluateParams` |

## Bind the class

Every stage spec includes a `parameter_model` reference. The approved 0.1
stage-invocation form binds that model beside the callable that receives it:

```yaml
kind: train
implementation:
  path: project/training/fit.py
  symbol: train
  sha256: 4d93d67ed414c12b8bf130e915d417e801577cc1f59b163060728151d08ad9a5
  bytes: 2468
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

Current pre-release stage records use `script` for their execution target. The
[Stage invocation](STAGE_INVOCATION.md) migration replaces that field with the
`implementation` reference shown above.

## Enforcement

| Operation | Check |
| --- | --- |
| Freeze | Local class bytes match the selected source commit; the class accepts the parameters |
| Preflight | Class identity and parameter validity receive separate check results |
| Execute | The controlled child validates the parameters before constructing `StageContext` |
| Verify | Source bytes match the frozen identity and define the selected top-level class |

The worker imports project code inside the child process defined by
[Process startup](PROCESS_STARTUP.md). Local and GCE execution use the same
parameter-model interface. OCI isolation will apply that interface inside its
confinement boundary.

Validation uses strict Pydantic types. The class output must equal the frozen
JSON mapping exactly. Include every effective default in `params`; this keeps
the plan and the values received by project code identical.

This contract proves parameter identity and validity. The current stage
interface supplies the spec path to project code, which reloads the document.
[Stage invocation](STAGE_INVOCATION.md) defines typed delivery of the validated
value to the decorated callable. [HTTP retrieval](HTTP_RETRIEVAL.md) applies the
same validation mechanism to `HttpTransportParams`. The selected transport
callable receives that typed value through `HttpTransportContext`.
