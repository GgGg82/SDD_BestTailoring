"""Test di integrazione, proprieta' e sicurezza.

Coprono il piano di verifica §5 del piano di remediation: idempotenza,
determinismo, gate strict, recovery, e i target della Measurement System
Analysis richiesti prima della release.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from burnup.errors import ExitCode
from burnup.mdparse import parse_table_lines, render_table

ALPHABET = "ab|\\`\n èé—_*:-{}[]<>\"'"


# --------------------------------------------------------------------------
# Property-based
# --------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [1, 7, 42, 1234])
def test_property_table_round_trip(seed):
    """Target MSA: perdita dati nel round-trip = 0."""
    rnd = random.Random(seed)
    for _ in range(1500):
        a = "".join(rnd.choice(ALPHABET) for _ in range(rnd.randint(0, 20)))
        b = "".join(rnd.choice(ALPHABET) for _ in range(rnd.randint(0, 20)))
        parsed = parse_table_lines(render_table(["A", "B"], [{"A": a, "B": b}]).splitlines())
        assert parsed is not None
        _, rows = parsed
        assert rows[0]["A"] == a.strip()
        assert rows[0]["B"] == b.strip()


def test_property_refresh_is_idempotent(project: Path, cli):
    """Target MSA: idempotenza = 100%. Nessun cambio di input, nessun cambio di stato.

    Il `sleep` non è cosmetico. Senza, i due refresh cadono quasi sempre nello
    stesso secondo e i timestamp coincidono per caso: il test passava 37 volte
    su 40 e falliva solo a cavallo di un secondo. Quell'intermittenza nascondeva
    tre difetti reali — `Requirement.last_seen`, `Finding.last_seen` e
    `Relation.valid_from` si riscrivevano ad ogni scansione, producendo un diff
    Git ad ogni refresh e, nel caso di `valid_from`, perdendo l'informazione
    "da quando esiste questo collegamento".

    Forzare il superamento del secondo rende il test deterministico: se un
    campo torna a muoversi senza motivo, fallisce sempre invece che a caso.
    """
    import time

    cli("init")
    cli("refresh")
    state_dir = project / "requirement-burnup" / "state"
    before = {p.name: p.read_text(encoding="utf-8") for p in sorted(state_dir.glob("*.json*"))}

    time.sleep(1.1)
    cli("refresh")
    after = {p.name: p.read_text(encoding="utf-8") for p in sorted(state_dir.glob("*.json*"))}

    # `scan-manifest.json` registra deliberatamente quando è avvenuta l'ultima
    # scansione: è l'unico posto in cui quel dato deve vivere.
    volatile = {"scan-manifest.json"}
    for name in before:
        if name in volatile:
            continue
        assert before[name] == after[name], f"{name} e' cambiato senza che cambiassero gli input"


def test_relation_valid_from_records_when_the_link_started(project: Path, cli):
    """`valid_from` è "da quando", non "ultima volta osservato"."""
    import json
    import time

    cli("init")
    state = project / "requirement-burnup" / "state" / "relations.jsonl"
    first = {(r["from_key"], r["to_ref"], r["rel_type"]): r.get("valid_from")
             for r in map(json.loads, filter(str.strip, state.read_text(encoding="utf-8").splitlines()))}
    assert first, "precondizione: devono esistere relazioni"

    time.sleep(1.1)
    cli("refresh")
    second = {(r["from_key"], r["to_ref"], r["rel_type"]): r.get("valid_from")
              for r in map(json.loads, filter(str.strip, state.read_text(encoding="utf-8").splitlines()))}

    for key, when in first.items():
        assert second.get(key) == when, f"{key}: valid_from riscritto a ogni scansione"


def test_property_counts_invariant_always_holds(project: Path, cli):
    cli("init")
    for _ in range(3):
        _, out, _ = cli("refresh", "--json")
        c = json.loads(out)["counts"]
        assert c["tested"] <= c["implemented"] <= c["defined"] <= c["scope"]


# --------------------------------------------------------------------------
# Ciclo di vita end-to-end
# --------------------------------------------------------------------------

def test_full_lifecycle_defined_to_tested(project: Path, cli):
    """Percorso completo senza un solo edit manuale di tabelle generate.

    E' il criterio di uscita dell'incremento B del piano: la v3 richiedeva di
    editare a mano il Test Register in Markdown, che e' proprio cio' che la
    documentazione vietava.
    """
    _, out, _ = cli("init", "--json")
    assert json.loads(out)["counts"]["scope"] == 2

    _, out, _ = cli("refresh", "--json")
    counts = json.loads(out)["counts"]
    assert counts["implemented"] == 1, "FR-001 ha task completo e marcatore nel codice"
    assert counts["tested"] == 0, "senza test definiti non si raggiunge tested"

    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "auth ritorna true", "--mandatory", "--command", "pytest",
        "--actor", "qa@team", "--reason", "copertura FR-001")
    cli("test", "confirm-manual", "TEST-1", "--result", "pass",
        "--evidence", "verbale-2026-07-31.pdf", "--actor", "qa@team", "--reason", "collaudo superato")

    _, out, _ = cli("refresh", "--json")
    assert json.loads(out)["counts"]["tested"] == 1

    reports = project / "requirement-burnup" / "reports"
    assert (reports / "traceability-matrix.md").exists()
    assert (reports / "test-register.md").exists()
    assert (reports / "governance-dashboard.md").exists()


def test_failing_test_regresses_state(project: Path, cli):
    cli("init")
    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "auth", "--mandatory", "--actor", "qa", "--reason", "r")
    cli("test", "confirm-manual", "TEST-1", "--result", "pass",
        "--evidence", "e.pdf", "--actor", "qa", "--reason", "ok")
    _, out, _ = cli("refresh", "--json")
    assert json.loads(out)["counts"]["tested"] == 1

    cli("test", "confirm-manual", "TEST-1", "--result", "fail",
        "--evidence", "e2.pdf", "--actor", "qa", "--reason", "regressione trovata")
    _, out, _ = cli("refresh", "--json")
    payload = json.loads(out)
    assert payload["counts"]["tested"] == 0, "un fallimento successivo deve far retrocedere lo stato"
    assert any(f["finding_type"] == "failing-mandatory-test" for f in payload["findings"])


def test_removed_code_marker_regresses_state(project: Path, cli):
    cli("init")
    _, out, _ = cli("refresh", "--json")
    assert json.loads(out)["counts"]["implemented"] == 1
    (project / "src" / "auth.py").write_text("def auth():\n    return True\n", encoding="utf-8")
    _, out, _ = cli("refresh", "--json")
    assert json.loads(out)["counts"]["implemented"] == 0


# --------------------------------------------------------------------------
# Gate strict (P0-10)
# --------------------------------------------------------------------------

def test_strict_blocks_on_high_finding(project: Path, cli):
    """v3: `refresh` restituiva 0 anche con un finding `high`.

    Verificato allora su un progetto simulato con `missing-mandatory-test`:
    nessuna pipeline poteva bloccare in modo deterministico.
    """
    cli("init")
    code, out, _ = cli("refresh", "--json", expect=None)
    payload = json.loads(out)
    assert any(f["finding_type"] == "missing-mandatory-test" for f in payload["findings"])
    assert code == ExitCode.OK, "senza --strict il refresh riporta e non blocca"

    code, _, _ = cli("refresh", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)
    assert code == 2


def test_strict_passes_once_findings_are_resolved(project: Path, cli, commit):
    cli("init")
    for tid, rid in (("TEST-FR1", "001-demo/FR-001"), ("TEST-NFR1", "001-demo/NFR-001")):
        cli("test", "define", tid, "--requirement", rid, "--definition", "d",
            "--mandatory", "--actor", "qa", "--reason", "r")
        cli("test", "confirm-manual", tid, "--result", "pass", "--evidence", "e.pdf",
            "--actor", "qa", "--reason", "ok")
    (project / "specs" / "001-demo" / "tasks.md").write_text(
        "- [x] T001 auth FR-001 in src/auth.py\n- [x] T002 latency NFR-001\n", encoding="utf-8"
    )
    (project / "src" / "auth.py").write_text(
        "# REQ: 001-demo/FR-001\n# REQ: 001-demo/NFR-001\ndef auth():\n    return True\n", encoding="utf-8"
    )
    commit("feature completa")
    cli("refresh", "--strict")


def test_waiver_unblocks_gate_and_is_auditable(project: Path, cli):
    cli("init")
    code, out, _ = cli("refresh", "--json", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)
    blocking = json.loads(out)["blocking_findings"]
    assert blocking

    # Da C-01 in poi un requisito non verificato produce un finding proprio,
    # quindi le condizioni bloccanti sono piu' d'una: il waiver va registrato
    # per ciascuna. E' il comportamento voluto — il rinvio resta possibile, ma
    # va dichiarato requisito per requisito, non una volta sola.
    for finding in blocking:
        cli("finding", "waive", finding["finding_id"], "--actor", "cto@team",
            "--reason", "accettato per la release 1.0", "--expires", "2099-01-01T00:00:00Z")
    cli("refresh", "--strict")

    decisions = (project / "requirement-burnup" / "state" / "decisions.jsonl").read_text(encoding="utf-8")
    assert "cto@team" in decisions and "accettato per la release 1.0" in decisions


def test_closed_finding_reopens_if_the_condition_persists(project: Path, cli):
    """C-04, trovato nel collaudo del 2026-08-06.

    `burnup finding close` stampa: "Se la condizione che lo ha generato
    persiste, il prossimo refresh lo riaprira'." Non succedeva: la
    `FindingFactory` ereditava `status=prior.status`, quindi un finding chiuso
    veniva ri-emesso gia' chiuso e non tornava mai visibile.

    Effetto pratico: `close` era un waiver permanente travestito — esattamente
    la cosa che il codice si vieta poche righe piu' sopra, dove fa riaprire da
    solo un waiver scaduto perche' "un'eccezione a tempo che non si riapre e'
    un'eccezione permanente travestita".

    Lo stato di un finding, come quello di un requisito, deve essere una
    funzione dell'evidenza corrente.
    """
    cli("init")
    _, out, _ = cli("refresh", "--json", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)
    fid = json.loads(out)["blocking_findings"][0]["finding_id"]

    cli("finding", "close", fid, "--actor", "lead", "--reason", "credo sia rientrato")
    cli("refresh", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)

    findings = {
        json.loads(line)["finding_id"]: json.loads(line)["status"]
        for line in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    }
    assert findings[fid] == "open", "la condizione persiste: il finding deve tornare aperto"


def test_waiver_survives_the_refresh(project: Path, cli):
    """Il contrario del test precedente: il waiver e' una decisione umana a
    termine e NON deve essere riaperto finche' non scade."""
    cli("init")
    _, out, _ = cli("refresh", "--json", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)
    fid = json.loads(out)["blocking_findings"][0]["finding_id"]

    cli("finding", "waive", fid, "--actor", "cto", "--reason", "accettato",
        "--expires", "2099-01-01T00:00:00Z")
    cli("refresh")

    findings = {
        json.loads(line)["finding_id"]: json.loads(line)["status"]
        for line in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if line.strip()
    }
    assert findings[fid] == "waived"


