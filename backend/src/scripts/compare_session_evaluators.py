"""CLI for privacy-safe, non-persisting evaluator comparisons."""

from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy.orm import Session

from config.settings import get_settings
from db.base import SessionLocal
from repositories.turn_repo import TurnRepository
from services.evaluator_comparison_service import (
    EVALUATOR_DEFINITIONS,
    EvaluatorComparisonService,
    build_comparison_artifact,
    validate_evaluator_identifiers,
)

EXIT_SUCCESS = 0
EXIT_INVALID_INPUT = 2
EXIT_PARTIAL_FAILURE = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare supported evaluators without modifying stored session data."
    )
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument(
        "--evaluators",
        default="all",
        help="'all' or a comma-separated selection: baseline,hybrid_v1,hybrid_v2",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--include-transcript", action="store_true")
    parser.add_argument("--allow-active-session", action="store_true")
    return parser


def parse_evaluator_selection(raw: str) -> list[str]:
    value = str(raw).strip()
    if value == "all":
        return list(EVALUATOR_DEFINITIONS)
    if "all" in {part.strip() for part in value.split(",")}:
        raise ValueError("'all' cannot be combined with individual evaluator identifiers.")
    return validate_evaluator_identifiers(value.split(","))


def get_git_commit() -> str | None:
    """Return a validated commit hash without exposing command errors or repository config."""
    repository_root = Path(__file__).resolve().parents[3]
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None


def _write_json(output: Path, content: str, *, overwrite: bool) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with output.open(mode, encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        handle.write("\n")


async def execute_command(args: argparse.Namespace, db: Session) -> int:
    """Execute an already-parsed command, returning a stable process-style exit code."""
    try:
        if args.session_id <= 0:
            raise ValueError("--session-id must be a positive integer.")
        evaluators = parse_evaluator_selection(args.evaluators)
        if args.output.exists() and not args.overwrite:
            raise FileExistsError("Output already exists; pass --overwrite to replace it.")

        settings = get_settings()
        service = EvaluatorComparisonService(
            db,
            model_identifier=settings.openai_model_id,
        )
        results = await service.run_evaluators(
            args.session_id,
            evaluators,
            require_completed=not args.allow_active_session,
        )
        turns = TurnRepository(db).get_by_session(args.session_id)
        artifact = build_comparison_artifact(
            session_id=args.session_id,
            turns=turns,
            requested_evaluators=evaluators,
            results=results,
            include_transcript=args.include_transcript,
            git_commit=get_git_commit(),
        )
        _write_json(
            args.output,
            artifact.model_dump_json(indent=2, exclude_none=True),
            overwrite=args.overwrite,
        )
        return (
            EXIT_SUCCESS
            if all(result.status == "success" for result in results)
            else EXIT_PARTIAL_FAILURE
        )
    except (ValueError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID_INPUT


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    db = SessionLocal()
    try:
        return asyncio.run(execute_command(args, db))
    except Exception:  # noqa: BLE001 - CLI boundary omits raw exception details
        print("Comparison failed before a safe artifact could be produced.", file=sys.stderr)
        return EXIT_INVALID_INPUT
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
