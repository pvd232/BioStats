"""Apply a frozen run's controls before invoking one project stage entrypoint."""

from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

from .protocol import RunSpec
from .runtime import apply_reproducibility, autocast_context, observe_local_execution
from .serialization import load_stage_spec, parse_yaml_bytes


def main(argv: list[str] | None = None) -> int:
    """Apply run controls and execute one exact stage script in this process."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2:
        raise ValueError("stage worker requires STAGE_SPEC and RUN_SPEC")
    stage_spec_path = Path(arguments[0])
    run_spec_path = Path(arguments[1])
    stage = load_stage_spec(stage_spec_path)
    run = RunSpec.model_validate(parse_yaml_bytes(run_spec_path.read_bytes()))
    apply_reproducibility(run.seed, run.reproducibility)
    context_path = os.environ.get("VIPER_RUNTIME_CONTEXT_PATH")
    if context_path is None:
        raise ValueError("VIPER_RUNTIME_CONTEXT_PATH is required")
    Path(context_path).write_text(
        observe_local_execution(run.seed, run.reproducibility).model_dump_json(),
        encoding="utf-8",
    )
    sys.argv = [str(stage.script), str(stage_spec_path)]
    with autocast_context(run.reproducibility):
        runpy.run_path(stage.script, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