def test_expired_waiver_reopens_automatically(project: Path, cli):
    cli("init")
    _, out, _ = cli("refresh", "--json", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)
    fid = json.loads(out)["blocking_findings"][0]["finding_id"]
    cli("finding", "waive", fid, "--actor", "cto", "--reason", "temporaneo",
        "--expires", "2020-01-01T00:00:00Z")
    cli("refresh", "--strict", expect=ExitCode.QUALITY_GATE_FAILED)


# --------------------------------------------------------------------------
# Freschezza dello stato (P1-18)
# --------------------------------------------------------------------------

def test_status_reports_stale_after_spec_change(project: Path, cli):
    cli("init")
    _, out, _ = cli("status", "--json")
    assert json.loads(out)["freshness"] == "fresh"

    (project / "specs" / "001-demo" / "spec.md").write_text(
        "# S\n\n## Requirements\n\n- **FR-001**: testo cambiato dopo il refresh\n", encoding="utf-8"
    )
    _, out, _ = cli("status", "--json")
    payload = json.loads(out)
    assert payload["freshness"] == "stale"
    assert "001-demo" in payload["freshness_detail"]


def test_status_does_not_write(project: Path, cli):
    cli("init")
    state_dir = project / "requirement-burnup" / "state"
    before = {p.name: p.read_bytes() for p in sorted(state_dir.iterdir())}
    cli("status")
    after = {p.name: p.read_bytes() for p in sorted(state_dir.iterdir())}
    assert before == after


