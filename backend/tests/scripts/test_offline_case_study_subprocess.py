"""Process-boundary checks for the genuinely offline seeded baseline workflow."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_ROOT.parent
SOURCE_ROOT = BACKEND_ROOT / "src"
SENSITIVE_ENV_PREFIXES = ("DATABASE", "SUPABASE", "OPENAI", "GEMINI")


def _offline_environment(guard_directory: Path | None = None) -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith(SENSITIVE_ENV_PREFIXES)
    }
    python_paths = [str(SOURCE_ROOT)]
    if guard_directory is not None:
        python_paths.insert(0, str(guard_directory))
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _write_offline_guards(directory: Path) -> None:
    (directory / "sitecustomize.py").write_text(
        """
import socket
import sqlalchemy
import config.settings

def forbidden_settings(*args, **kwargs):
    raise AssertionError("baseline case study loaded application settings")

def forbidden_connection(*args, **kwargs):
    raise AssertionError("baseline case study attempted a network connection")

original_create_engine = sqlalchemy.create_engine

def guarded_create_engine(url, *args, **kwargs):
    if str(url) != "sqlite:///:memory:":
        raise AssertionError(f"unexpected database engine: {url}")
    return original_create_engine(url, *args, **kwargs)

config.settings.get_settings = forbidden_settings
socket.create_connection = forbidden_connection
socket.socket.connect = forbidden_connection
sqlalchemy.create_engine = guarded_create_engine
""".lstrip(),
        encoding="utf-8",
    )


def test_domain_entities_import_without_configured_database_runtime(tmp_path: Path) -> None:
    command = [
        sys.executable,
        "-c",
        (
            "import sys; "
            "from domain.entities.session import Session; "
            "from db.base import Base; "
            "assert Session.__name__ == 'Session'; "
            "assert Base.__name__ == 'Base'; "
            "assert 'db.runtime' not in sys.modules; "
            "assert 'core.events' not in sys.modules"
        ),
    ]

    completed = subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        env=_offline_environment(tmp_path),
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr


def test_documented_baseline_make_target_is_offline(tmp_path: Path) -> None:
    guard_directory = tmp_path / "offline_guard"
    guard_directory.mkdir()
    _write_offline_guards(guard_directory)
    output = tmp_path / "seeded_baseline_case_study.json"
    command = [
        "make",
        "evaluator-case-study-baseline",
        f"EVALUATOR_CASE_STUDY_BASELINE_OUTPUT={output}",
        ("EVALUATOR_CASE_STUDY_PYTHONPATH=" f"{guard_directory}{os.pathsep}{SOURCE_ROOT}"),
    ]

    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        env=_offline_environment(guard_directory),
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert list(payload["condition_results"]) == ["strong", "decent", "mixed", "weak"]
    assert payload["requested_evaluators"] == ["baseline"]
    assert len(payload["paper_table_rows"]) == 4
    assert all(row["evaluator_identifier"] == "baseline" for row in payload["paper_table_rows"])
    assert any("in-memory SQLite" in note for note in payload["methodology_notes"])
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "seeded-case-study@example.invalid" not in serialized
    assert "Fixture-owned transcript" not in serialized
