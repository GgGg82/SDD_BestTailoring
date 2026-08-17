"""Il Gate 4 non deve congelare una baseline che non esiste in nessuna versione salvata.

Il Gate Decision Record registra il fingerprint del codice approvato: serve a
poter dire domani "ho approvato esattamente questa versione". Se al momento
dell'approvazione ci sono modifiche non committate, quel fingerprint non
descrive alcuno stato salvato, e il verbale dichiara congelato uno stato che
non lo e'.

`worktree_dirty` era gia' calcolato e scritto nel verbale (`cli.py`), ma nessun
criterio lo consultava.

## Cosa conta come "sporco"

Deliberatamente **non** i file che l'engine scrive da se'. Verificato durante il
collaudo: seguendo alla lettera la procedura di `CLAUDE.md` — prima
`refresh --strict`, poi approvazione del Gate 4 — l'albero risulta sempre
sporco, perche' e' il refresh stesso ad aver appena riscritto `state/` e
`reports/`:

    albero pulito                 -> 0 file modificati
    dopo 'refresh --strict'       -> 4 file modificati (output dell'engine)
    worktree_dirty al Gate 4      -> True

Contare anche quelli renderebbe la procedura documentata ineseguibile senza un
passaggio di commit che oggi non e' scritto da nessuna parte. Escluderli e'
anche coerente con una regola che il framework applica gia': la directory di
output e' *sempre* esclusa dalla scansione dei sorgenti (TRACEABILITY-RULES).

Il segnale diventa cosi' quello che serve davvero: **il tuo** lavoro — codice,
spec, task — ha modifiche non salvate.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from burnup.errors import ExitCode

FINDING_TYPE = "uncommitted-changes"


def _plan(project: Path) -> None:
    (project / "specs" / "001-demo" / "plan.md").write_text("# Plan\n", encoding="utf-8")


def _complete_feature(project: Path) -> None:
    (project / "specs" / "001-demo" / "tasks.md").write_text(
        "# Task\n\n"
        "- [x] T001 [REQ:FR-001] Implement auth in src/auth.py\n"
        "- [x] T002 [REQ:NFR-001] Tune latency in src/auth.py\n",
        encoding="utf-8",
    )
    (project / "src" / "auth.py").write_text(
        '"""Auth."""\n# REQ: 001-demo/FR-001\ndef auth():\n    return True\n\n'
        "# REQ: 001-demo/NFR-001\ndef fast():\n    return True\n",
        encoding="utf-8",
    )
    _plan(project)


def _verify_all(cli) -> None:
    for req, test_id in (("001-demo/FR-001", "TEST-001"), ("001-demo/NFR-001", "TEST-002")):
        cli("test", "define", test_id, "--actor", "ba-qa", "--reason", "collaudo",
            "--requirement", req, "--definition", f"verifica {req}", "--mandatory")
        cli("test", "confirm-manual", test_id, "--actor", "ba-qa", "--reason", "eseguito",
            "--result", "pass", "--evidence", "verbale")
    cli("refresh")


def _commit(project: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(["git", "-c", "user.email=t@e.com", "-c", "user.name=t",
                    "commit", "-qm", message], cwd=project, check=True)


def open_types(project: Path) -> set[str]:
    path = project / "requirement-burnup" / "state" / "findings.jsonl"
    return {
        json.loads(line)["finding_type"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line)["status"] == "open"
    }


def test_engine_output_alone_does_not_count_as_dirty(project: Path, cli):
    """Il refresh sporca l'albero da se': non deve accusarsi da solo."""
    _complete_feature(project)
    cli("init")
    _verify_all(cli)
    _commit(project, "stato")

    cli("refresh")
    assert subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                          cwd=project, capture_output=True, text=True).stdout.strip(), \
        "presupposto del test: il refresh deve aver modificato i propri file"

    assert FINDING_TYPE not in open_types(project)


def test_uncommitted_source_changes_are_reported(project: Path, cli):
    _complete_feature(project)
    cli("init")
    _verify_all(cli)
    _commit(project, "stato")

    (project / "src" / "auth.py").write_text(
        (project / "src" / "auth.py").read_text(encoding="utf-8") + "\n# modifica non salvata\n",
        encoding="utf-8",
    )
    cli("refresh")

    assert FINDING_TYPE in open_types(project)


def test_gate_4_is_blocked_by_uncommitted_work(project: Path, cli):
    _complete_feature(project)
    cli("init")
    _verify_all(cli)
    _commit(project, "stato")
    for gate in ("1", "2", "3"):
        cli("gate", "approve", "001-demo", gate, "--actor", "utente", "--reason", "baseline")

    (project / "specs" / "001-demo" / "spec.md").write_text(
        (project / "specs" / "001-demo" / "spec.md").read_text(encoding="utf-8") + "\n<!-- nota -->\n",
        encoding="utf-8",
    )
    cli("refresh", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)
    cli("gate", "approve", "001-demo", "4", "--actor", "utente", "--reason", "rilascio",
        expect=ExitCode.QUALITY_GATE_FAILED)


def test_documented_procedure_still_works_on_a_clean_tree(project: Path, cli):
    """Il controllo non deve rompere la sequenza prescritta da CLAUDE.md."""
    _complete_feature(project)
    cli("init")
    _verify_all(cli)
    _commit(project, "stato")
    for gate in ("1", "2", "3"):
        cli("gate", "approve", "001-demo", gate, "--actor", "utente", "--reason", "baseline")

    cli("refresh", "--strict")
    cli("gate", "approve", "001-demo", "4", "--actor", "utente", "--reason", "rilascio")