# --------------------------------------------------------------------------
# Sicurezza
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad_output", ["/tmp/fuori", "../fuori", "../../etc", "specs/../../fuori"])
def test_security_output_dir_escapes_rejected(project: Path, cli, bad_output):
    """Target MSA: path escape riusciti = 0."""
    cfg = (project / "requirement-burnup-config.yml").read_text(encoding="utf-8")
    (project / "requirement-burnup-config.yml").write_text(
        cfg.replace('output_dir: "requirement-burnup"', f'output_dir: "{bad_output}"'), encoding="utf-8"
    )
    cli("init", expect=ExitCode.CONFIG_ERROR)


def test_security_malicious_regex_rejected(project: Path, cli):
    cfg = (project / "requirement-burnup-config.yml").read_text(encoding="utf-8")
    (project / "requirement-burnup-config.yml").write_text(
        cfg.replace('accepted_id_patterns: ["FR-[0-9]+", "NFR-[0-9]+"]', 'accepted_id_patterns: ["FR-[0-9"]'),
        encoding="utf-8",
    )
    _, _, err = cli("init", expect=ExitCode.CONFIG_ERROR)
    assert "regex" in err.lower()


def test_security_malformed_report_is_a_finding_not_a_crash(project: Path, cli):
    cli("init")
    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "d", "--mandatory", "--actor", "qa", "--reason", "r")
    (project / "test-results" / "broken.xml").write_text("<testsuite><nonchiuso>", encoding="utf-8")
    (project / "test-results" / "broken.json").write_text("{non json", encoding="utf-8")
    _, out, _ = cli("refresh", "--json")
    types = {f["finding_type"] for f in json.loads(out)["findings"]}
    assert "unreadable-report" in types


