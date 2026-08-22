"""Provide installed commands for plan authoring and provenance verification."""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import TypeAdapter

from .authoring import freeze_run_plan, load_run_plan_draft
from .execution import execute_stage_process
from .records import ArtifactPointer, BenchmarkResult, ResolvedRun, RunSpec
from .verifier import (
    VerificationPolicy,
    verify_benchmark_result,
    verify_promoted_artifact,
    verify_run_result,
)
from .yaml_io import load_resolved_spec, load_spec, load_yaml_bytes


def _load_model(path: Path, model_type: type[object]) -> object:
    """Load one duplicate-key-safe YAML document through a Pydantic model."""
    return TypeAdapter(model_type).validate_python(load_yaml_bytes(path.read_bytes()))


def _policy(repositories: list[str]) -> VerificationPolicy:
    """Construct an explicit artifact-loader trust policy from CLI arguments."""
    return VerificationPolicy(trusted_loader_repositories=frozenset(repositories))


def build_parser() -> argparse.ArgumentParser:
    """Build the MANTRA command-line parser and its subcommands."""
    parser = argparse.ArgumentParser(prog="mantra")
    commands = parser.add_subparsers(dest="command", required=True)

    validate_stage = commands.add_parser(
        "validate-stage",
        help="validate one authored stage specification",
    )
    validate_stage.add_argument("path", type=Path)

    validate_resolved = commands.add_parser(
        "validate-resolved-stage",
        help="validate one resolved stage record",
    )
    validate_resolved.add_argument("path", type=Path)

    validate_run = commands.add_parser(
        "validate-run",
        help="validate one frozen run specification",
    )
    validate_run.add_argument("path", type=Path)

    freeze = commands.add_parser(
        "freeze-run",
        help="write canonical stage specs and a hash-bound RunSpec",
    )
    freeze.add_argument("draft", type=Path)
    freeze.add_argument("--repository-root", type=Path, default=Path.cwd())

    execute = commands.add_parser(
        "execute-stage",
        help="run one stage from a frozen local run plan",
    )
    execute.add_argument("run_spec", type=Path)
    execute.add_argument("stage_id")
    execute.add_argument("--repository-root", type=Path, default=Path.cwd())

    for name, help_text in (
        ("verify-run", "verify one terminal resolved run"),
        ("verify-benchmark", "verify one benchmark result"),
        ("verify-pointer", "verify one promoted artifact pointer"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("path", type=Path)
        command.add_argument(
            "--trust-loader-source",
            action="append",
            required=True,
            help="exact source-repository URL whose artifact loaders may execute",
        )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute one authoring, validation, or verification command."""
    arguments = build_parser().parse_args(argv)

    if arguments.command == "validate-stage":
        stage = load_spec(arguments.path)
        print(f"valid {stage.kind} stage")
        return 0

    if arguments.command == "validate-resolved-stage":
        stage = load_resolved_spec(arguments.path)
        print(f"valid resolved {stage.kind} stage")
        return 0

    if arguments.command == "validate-run":
        _load_model(arguments.path, RunSpec)
        print("valid run plan")
        return 0

    if arguments.command == "freeze-run":
        draft = load_run_plan_draft(arguments.draft)
        frozen = freeze_run_plan(arguments.repository_root, draft)
        print(f"froze {len(frozen.run.stages)} stages in {len(frozen.files)} files")
        return 0

    if arguments.command == "execute-stage":
        run = _load_model(arguments.run_spec, RunSpec)
        assert isinstance(run, RunSpec)
        reference = next(
            (stage for stage in run.stages if stage.stage_id == arguments.stage_id),
            None,
        )
        if reference is None:
            raise ValueError(f"run plan has no stage {arguments.stage_id!r}")
        stage = load_spec(arguments.repository_root / reference.spec)
        result = execute_stage_process(arguments.repository_root, reference, stage)
        file_count = sum(
            1 if artifact.kind == "file" else len(artifact.members)
            for artifact in result.artifacts.values()
        )
        print(f"executed stage {reference.stage_id} and identified {file_count} files")
        return 0

    policy = _policy(arguments.trust_loader_source)
    if arguments.command == "verify-run":
        resolved_run = _load_model(arguments.path, ResolvedRun)
        assert isinstance(resolved_run, ResolvedRun)
        verified = verify_run_result(resolved_run, policy=policy)
        print(f"verified run {verified.plan.run.run_id}")
        return 0

    if arguments.command == "verify-benchmark":
        result = _load_model(arguments.path, BenchmarkResult)
        assert isinstance(result, BenchmarkResult)
        verified = verify_benchmark_result(result, policy=policy)
        print(f"verified benchmark result {verified.result.status}")
        return 0

    pointer = _load_model(arguments.path, ArtifactPointer)
    assert isinstance(pointer, ArtifactPointer)
    verified_artifact = verify_promoted_artifact(pointer, policy=policy)
    print(f"verified artifact with {len(verified_artifact.files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
