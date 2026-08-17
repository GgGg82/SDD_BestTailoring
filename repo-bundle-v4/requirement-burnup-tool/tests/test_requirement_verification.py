"""C-01: un requisito attivo non verificato deve bloccare il Gate 4.

Difetto trovato nel collaudo end-to-end del 2026-08-06 sulla v4.0.0-beta.1.

Riproduzione originale: un progetto con due requisiti, uno completo e testato,
l'altro presente solo in `spec.md` — nessun task, nessun marcatore nel codice,
nessun test. Risultato:

    001-login/FR-001   tested
    001-login/FR-002   defined
    Finding aperti: 0          Tested: 1/2 (50.0%)
    refresh --strict           -> exit 0
    gate approve 1,2,3,4       -> tutti APPROVATI
    Gate Decision Record:      {'scope': 2, 'tested': 1, ...} outcome: approved

Il record di approvazione conteneva il dato che avrebbe dovuto bloccarlo.

Causa: in `status.py` l'intero blocco che valuta `tested` — incluso il finding
`missing-mandatory-test` — era annidato dentro `if state == "implemented"`. Un
requisito che non raggiunge `implemented` non veniva mai controllato sulla
copertura di test, e la catena di branch sopra emetteva un finding solo per due
casi intermedi. Il caso "ne' codice ne' task", cioe' il requisito su cui nessuno
ha lavorato, cadeva fuori da tutti i rami in silenzio.

Non era una questione di soglia: con `strict_blocks_on: ["high","medium","low"]`
il risultato era identico, perche' non esisteva alcun finding da bloccare.

Rimedio: `requirement-not-verified`, severita' `high`, emesso per OGNI requisito
attivo che non raggiunge `tested`. Gli altri finding restano come spiegazione
del perche'; questo e' il segnale uniforme e waivabile su cui il Gate 4 si
misura. La via d'uscita legittima resta quella che il framework aveva gia':
`burnup finding waive` oppure `burnup requirement remove`, entrambi con attore,
motivo e record permanente.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from burnup.errors import ExitCode

FINDING_TYPE = "requirement-not-verified"


def open_findings(project: Path) -> list[dict]:
    path = project / "requirement-burnup" / "state" / "findings.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def open_of_type(project: Path, finding_type: str) -> list[dict]:
    return [f for f in open_findings(project) if f["status"] == "open" and f["finding_type"] == finding_type]


def lifecycle(project: Path, requirement_id: str) -> str:
    path = project / "requirement-burnup" / "state" / "requirements.json"
    for req in json.loads(path.read_text(encoding="utf-8")):
        if req["requirement_id"] == requirement_id:
            return req["lifecycle_state"]
    raise AssertionError(f"requisito {requirement_id} non trovato nello store")


def write_plan(project: Path) -> None:
    """Il Gate 2 richiede `plan.md`, che la fixture minima non contiene."""
    (project / "specs" / "001-demo" / "plan.md").write_text(
        "# Plan\n\nStack: Python. Nessuna dipendenza esterna.\n", encoding="utf-8"
    )


def make_tested(cli, project: Path, requirement_key: str, test_id: str) -> None:
    """Porta un requisito a 'tested' passando dai comandi di decisione umana."""
    cli("test", "define", test_id, "--actor", "ba-qa", "--reason", "collaudo",
        "--requirement", requirement_key, "--definition", f"verifica {requirement_key}", "--mandatory")
    cli("test", "confirm-manual", test_id, "--actor", "ba-qa", "--reason", "eseguito in locale",
        "--result", "pass", "--evidence", "verbale-collaudo")
    cli("refresh")


# -- Il difetto ------------------------------------------------------------
def test_requirement_with_incomplete_tasks_and_no_code_is_reported(cli, project: Path):
    """NFR-001 della fixture: task incompleto, nessun codice, nessun test.

    Prima del fix questo requisito restava 'defined' senza produrre alcun
    finding: ne' `incomplete-tasks` (che richiede evidenza di codice) ne'
    `tasks-complete-without-code-evidence` (che richiede i task completi).
    """
    cli("init")
    assert lifecycle(project, "NFR-001") == "defined"

    reported = open_of_type(project, FINDING_TYPE)
    subjects = {f["subject"] for f in reported}
    assert "001-demo/NFR-001" in subjects, (
        "un requisito attivo che non raggiunge 'tested' deve produrre un finding: "
        f"tipi aperti trovati = {sorted({f['finding_type'] for f in open_findings(project) if f['status'] == 'open'})}"
    )
    assert all(f["severity"] == "high" for f in reported)


def test_requirement_with_no_evidence_at_all_is_reported(cli, project: Path):
    """Il caso della riproduzione originale: requisito scritto e nient'altro."""
    spec = project / "specs" / "001-demo" / "spec.md"
    spec.write_text(
        spec.read_text(encoding="utf-8").replace(
            "- **NFR-001**: la risposta deve arrivare entro 100ms",
            "- **NFR-001**: la risposta deve arrivare entro 100ms\n"
            "- **FR-002**: il sistema deve cifrare le password a riposo",
        ),
        encoding="utf-8",
    )
    cli("init")

    assert lifecycle(project, "FR-002") == "defined"
    assert "001-demo/FR-002" in {f["subject"] for f in open_of_type(project, FINDING_TYPE)}


