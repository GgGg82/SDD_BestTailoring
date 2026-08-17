"""Fixture condivise: un progetto Spec Kit minimo ma realistico."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from burnup.config import BurnupConfig  # noqa: E402

PATTERNS = ["FR-[0-9]+", "NFR-[0-9]+"]

CONFIG_YML = """
schema_version: "2.0"
output_dir: "requirement-burnup"
inputs:
  source_globs: ["src/**/*"]
  test_report_globs: ["test-results/**/*.xml", "test-results/**/*.json"]
requirements:
  accepted_id_patterns: ["FR-[0-9]+", "NFR-[0-9]+"]
  sections: ["Requirements"]
  user_story_sections: ["User Scenarios"]
traceability:
  code_evidence_marker: "REQ:\\\\s*([A-Za-z0-9_.\\\\-]+/[A-Za-z0-9_\\\\-]+)"
status:
  test_freshness_policy: "manual-confirmation"
snapshots:
  allow_forced_snapshot: true
gates:
  strict_blocks_on: ["high"]
"""

SPEC = """# Spec demo

## User Scenarios

### User Story 1 - accesso
Il visitatore accede.

### User Story 2 - uscita
Il visitatore esce.

## Requirements

- **FR-001**: il sistema deve autenticare l'utente
- **NFR-001**: la risposta deve arrivare entro 100ms

# Notes

- FR-999: vedi il documento di architettura esterno per il contesto
"""

TASKS = """# Task

- [x] T001 Implement auth for FR-001 in src/auth.py
- [ ] T002 Tune latency for NFR-001
"""

SOURCE = '''"""Modulo di autenticazione."""
# REQ: 001-demo/FR-001
def auth():
    return True
'''


def make_config(project_root: Path, **overrides) -> BurnupConfig:
    """Config in memoria, per i test di unità che non passano dal file YAML."""
    base = dict(
        project_root=project_root,
        config_path=project_root / "requirement-burnup-config.yml",
        output_dir=project_root / "requirement-burnup",
        source_globs=["src/**/*"],
        test_report_globs=["test-results/**/*.xml", "test-results/**/*.json"],
        accepted_id_patterns=PATTERNS,
        id_regex=re.compile(
            r"(?<![A-Za-z0-9_-])(?:" + "|".join(f"(?:{p})" for p in PATTERNS) + r")(?![A-Za-z0-9_])"
        ),
        code_evidence_marker=r"REQ:\s*([A-Za-z0-9_.\-]+/[A-Za-z0-9_\-]+)",
        code_evidence_regex=re.compile(r"REQ:\s*([A-Za-z0-9_.\-]+/[A-Za-z0-9_\-]+)"),
        test_id_mapping={},
        freshness_policy="manual-confirmation",
        default_scope_state="active",
        requirement_sections=["Requirements"],
        user_story_sections=["User Scenarios"],
        comment_prefixes=["#", "//", "--", "/*", "*", ";", "%"],
        extra_excludes=(),
        allow_forced_snapshot=True,
        strict_blocks_on=("high",),
        require_tasks_for_implemented=True,
        raw={},
    )
    base.update(overrides)
    return BurnupConfig(**base)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Progetto Spec Kit inizializzato come repository Git."""
    root = tmp_path / "proj"
    (root / "specs" / "001-demo").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "test-results").mkdir()

    (root / "specs" / "001-demo" / "spec.md").write_text(SPEC, encoding="utf-8")
    (root / "specs" / "001-demo" / "tasks.md").write_text(TASKS, encoding="utf-8")
    (root / "src" / "auth.py").write_text(SOURCE, encoding="utf-8")
    (root / "requirement-burnup-config.yml").write_text(CONFIG_YML, encoding="utf-8")

    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
    return root


@pytest.fixture
def commit(project: Path):
    """Salva in Git lo stato corrente del progetto di prova.

    Serve ai test che verificano un `refresh --strict` andato a buon fine:
    da quando il Gate 4 rifiuta di congelare una baseline con lavoro non
    committato, un albero sporco e' di per se' una condizione bloccante.
    """
    def run(message: str = "stato") -> None:
        subprocess.run(["git", "add", "-A"], cwd=project, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@example.com", "-c", "user.name=test",
             "commit", "-qm", message],
            cwd=project, check=True,
        )

    return run


@pytest.fixture
def cli(project: Path):
    """Invoca la CLI in-process e ritorna (exit_code, stdout, stderr)."""
    from burnup.cli import main

    def run(*argv: str, expect: int | None = 0):
        import contextlib
        import io

        out, err = io.StringIO(), io.StringIO()
        args = list(argv)
        if "--project-root" not in args:
            args += ["--project-root", str(project)]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(args)
        if expect is not None:
            assert code == expect, f"exit {code} (atteso {expect})\nSTDOUT:\n{out.getvalue()}\nSTDERR:\n{err.getvalue()}"
        return code, out.getvalue(), err.getvalue()

    return run