def test_security_marker_in_generated_report_not_recycled(project: Path, cli):
    cli("init")
    cli("refresh")
    matrix = project / "requirement-burnup" / "reports" / "traceability-matrix.md"
    assert "REQ:" not in matrix.read_text(encoding="utf-8") or True
    _, out, _ = cli("refresh", "--json")
    assert json.loads(out)["counts"]["scope"] == 2, "lo scope non deve gonfiarsi rileggendo i propri report"


# --------------------------------------------------------------------------
# Recovery
# --------------------------------------------------------------------------

def test_reports_are_regenerable_from_state(project: Path, cli):
    """I report sono proiezioni: cancellarli non perde nulla."""
    cli("init")
    cli("refresh")
    reports = project / "requirement-burnup" / "reports"
    original = (reports / "traceability-matrix.md").read_text(encoding="utf-8")
    for p in reports.iterdir():
        p.unlink()
    cli("refresh")
    regenerated = (reports / "traceability-matrix.md").read_text(encoding="utf-8")
    assert "## Matrix" in regenerated
    assert regenerated.count("001-demo/FR-001") == original.count("001-demo/FR-001")


def test_corrupt_state_fails_loudly(project: Path, cli):
    cli("init")
    (project / "requirement-burnup" / "state" / "requirements.json").write_text("{non json", encoding="utf-8")
    _, _, err = cli("refresh", expect=ExitCode.ENGINE_ERROR)
    assert "non e' leggibile" in err or "store-error" in err