def test_strict_refresh_exits_2_when_a_requirement_is_unverified(cli, project: Path):
    cli("init")
    cli("refresh", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)


def test_gate_4_is_not_approvable_with_an_unverified_requirement(cli, project: Path):
    """Il cuore del difetto: i quattro gate passavano tutti."""
    write_plan(project)
    cli("init")
    for gate in ("1", "2", "3"):
        cli("gate", "approve", "001-demo", gate, "--actor", "utente", "--reason", "baseline")

    cli("gate", "approve", "001-demo", "4", "--actor", "utente", "--reason", "rilascio",
        expect=ExitCode.QUALITY_GATE_FAILED)


# -- Le vie d'uscita legittime --------------------------------------------
def test_waiver_unblocks_gate_4(cli, project: Path):
    """Rinviare un requisito resta possibile, ma lascia un record con attore e motivo."""
    write_plan(project)
    cli("init")
    make_tested(cli, project, "001-demo/FR-001", "TEST-001")

    for finding in open_of_type(project, FINDING_TYPE):
        cli("finding", "waive", finding["finding_id"], "--actor", "utente",
            "--reason", "NFR-001 rinviato alla prossima release, deciso con lo sponsor")
    cli("refresh")

    for gate in ("1", "2", "3", "4"):
        cli("gate", "approve", "001-demo", gate, "--actor", "utente", "--reason", f"gate {gate}")

    decisions = [
        json.loads(line)
        for line in (project / "requirement-burnup" / "state" / "gate-decisions.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    gate4 = [d for d in decisions if d["gate"] == 4][-1]
    assert gate4["outcome"] == "approved"
    assert gate4["waivers"], "l'approvazione deve citare il waiver che l'ha resa possibile"


def test_removing_a_requirement_from_scope_clears_the_finding(cli, project: Path):
    """L'altra via d'uscita gia' prevista dal framework: decisione di scope."""
    cli("init")
    cli("requirement", "remove", "001-demo/NFR-001", "--actor", "utente",
        "--reason", "fuori perimetro per questa release")
    cli("refresh")

    assert "001-demo/NFR-001" not in {f["subject"] for f in open_of_type(project, FINDING_TYPE)}


# -- Nessun falso positivo -------------------------------------------------
def test_no_finding_when_every_requirement_is_tested(cli, project: Path, commit):
    """Il finding deve sparire da solo quando l'evidenza c'e': e' una funzione
    dello stato corrente, non una macchina a stati che va riazzerata a mano."""
    tasks = project / "specs" / "001-demo" / "tasks.md"
    tasks.write_text(
        "# Task\n\n"
        "- [x] T001 [REQ:FR-001] Implement auth in src/auth.py\n"
        "- [x] T002 [REQ:NFR-001] Tune latency in src/auth.py\n",
        encoding="utf-8",
    )
    source = project / "src" / "auth.py"
    source.write_text(
        '"""Modulo di autenticazione."""\n'
        "# REQ: 001-demo/FR-001\n"
        "def auth():\n"
        "    return True\n\n"
        "# REQ: 001-demo/NFR-001\n"
        "def fast():\n"
        "    return True\n",
        encoding="utf-8",
    )
    cli("init")
    make_tested(cli, project, "001-demo/FR-001", "TEST-001")
    make_tested(cli, project, "001-demo/NFR-001", "TEST-002")

    assert lifecycle(project, "FR-001") == "tested"
    assert lifecycle(project, "NFR-001") == "tested"
    assert open_of_type(project, FINDING_TYPE) == []
    commit("feature completa")
    cli("refresh", "--strict")


def test_finding_reopens_when_evidence_regresses(cli, project: Path):
    """Il segnale non deve essere transitorio come `requirement-changed`, che
    si chiude al refresh successivo: finche' il requisito non e' verificato,
    il finding resta aperto."""
    cli("init")
    make_tested(cli, project, "001-demo/FR-001", "TEST-001")
    assert "001-demo/FR-001" not in {f["subject"] for f in open_of_type(project, FINDING_TYPE)}

    spec = project / "specs" / "001-demo" / "spec.md"
    spec.write_text(
        spec.read_text(encoding="utf-8").replace(
            "il sistema deve autenticare l'utente",
            "il sistema deve cancellare tutti i dati dell'utente al logout",
        ),
        encoding="utf-8",
    )
    cli("refresh")
    cli("refresh")  # `requirement-changed` si chiude qui; questo no

    assert "001-demo/FR-001" in {f["subject"] for f in open_of_type(project, FINDING_TYPE)}
    cli("refresh", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)
