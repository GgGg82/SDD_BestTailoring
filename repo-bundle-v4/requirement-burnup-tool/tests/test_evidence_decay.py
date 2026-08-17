"""C-02: l'evidenza di test deve decadere quando il requisito cambia significato.

Difetto trovato nel collaudo end-to-end del 2026-08-06.

`STATUS-RULES.md` apre con il principio che ha motivato l'intera riscrittura v4:

    L'evidenza vale solo se si riferisce al fingerprint corrente del requisito.

Non era vero per l'evidenza di test. Riproduzione:

    PRIMA:  FR-001 = tested
       verified-by -> TEST-001   fp adecc05d17

      "il sistema deve autenticare l'utente"
            ->  "il sistema deve cancellare tutti i dati al logout"

    DOPO:   FR-001 = tested      <- invariato
       verified-by -> TEST-001   fp 7b8bace442   <- ristampata

Il requisito diceva l'opposto di prima e restava verificato.

Causa: la relazione `verified-by` veniva ricostruita ad ogni refresh a partire
dalla definizione del test e ristampata con il fingerprint CORRENTE, quindi non
poteva mai risultare stantia. A poche righe di distanza il codice applicava
invece il criterio giusto alle relazioni confermate a mano, preservate solo
`if rel.requirement_fingerprint == req.fingerprint`.

Il probe originale dell'audit sembrava superato solo perche' cancellava anche
task e marcatore nel codice: la regressione veniva da quelli.

Rimedio: `TestDefinition` registra il fingerprint del requisito al momento di
`burnup test define`. La relazione `verified-by` viene creata solo quando quel
fingerprint combacia con quello corrente; altrimenti decade e viene emesso
`test-definition-stale`. Riscrivere un requisito obbliga quindi a riconfermarne
i test — che e' esattamente cio' che STATUS-RULES.md dichiara di volere.
"""
from __future__ import annotations

import json
from pathlib import Path

from burnup.errors import ExitCode

REWRITE = ("il sistema deve autenticare l'utente",
           "il sistema deve cancellare tutti i dati dell'utente al logout")


def lifecycle(project: Path, requirement_id: str) -> str:
    path = project / "requirement-burnup" / "state" / "requirements.json"
    for req in json.loads(path.read_text(encoding="utf-8")):
        if req["requirement_id"] == requirement_id:
            return req["lifecycle_state"]
    raise AssertionError(f"requisito {requirement_id} non trovato")


def open_types(project: Path) -> set[str]:
    path = project / "requirement-burnup" / "state" / "findings.jsonl"
    return {
        json.loads(line)["finding_type"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line)["status"] == "open"
    }


def relations(project: Path, rel_type: str) -> list[dict]:
    path = project / "requirement-burnup" / "state" / "relations.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line)["rel_type"] == rel_type
    ]


def verify(cli, requirement: str = "001-demo/FR-001", test_id: str = "TEST-001") -> None:
    cli("test", "define", test_id, "--actor", "ba-qa", "--reason", "collaudo",
        "--requirement", requirement, "--definition", f"verifica {requirement}", "--mandatory")
    cli("test", "confirm-manual", test_id, "--actor", "ba-qa", "--reason", "eseguito",
        "--result", "pass", "--evidence", "verbale")
    cli("refresh")


def rewrite_requirement(project: Path) -> None:
    spec = project / "specs" / "001-demo" / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace(*REWRITE), encoding="utf-8")


# -- Il difetto ------------------------------------------------------------
def test_rewriting_a_requirement_invalidates_its_test_evidence(cli, project: Path):
    """Il probe che ha motivato la v4, isolato: cambia SOLO il testo.

    `tasks.md` e il marcatore nel codice restano intatti perche' citano l'ID,
    non il testo. Prima del fix bastava questo a far sopravvivere lo stato
    `tested`.
    """
    cli("init")
    verify(cli)
    assert lifecycle(project, "FR-001") == "tested"

    rewrite_requirement(project)
    cli("refresh")

    assert lifecycle(project, "FR-001") != "tested", (
        "un requisito riscritto di significato non puo' restare verificato "
        "da un test eseguito sul testo precedente"
    )


def test_stale_test_definition_is_reported(cli, project: Path):
    cli("init")
    verify(cli)
    rewrite_requirement(project)
    cli("refresh")

    assert "test-definition-stale" in open_types(project)


def test_verified_by_relation_keeps_the_fingerprint_of_its_moment(cli, project: Path):
    """La relazione non deve essere ristampata: e' il campo che la fa decadere."""
    cli("init")
    verify(cli)
    before = relations(project, "verified-by")
    assert before, "la relazione deve esistere quando il requisito e' verificato"
    original = before[0]["requirement_fingerprint"]

    rewrite_requirement(project)
    cli("refresh")

    current = [r for r in relations(project, "verified-by")]
    assert all(r["requirement_fingerprint"] == original for r in current), (
        "la relazione non deve essere ristampata con il fingerprint nuovo"
    )


def test_strict_and_gate_4_react_to_the_regression(cli, project: Path, commit):
    (project / "specs" / "001-demo" / "plan.md").write_text("# Plan\n", encoding="utf-8")
    tasks = project / "specs" / "001-demo" / "tasks.md"
    tasks.write_text(
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
    cli("init")
    verify(cli)
    verify(cli, "001-demo/NFR-001", "TEST-002")
    commit("feature completa")
    cli("refresh", "--strict")

    rewrite_requirement(project)
    cli("refresh", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)


# -- Riconferma ------------------------------------------------------------
def test_redefining_the_test_restores_verification(cli, project: Path):
    """La via d'uscita: riaffermare che il test verifica il requisito NUOVO."""
    cli("init")
    verify(cli)
    rewrite_requirement(project)
    cli("refresh")
    assert lifecycle(project, "FR-001") != "tested"

    cli("test", "define", "TEST-001", "--actor", "ba-qa", "--replace",
        "--reason", "il test copre anche il comportamento riscritto",
        "--requirement", "001-demo/FR-001", "--definition", "verifica FR-001", "--mandatory")
    cli("test", "confirm-manual", "TEST-001", "--actor", "ba-qa", "--reason", "rieseguito",
        "--result", "pass", "--evidence", "verbale-2")
    cli("refresh")

    assert lifecycle(project, "FR-001") == "tested"
    assert "test-definition-stale" not in open_types(project)


def test_reformatting_does_not_invalidate_evidence(cli, project: Path):
    """Nessun falso positivo: la normalizzazione assorbe le variazioni tipografiche.

    STATUS-RULES: "riformattare una spec non invalida l'evidenza; riscriverne
    il significato si'."
    """
    cli("init")
    verify(cli)
    spec = project / "specs" / "001-demo" / "spec.md"
    spec.write_text(
        spec.read_text(encoding="utf-8").replace(
            "- **FR-001**: il sistema deve autenticare l'utente",
            "- **FR-001**:   il sistema deve *autenticare* l'utente.",
        ),
        encoding="utf-8",
    )
    cli("refresh")

    assert lifecycle(project, "FR-001") == "tested"
    assert "test-definition-stale" not in open_types(project)
