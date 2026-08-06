"""I 7 finding rilevati dalla revisione critica dell'audit (N-01..N-07).

Non erano nel report originale. Ognuno e' stato verificato sul codice v3 prima
di essere accettato come difetto reale.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from burnup.engine import compute_counts, git_revision
from burnup.errors import ExitCode, InvariantError
from burnup.mdparse import parse_document, read_text
from burnup.models import Requirement
from burnup.paths import expand_globs
from burnup.risk_link import strip_backticks
from burnup.store import Store, StoreLock, atomic_write_text
from conftest import make_config


def _req(key: str, state: str, scope: str = "active") -> Requirement:
    return Requirement(
        key=key, feature_id="f", requirement_id=key.split("/")[-1], text="t",
        fingerprint="fp", source="s", scope_state=scope, lifecycle_state=state,
    )


# -- N-01 ------------------------------------------------------------------
def test_n01_invariant_raises_typed_error(monkeypatch):
    """v3: l'invariante di burn-up era protetta da un `assert`.

    Due conseguenze, entrambe verificate sul codice v3: sotto `python -O`
    l'`assert` sparisce, disattivando il controllo proprio quando l'integrita'
    conta di piu'; e quando scattava, `AssertionError` non era intercettata
    dalla CLI, che restituiva un traceback grezzo con exit code 1 —
    indistinguibile da un errore di configurazione.
    """
    import burnup.engine as engine
    from burnup.models import Counts

    def broken(*_args, **kwargs):
        return Counts(scope=1, defined=0, implemented=0, tested=1, removed_total=0)

    monkeypatch.setattr(engine, "Counts", broken)
    with pytest.raises(InvariantError) as exc:
        engine.compute_counts([_req("f/FR-001", "tested")])
    assert exc.value.exit_code == ExitCode.ENGINE_ERROR
    assert "Invariante" in exc.value.message


def test_n01b_invariant_check_survives_python_O():
    """Il controllo deve restare attivo anche con le ottimizzazioni abilitate."""
    tool_dir = Path(__file__).resolve().parent.parent
    script = (
        "import burnup.engine as e\n"
        "from burnup.models import Counts\n"
        "from burnup.errors import InvariantError\n"
        "e.Counts = lambda **k: Counts(scope=1, defined=0, implemented=0, tested=1, removed_total=0)\n"
        "class R:\n"
        "    scope_state = 'active'\n"
        "    lifecycle_state = 'tested'\n"
        "    key = 'f/FR-001'\n"
        "try:\n"
        "    e.compute_counts([R()])\n"
        "    print('NON-RILEVATO')\n"
        "except InvariantError:\n"
        "    print('RILEVATO')\n"
    )
    env = dict(os.environ, PYTHONPATH=str(tool_dir))
    result = subprocess.run([sys.executable, "-O", "-c", script], capture_output=True, text=True, env=env)
    assert result.stdout.strip() == "RILEVATO", (
        f"il controllo di integrita' e' stato disattivato da python -O: {result.stdout} {result.stderr}"
    )


def test_n01b_invariant_error_has_distinct_exit_code():
    assert InvariantError("x").exit_code == ExitCode.ENGINE_ERROR
    from burnup.errors import ConfigError, QualityGateFailed
    assert ConfigError("x").exit_code == ExitCode.CONFIG_ERROR
    assert QualityGateFailed("x").exit_code == ExitCode.QUALITY_GATE_FAILED
    # I quattro codici devono essere distinguibili da una pipeline.
    assert len({ExitCode.OK, ExitCode.CONFIG_ERROR, ExitCode.QUALITY_GATE_FAILED, ExitCode.ENGINE_ERROR}) == 4


# -- N-02 ------------------------------------------------------------------
def test_n02_no_artifacts_created_when_validation_fails(project: Path, cli):
    """v3: `_ensure_output_files` copiava i template all'inizio del refresh,
    quindi un errore successivo lasciava artefatti vuoti che il refresh
    seguente trattava come stato precedente valido."""
    (project / "requirement-burnup-config.yml").write_text(
        'schema_version: "2.0"\noutput_dir: "requirement-burnup"\n'
        'inputs:\n  source_globs: []\n'
        "requirements:\n  accepted_id_patterns: []\n"
        "traceability: {}\nstatus:\n  test_freshness_policy: \"latest-known\"\nsnapshots: {}\n",
        encoding="utf-8",
    )
    cli("init", expect=ExitCode.CONFIG_ERROR)
    assert not (project / "requirement-burnup").exists(), \
        "nessun artefatto deve esistere se la configurazione non e' valida"


def test_n02b_atomic_write_leaves_no_partial_file(tmp_path: Path):
    target = tmp_path / "out.json"
    atomic_write_text(target, '{"a": 1}')
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
    assert not list(tmp_path.glob(".*tmp")), "nessun file temporaneo deve sopravvivere"

    class Boom(Exception):
        pass

    try:
        atomic_write_text(target, None)  # type: ignore[arg-type]
    except Exception:
        pass
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}, \
        "una scrittura fallita non deve danneggiare il file esistente"


# -- N-03 ------------------------------------------------------------------
def test_n03_bom_frontmatter(tmp_path: Path):
    """Sostituisce il finding P1-08 dell'audit, che sul CRLF era un falso positivo."""
    p = tmp_path / "bom.md"
    p.write_bytes("﻿---\nartifact: x\n---\n\n# Titolo\n".encode("utf-8"))
    doc = parse_document(read_text(p))
    assert "artifact: x" in doc.frontmatter_raw
    assert doc.sections[1].title == "Titolo"


