"""Execute one project parameter validator in a dedicated worker process."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .parameter_models import ParameterValidationContext, validate_parameters
from .protocol import InternalSpec
from .serialization import load_stage_spec


def main() -> int:
    """Validate frozen stage parameters and write their effective JSON mapping."""
    context_path = os.environ.get("VIPER_CONTEXT_PATH")
    if context_path is None:
        raise ValueError("VIPER_CONTEXT_PATH is required")
    context = ParameterValidationContext.model_validate_json(
        Path(context_path).read_text(encoding="utf-8")
    )
    stage = load_stage_spec(context.stage_spec_path)
    if not isinstance(stage, InternalSpec):
        raise ValueError("parameter validation requires an internal stage")
    reference = stage.parameter_model
    validated = validate_parameters(
        Path.cwd() / reference.path,
        reference,
        stage.params,
        type(stage.params),
    )
    context.result_path.write_text(
        json.dumps(validated, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
