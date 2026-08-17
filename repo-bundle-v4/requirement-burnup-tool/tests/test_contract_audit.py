"""Secondo giro di collaudo (2026-08-07): il contratto dichiarato deve essere vero.

Metodo, nato dal primo giro: i difetti non stavano nelle funzioni ma negli
scostamenti fra cio' che il sistema **dichiara** e cio' che **fa**. Qui ogni
test prende una promessa scritta — nel template di configurazione, in un
messaggio della CLI, in un documento normativo — e la verifica.

Difetti chiusi da questo file:

* **C-05** — messaggi che rimandano a comandi inesistenti (`burnup migrate`,
  `burnup migrate-config`).
* **C-06** — `requirements.default_scope_state` documentato e ignorato. E' uno
  dei cinque campi che il template dichiara di aver corretto rispetto alla v3
  (P1-07): "Se un campo compare in questo template, ha effetto". La v4 ne aveva
  corretti quattro su cinque.
* **C-07** — l'ora di esecuzione JUnit veniva letta solo dall'elemento radice.
  Con `<testsuites>` come radice — la forma che producono pytest e la maggior
  parte dei CI — il `timestamp` sta sul `<testsuite>` figlio e veniva ignorato,
  quindi nessun report era importabile senza sidecar. TEST-REGISTER-SPEC.md
  prescrive: "testcase@timestamp -> testsuite@timestamp -> sidecar".
* **C-08** — `ExitCode.USAGE_ERROR = 4` definito e mai usato: ogni errore d'uso
  usciva con 2, che il contratto riserva a "quality gate fallito". Una pipeline
  non poteva distinguere un refuso da un gate respinto.
* **C-09** — `definition` dichiarato obbligatorio in TEST-REGISTER-SPEC, ma la
  stringa vuota veniva accettata.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from burnup.cli import build_parser, main
from burnup.errors import ExitCode

JUNIT_TS = "2026-08-06T10:00:00"


def _run(project: Path, *argv: str) -> int:
    import contextlib
    import io

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            return main(list(argv) + ["--project-root", str(project)])
        except SystemExit as exc:  # argparse
            return int(exc.code or 0)


def _runs(project: Path) -> list[dict]:
    path = project / "requirement-burnup" / "state" / "test-runs.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _requirements(project: Path) -> list[dict]:
    path = project / "requirement-burnup" / "state" / "requirements.json"
    return json.loads(path.read_text(encoding="utf-8"))


# -- C-05 -----------------------------------------------------------------
def test_no_message_points_to_a_command_that_does_not_exist():
    """Un suggerimento che rimanda a un comando inesistente è peggio di nessun
    suggerimento: manda l'utente a sbattere invece di lasciarlo cercare."""
    import ast
    import re

    source = Path(__file__).resolve().parent.parent / "burnup"
    parser = build_parser()
    esposti = set()
    for action in parser._actions:
        if getattr(action, "choices", None) and isinstance(action.choices, dict):
            for nome, sub in action.choices.items():
                esposti.add(nome)
                for sub_action in sub._actions:
                    if getattr(sub_action, "choices", None) and isinstance(sub_action.choices, dict):
                        esposti.update(f"{nome} {c}" for c in sub_action.choices)

    # Solo le stringhe che possono arrivare all'utente: i commenti del codice
    # parlano anche di comandi che deliberatamente non esistono.
    citati: set[str] = set()
    for path in source.glob("*.py"):
        albero = ast.parse(path.read_text(encoding="utf-8"))
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                for match in re.findall(r"burnup ([a-z][a-z-]*(?: [a-z][a-z-]*)?)", nodo.value):
                    citati.add(match.strip())

    inesistenti = {
        c for c in citati
        if c not in esposti and c.split()[0] not in esposti
    }
    assert not inesistenti, f"comandi citati nei messaggi ma non esposti dalla CLI: {sorted(inesistenti)}"


def test_store_schema_mismatch_suggests_something_executable(project: Path, cli):
    cli("init")
    (project / "requirement-burnup" / "state" / "schema-version.json").write_text(
        '{"schema_version": "1.0"}', encoding="utf-8"
    )
    _, _, err = cli("refresh", expect=ExitCode.ENGINE_ERROR)
    assert "migrate" not in err, "non promettere una migrazione che non esiste"
    assert "init --reset" in err


# -- C-06 -----------------------------------------------------------------
def test_default_scope_state_has_effect(project: Path, cli):
    """Il template promette: "Se un campo compare in questo template, ha effetto"."""
    config = project / "requirement-burnup-config.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "requirements:", 'requirements:\n  default_scope_state: "removed"'
        ),
        encoding="utf-8",
    )
    cli("init")

    stati = {r["requirement_id"]: r["scope_state"] for r in _requirements(project)}
    assert stati and set(stati.values()) == {"removed"}, (
        f"default_scope_state non applicato ai requisiti nuovi: {stati}"
    )


