"""C-10: l'engine deve conoscere le classi di change.

`docs/SCALE-ADAPTIVE-FLOW.md` è dichiarato **normativo** e prescrive:

    | | Fast Track | Standard | High-Risk |
    | Gate | **1 e 4** | 1, 2, 3, 4 | 1, 2, 3, 4 + revisione di sicurezza |
    | plan.md | non richiesto | richiesto | richiesto |

e `.specify/templates/progress-template.md` lo ripete: *"Fast Track salta i
Gate 2 e 3, ma NON riduce tracciabilità, test obbligatori né `refresh --strict`
prima del Gate 4"*.

La state machine invece esigeva che ogni gate avesse il precedente valido, e
il Gate 4 era irraggiungibile senza i Gate 2 e 3:

    Gate 1 -> exit 0
    Gate 4 -> exit 2
       - il Gate 3 (Implementation Readiness) non e' valido: stato 'not-approved'

Cercando `fast-track`, `high-risk` o `change_class` nel codice non compariva
nulla: l'engine non sapeva che le classi esistessero. Vivevano solo in
`progress.md`, dichiarate dall'Orchestratore, e nessun meccanismo le leggeva.

## La scelta di implementazione

La classe è una **decisione umana**, quindi passa da un comando e produce un
record permanente con attore e motivo — come ogni altra decisione del sistema.
Non serve un campo nuovo nel canonical store: `decisions.jsonl` esiste già, e
la classe corrente è l'ultima decisione di tipo `feature-class`.

`SCALE-ADAPTIVE-FLOW` impone due vincoli che i test qui sotto presidiano:

* **la promozione è ammessa in corsa, la retrocessione no** — retrocedere
  significherebbe rimuovere un controllo dopo aver visto cosa avrebbe trovato;
* **ciò che scala è il numero di artefatti e revisioni, mai il rigore della
  misurazione** — tracciabilità, test obbligatori e `refresh --strict` valgono
  identici in tutte le classi.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from burnup.errors import ExitCode


def _plan(project: Path) -> None:
    (project / "specs" / "001-demo" / "plan.md").write_text("# Plan\n", encoding="utf-8")


def _feature_completa(project: Path) -> None:
    (project / "specs" / "001-demo" / "tasks.md").write_text(
        "# Task\n\n"
        "- [x] T001 [REQ:FR-001] auth in src/auth.py\n"
        "- [x] T002 [REQ:NFR-001] latency in src/auth.py\n",
        encoding="utf-8",
    )
    (project / "src" / "auth.py").write_text(
        '"""Auth."""\n# REQ: 001-demo/FR-001\ndef auth():\n    return True\n\n'
        "# REQ: 001-demo/NFR-001\ndef fast():\n    return True\n",
        encoding="utf-8",
    )


def _verifica_tutto(cli) -> None:
    for req, tid in (("001-demo/FR-001", "TEST-001"), ("001-demo/NFR-001", "TEST-002")):
        cli("test", "define", tid, "--actor", "qa", "--reason", "copertura",
            "--requirement", req, "--definition", f"verifica {req}", "--mandatory")
        cli("test", "confirm-manual", tid, "--actor", "qa", "--reason", "eseguito",
            "--result", "pass", "--evidence", "verbale")
    cli("refresh")


def _decisioni(project: Path, kind: str) -> list[dict]:
    path = project / "requirement-burnup" / "state" / "decisions.jsonl"
    return [
        d for d in (json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip())
        if d["kind"] == kind
    ]


# -- Il difetto ------------------------------------------------------------
def test_fast_track_permette_di_approvare_il_gate_4_dopo_il_gate_1(project: Path, cli, commit):
    """La riga "Gate: 1 e 4" di SCALE-ADAPTIVE-FLOW, resa eseguibile."""
    _feature_completa(project)
    cli("init")
    _verifica_tutto(cli)
    commit("feature completa")

    cli("feature", "class", "001-demo", "fast-track",
        "--actor", "orchestratore", "--reason", "correzione di testo, nessun requisito nuovo")

    cli("gate", "approve", "001-demo", "1", "--actor", "utente", "--reason", "requisiti")
    cli("refresh", "--strict")
    cli("gate", "approve", "001-demo", "4", "--actor", "utente", "--reason", "rilascio")


def test_fast_track_non_richiede_plan_ne_tasks(project: Path, cli, commit):
    """SCALE-ADAPTIVE-FLOW: per Fast Track `plan.md` è "non richiesto"."""
    _feature_completa(project)
    (project / "specs" / "001-demo" / "plan.md").unlink(missing_ok=True)
    cli("init")
    _verifica_tutto(cli)
    commit("feature completa")

    cli("feature", "class", "001-demo", "fast-track", "--actor", "orc", "--reason", "fix locale")
    cli("gate", "approve", "001-demo", "1", "--actor", "utente", "--reason", "requisiti")
    cli("refresh", "--strict")
    cli("gate", "approve", "001-demo", "4", "--actor", "utente", "--reason", "rilascio")


def test_standard_resta_il_comportamento_di_prima(project: Path, cli, commit):
    """La classe di default non cambia nulla: tutti e quattro i gate, in ordine."""
    _feature_completa(project)
    _plan(project)
    cli("init")
    _verifica_tutto(cli)
    commit("feature completa")

    cli("gate", "approve", "001-demo", "1", "--actor", "u", "--reason", "r")
    cli("gate", "approve", "001-demo", "4", "--actor", "u", "--reason", "r",
        expect=ExitCode.QUALITY_GATE_FAILED)


def test_la_classe_di_default_e_standard(project: Path, cli):
    cli("init")
    _, out, _ = cli("gate", "status", "001-demo", "--json")
    assert json.loads(out)["change_class"] == "standard"


# -- Promozione sì, retrocessione no --------------------------------------
def test_la_promozione_e_ammessa_in_corsa(project: Path, cli):
    cli("init")
    cli("feature", "class", "001-demo", "fast-track", "--actor", "orc", "--reason", "sembrava piccola")
    cli("feature", "class", "001-demo", "high-risk", "--actor", "orc",
        "--reason", "tocca l'autenticazione, emerso durante l'implementazione")
    _, out, _ = cli("gate", "status", "001-demo", "--json")
    assert json.loads(out)["change_class"] == "high-risk"


def test_la_retrocessione_e_rifiutata(project: Path, cli):
    """"La retrocessione non è ammessa: significherebbe rimuovere un controllo
    dopo aver visto cosa avrebbe trovato"."""
    cli("init")
    cli("feature", "class", "001-demo", "high-risk", "--actor", "orc", "--reason", "dati personali")
    cli("feature", "class", "001-demo", "fast-track", "--actor", "orc", "--reason", "ci ho ripensato",
        expect=ExitCode.CONFIG_ERROR)


