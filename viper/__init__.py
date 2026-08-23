"""VIPER execution and artifact provenance engine."""

from . import (
    application,
    authoring,
    ids,
    inspection,
    journal,
    local_store,
    materialization,
    metrics,
    parameter_models,
    preflight,
    protocol,
    resume,
    runner,
    stage_execution,
    stages,
    worker,
    workspace,
)

__all__ = [
    "application",
    "authoring",
    "ids",
    "inspection",
    "journal",
    "local_store",
    "materialization",
    "metrics",
    "parameter_models",
    "preflight",
    "protocol",
    "runner",
    "resume",
    "stage_execution",
    "stages",
    "worker",
    "workspace",
]

from .api import run
from .stages import (
    StageContext,
    build_stage,
    download_stage,
    embed_stage,
    evaluate_stage,
    train_stage,
)

__all__ += [
    "StageContext",
    "build_stage",
    "download_stage",
    "embed_stage",
    "evaluate_stage",
    "train_stage",
    "run",
]