def test_default_scope_state_does_not_override_a_human_decision(project: Path, cli):
    """Una decisione registrata vale piu' di un default di configurazione."""
    cli("init")
    cli("requirement", "remove", "001-demo/NFR-001", "--actor", "u", "--reason", "fuori perimetro")
    cli("refresh")
    stati = {r["requirement_id"]: r["scope_state"] for r in _requirements(project)}
    assert stati["FR-001"] == "active"
    assert stati["NFR-001"] == "removed"


# -- C-07 -----------------------------------------------------------------
@pytest.mark.parametrize(
    "xml,label",
    [
        (
            f'<?xml version="1.0"?><testsuites><testsuite name="s" timestamp="{JUNIT_TS}">'
            '<testcase classname="c" name="TEST-1_login" time="0.1"/></testsuite></testsuites>',
            "timestamp sul <testsuite> dentro <testsuites> (pytest)",
        ),
        (
            f'<?xml version="1.0"?><testsuite name="s" timestamp="{JUNIT_TS}">'
            '<testcase classname="c" name="TEST-1_login" time="0.1"/></testsuite>',
            "<testsuite> come radice",
        ),
        (
            '<?xml version="1.0"?><testsuites><testsuite name="s">'
            f'<testcase classname="c" name="TEST-1_login" time="0.1" timestamp="{JUNIT_TS}"/>'
            "</testsuite></testsuites>",
            "timestamp sul <testcase>",
        ),
    ],
)
def test_junit_execution_time_is_read_from_every_documented_position(project: Path, cli, xml, label):
    """TEST-REGISTER-SPEC: "testcase@timestamp -> testsuite@timestamp -> sidecar"."""
    (project / "test-results" / "j.xml").write_text(xml, encoding="utf-8")
    cli("init")
    cli("test", "define", "TEST-1", "--actor", "qa", "--reason", "r",
        "--requirement", "001-demo/FR-001", "--definition", "d", "--mandatory")
    cli("refresh")

    runs = _runs(project)
    assert len(runs) == 1, f"report non importato — {label}"
    assert runs[0]["executed_at"].startswith("2026-08-06T10:00:00")


def test_junit_without_any_timestamp_is_still_rejected(project: Path, cli):
    """Nessun fallback inventato: senza ora dichiarata il risultato si scarta."""
    (project / "test-results" / "j.xml").write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="s">'
        '<testcase classname="c" name="TEST-1_login"/></testsuite></testsuites>',
        encoding="utf-8",
    )
    cli("init")
    cli("test", "define", "TEST-1", "--actor", "qa", "--reason", "r",
        "--requirement", "001-demo/FR-001", "--definition", "d", "--mandatory")
    cli("refresh")

    assert _runs(project) == []
    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "missing-execution-timestamp" in tipi


# -- C-08 -----------------------------------------------------------------
@pytest.mark.parametrize(
    "argv,label",
    [
        (["comando-inesistente"], "sottocomando inesistente"),
        (["refresh", "--flag-inventato"], "flag sconosciuto"),
        (["test", "define", "T1", "--kind", "inventato"], "valore fuori enum"),
    ],
)
def test_usage_errors_do_not_collide_with_the_quality_gate_code(project: Path, argv, label):
    """Exit code 2 significa "quality gate fallito", ed è contratto pubblico.

    Un refuso sulla riga di comando non deve essere indistinguibile da un gate
    respinto: in una pipeline la differenza è fra "il codice non è pronto" e
    "hai sbagliato a scrivere".
    """
    code = _run(project, *argv)
    assert code == ExitCode.USAGE_ERROR, f"{label}: atteso {ExitCode.USAGE_ERROR}, ottenuto {code}"


# -- C-09 -----------------------------------------------------------------
def test_test_definition_requires_a_definition(project: Path, cli):
    """TEST-REGISTER-SPEC: `definition` | "obbligatorio: cosa si verifica e
    qual è l'esito atteso". Un catalogo di test senza criterio di esito è un
    elenco di nomi."""
    cli("init")
    cli("test", "define", "TEST-1", "--actor", "qa", "--reason", "r",
        "--requirement", "001-demo/FR-001", "--definition", "   ",
        expect=ExitCode.CONFIG_ERROR)


def test_test_definition_accepts_a_real_definition(project: Path, cli):
    cli("init")
    cli("test", "define", "TEST-1", "--actor", "qa", "--reason", "r",
        "--requirement", "001-demo/FR-001",
        "--definition", "l'utente autenticato riceve un token valido per 24h")