def test_la_classe_e_una_decisione_registrata(project: Path, cli):
    cli("init")
    cli("feature", "class", "001-demo", "fast-track",
        "--actor", "orchestratore", "--reason", "solo refactoring interno")
    registrate = _decisioni(project, "feature-class")
    assert len(registrate) == 1
    assert registrate[0]["actor"] == "orchestratore"
    assert "refactoring" in registrate[0]["reason"]
    assert registrate[0]["payload"]["change_class"] == "fast-track"


# -- Il rigore non scala ---------------------------------------------------
@pytest.mark.parametrize("classe", ["fast-track", "standard", "high-risk"])
def test_il_rigore_della_misurazione_non_scala_mai(project: Path, cli, commit, classe):
    """"Ciò che scala è il numero di artefatti e di revisioni, non il rigore
    della misurazione": un requisito non verificato blocca il Gate 4 in tutte
    e tre le classi."""
    _plan(project)
    cli("init")
    cli("feature", "class", "001-demo", classe, "--actor", "orc", "--reason", "collaudo")
    commit("stato")

    cli("refresh", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)
    cli("gate", "approve", "001-demo", "1", "--actor", "u", "--reason", "r")
    if classe != "fast-track":
        for gate in ("2", "3"):
            cli("gate", "approve", "001-demo", gate, "--actor", "u", "--reason", "r")
    cli("gate", "approve", "001-demo", "4", "--actor", "u", "--reason", "r",
        expect=ExitCode.QUALITY_GATE_FAILED)


def test_una_classe_inventata_e_rifiutata(project: Path, cli):
    cli("init")
    cli("feature", "class", "001-demo", "velocissima", "--actor", "orc", "--reason", "r",
        expect=ExitCode.USAGE_ERROR)