# -- N-04 ------------------------------------------------------------------
def test_n04_backtick_stripping_is_shared_and_guarded():
    """v3: `unbacktick` era duplicato in tre file con guardie divergenti.
    Solo requirements.py proteggeva con len>=2, quindi una cella contenente un
    singolo backtick si azzerava negli altri due."""
    assert strip_backticks("`FR-001`") == "FR-001"
    assert strip_backticks("`") == "`", "un solo backtick non e' una coppia di delimitatori"
    assert strip_backticks("``x``") == "x"
    assert strip_backticks("—") == ""
    assert strip_backticks("") == ""


# -- N-05 ------------------------------------------------------------------
def test_n05_git_revision_reports_why_it_failed(tmp_path: Path):
    """v3: ritornava stringa vuota per qualunque motivo, rendendo
    indistinguibili 'git assente' e 'non e' un repository'."""
    revision, dirty, problem = git_revision(tmp_path)
    assert revision == ""
    assert problem, "il motivo deve essere esplicito, non silenzioso"


def test_n05b_dirty_worktree_is_detected(project: Path):
    revision, dirty, problem = git_revision(project)
    assert revision and not dirty and not problem
    (project / "src" / "auth.py").write_text("# modificato\n", encoding="utf-8")
    revision2, dirty2, _ = git_revision(project)
    assert dirty2, "una modifica non committata deve essere rilevata"


def test_n05c_dirty_worktree_blocks_current_revision_freshness():
    from burnup.models import TestRun as Run
    from burnup.status import StatusContext, evaluate_freshness

    run = Run(run_id="r", run_identity="i", test_id="T", result="pass",
              executed_at="2026-01-01T00:00:00Z", source_revision="abc123", revision_origin="sidecar")
    clean = StatusContext("current-revision", "abc123", False, True)
    dirty = StatusContext("current-revision", "abc123", True, True)
    assert evaluate_freshness(run, clean).fresh
    assert not evaluate_freshness(run, dirty).fresh


# -- N-06 ------------------------------------------------------------------
def test_n06_reconcile_does_not_alias_discovered_rows(project: Path, cli):
    """Bug latente: la v3 faceva `row = discovered` senza copia."""
    cli("init")
    cli("refresh")
    state = json.loads((project / "requirement-burnup" / "state" / "requirements.json").read_text(encoding="utf-8"))
    keys = [r["key"] for r in state]
    assert len(keys) == len(set(keys)), "nessun requisito duplicato nello store"


# -- N-07 ------------------------------------------------------------------
def test_n07_output_dir_always_excluded_from_source_scan(project: Path, cli):
    """Il confronto e' sulle COMPONENTI del percorso, non sulla stringa:
    `requirement-burnup-config.yml` sta alla radice ed e' legittimamente
    scansionabile, mentre nulla dentro `requirement-burnup/` deve esserlo."""
    cli("init")
    found = expand_globs(project, ["**/*"])
    parts = [p.relative_to(project).parts for p in found]
    assert all("requirement-burnup" not in pp for pp in parts), "la directory di output non va scansionata"
    assert all(".git" not in pp for pp in parts)
    assert any(pp == ("src", "auth.py") for pp in parts), "il codice sorgente deve invece esserci"


# -- Lock (P0-12) ----------------------------------------------------------
def test_concurrent_refresh_is_serialised(project: Path, cli):
    cli("init")
    store = Store(project / "requirement-burnup")
    from burnup.errors import LockError

    with StoreLock(store.state_dir):
        with pytest.raises(LockError):
            with StoreLock(store.state_dir, timeout=0.2):
                pass


def test_lock_is_released_after_use(project: Path, cli):
    cli("init")
    store = Store(project / "requirement-burnup")
    with StoreLock(store.state_dir):
        pass
    with StoreLock(store.state_dir, timeout=0.2):
        pass  # deve poter riacquisire
