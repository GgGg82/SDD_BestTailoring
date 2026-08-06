"""I 23 probe dell'Appendix A dell'audit, come test di regressione permanenti.

Ogni test qui riproduce un difetto verificato sulla v3 e ne asserisce il
comportamento CORRETTO. Se uno di questi torna rosso, una regressione ha
riaperto un difetto gia' chiuso.

Riferimento: SDD_MULTI_AGENT_FRAMEWORK_V3_FULL_AUDIT.md, Appendix A.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from burnup.errors import ExitCode, PathConfinementError, SpecsLayoutError
from burnup.fingerprint import requirement_fingerprint, scope_fingerprint
from burnup.ids import finding_id, run_id, run_identity
from burnup.ingest import latest_run_by_test, resolve_test_id
from burnup.mdparse import parse_document, parse_table_lines, read_text, render_table
from burnup.models import TestRun
from burnup.paths import expand_globs, resolve_under_root
from burnup.risk_link import parse_id_list, read_open_risks
from burnup.specscan import detect_specs_root, discover_features, extract_requirements, link_code_evidence, link_tasks
from conftest import make_config


# -- Probe 1 ---------------------------------------------------------------
def test_probe_01_escaped_pipe_round_trip():
    """v3: `alpha | beta` rientrava come {'A': 'alpha \\', 'B': 'beta'} — dato perso."""
    rows = [{"A": "alpha | beta", "B": "intatto"}]
    parsed = parse_table_lines(render_table(["A", "B"], rows).splitlines())
    assert parsed is not None
    _, got = parsed
    assert got[0]["A"] == "alpha | beta"
    assert got[0]["B"] == "intatto", "il contenuto non deve slittare nella colonna successiva"


@pytest.mark.parametrize("value", ["a|b", "a\\b", "a\\|b", "`x|y`", "|", "\\", "a\nb", "—", ""])
def test_probe_01b_round_trip_hostile_values(value):
    parsed = parse_table_lines(render_table(["A", "B"], [{"A": value, "B": "z"}]).splitlines())
    _, got = parsed
    assert got[0]["A"] == value.strip()
    assert got[0]["B"] == "z"


# -- Probe 2 ---------------------------------------------------------------
def test_probe_02_crlf_and_bom_frontmatter(tmp_path: Path):
    """v3: il probe dell'audit accusava il CRLF, ma il difetto reale era il BOM.

    Il CRLF non si riproduceva nel percorso reale, perche' `read_text()`
    normalizza i newline. Il BOM invece rompeva davvero il match del
    frontmatter. Entrambi devono funzionare.
    """
    crlf = tmp_path / "crlf.md"
    crlf.write_bytes("---\r\nkey: v\r\n---\r\n# corpo\r\n".encode())
    assert "key: v" in parse_document(read_text(crlf)).frontmatter_raw

    bom = tmp_path / "bom.md"
    bom.write_bytes("﻿---\nkey: v\n---\n# corpo\n".encode("utf-8"))
    assert "key: v" in parse_document(read_text(bom)).frontmatter_raw


# -- Probe 3 e 23 ----------------------------------------------------------
def test_probe_03_and_23_user_story_leakage_and_out_of_section(project: Path):
    """v3: FR-001 e NFR-001 ereditavano US2; `FR-999` sotto Notes entrava nello scope."""
    config = make_config(project)
    feature = discover_features(detect_specs_root(project))[0]
    reqs, anomalies = extract_requirements(feature, config, "specs")

    by_id = {r.requirement_id: r for r in reqs}
    assert set(by_id) == {"FR-001", "NFR-001"}, "FR-999 fuori dalle sezioni non deve entrare nello scope"
    assert by_id["FR-001"].user_story == "", "nessun requisito eredita la user story di una sezione precedente"
    assert by_id["NFR-001"].user_story == ""
    assert any(t == "reference-outside-requirements" for t, _ in anomalies)


def test_probe_03b_inline_user_story_tag_is_honoured(project: Path):
    spec = project / "specs" / "001-demo" / "spec.md"
    spec.write_text("# S\n\n## Requirements\n\n- **FR-002** (US1): con tag inline\n", encoding="utf-8")
    feature = discover_features(detect_specs_root(project))[0]
    reqs, _ = extract_requirements(feature, make_config(project), "specs")
    assert reqs[0].user_story == "US1"
    assert reqs[0].user_story_origin == "inline"


# -- Probe 4 e 5 -----------------------------------------------------------
def test_probe_04_and_05_changed_requirement_drops_evidence(project: Path, cli):
    """Il probe piu' grave: v3 manteneva `tested` con ZERO findings.

    Requisito riscritto da capo, tasks.md cancellato, marcatore rimosso dal
    codice: la v3 riportava comunque Tested/Done 1 e nessun rilievo.
    """
    cli("init")
    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "auth", "--mandatory", "--actor", "qa", "--reason", "copertura")
    cli("test", "confirm-manual", "TEST-1", "--result", "pass",
        "--evidence", "verbale.pdf", "--actor", "qa", "--reason", "collaudo")
    _, out, _ = cli("refresh", "--json")
    assert json.loads(out)["counts"]["tested"] == 1, "precondizione: deve partire da tested"

    (project / "specs" / "001-demo" / "spec.md").write_text(
        "# Spec\n\n## Requirements\n\n- **FR-001**: il sistema deve cancellare tutti i dati al logout\n",
        encoding="utf-8",
    )
    (project / "specs" / "001-demo" / "tasks.md").unlink()
    (project / "src" / "auth.py").write_text("def auth():\n    return True\n", encoding="utf-8")

    _, out, _ = cli("refresh", "--json")
    payload = json.loads(out)
    assert payload["counts"]["tested"] == 0, "l'evidenza non si applica piu' al nuovo contenuto"
    assert payload["counts"]["implemented"] == 0
    assert any(f["finding_type"] == "requirement-changed" for f in payload["findings"]), \
        "il cambio di contenuto deve essere segnalato, non silenzioso"


def test_probe_04b_fingerprint_changes_with_meaning_not_formatting():
    a = requirement_fingerprint(requirement_id="FR-001", text="il sistema deve **autenticare**  l'utente.")
    b = requirement_fingerprint(requirement_id="FR-001", text="il sistema deve autenticare l'utente")
    c = requirement_fingerprint(requirement_id="FR-001", text="il sistema deve cancellare i dati")
    assert a == b, "riformattare non deve invalidare l'evidenza"
    assert a != c, "cambiare significato deve invalidarla"


# -- Probe 6 e 7 -----------------------------------------------------------
def test_probe_07_multiple_backticked_ids_parse_cleanly():
    """v3: `` `FR-001`, `FR-002` `` -> ['FR-001`', '`FR-002'] — ID corrotti."""
    assert parse_id_list("`FR-001`, `FR-002`") == ["FR-001", "FR-002"]
    assert parse_id_list("FR-001;FR-002") == ["FR-001", "FR-002"]
    assert parse_id_list("—") == []


def test_probe_06_closed_risk_annotation_not_persisted(project: Path, cli):
    """v3: `[rischio aperto: R-001]` restava nelle Note anche a rischio chiuso."""
    risk = project / "specs" / "001-demo" / "risk-register.md"
    risk.write_text(
        "# Risk\n\n## Rischi\n\n| Risk ID | Descrizione | Stato | Requisiti collegati |\n"
        "| --- | --- | --- | --- |\n| `R-001` | dipendenza fragile | aperto | `FR-001` |\n",
        encoding="utf-8",
    )
    assert len(read_open_risks(project / "specs" / "001-demo")) == 1

    cli("init")
    matrix = (project / "requirement-burnup" / "reports" / "traceability-matrix.md").read_text(encoding="utf-8")
    assert "rischio aperto" not in matrix, "il rischio non va scritto nelle Note umane"

    risk.write_text(risk.read_text(encoding="utf-8").replace("| aperto |", "| chiuso |"), encoding="utf-8")
    assert read_open_risks(project / "specs" / "001-demo") == []


# -- Probe 8 e 9 -----------------------------------------------------------
def test_probe_08_output_outside_project_root_rejected(project: Path):
    """v3: `output_dir: /tmp/OUTSIDE` scriveva fuori dal repository."""
    with pytest.raises(PathConfinementError):
        resolve_under_root(project, "/tmp/OUTSIDE", field="output_dir")
    with pytest.raises(PathConfinementError):
        resolve_under_root(project, "../fuori", field="output_dir")
    assert resolve_under_root(project, "requirement-burnup", field="output_dir") == project / "requirement-burnup"


def test_probe_09_absolute_input_glob_rejected(project: Path, tmp_path: Path):
    """v3: un glob assoluto leggeva file arbitrari del filesystem."""
    secret = tmp_path / "secret.txt"
    secret.write_text("dati riservati", encoding="utf-8")
    with pytest.raises(PathConfinementError):
        expand_globs(project, [str(secret)])
    with pytest.raises(PathConfinementError):
        expand_globs(project, ["../**/*"])


def test_probe_09b_symlink_escape_not_followed(project: Path, tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.py").write_text("# REQ: 001-demo/FR-001\n", encoding="utf-8")
    link = project / "src" / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink non supportati su questa piattaforma")
    found = expand_globs(project, ["src/**/*"])
    assert all("leak.py" not in str(p) for p in found)


# -- Probe 10 --------------------------------------------------------------
def test_probe_10_test1_does_not_capture_test10():
    """v3: `if tid in nome`, quindi TEST-1 catturava suite.TEST-10_login."""
    known = {"TEST-1", "TEST-10"}
    assert resolve_test_id("suite.TEST-10_login", known, {}) == "TEST-10"
    assert resolve_test_id("suite.TEST-1_auth", known, {}) == "TEST-1"
    assert resolve_test_id("TEST-100", known, {}) is None, "nessuna corrispondenza e' meglio di una sbagliata"


def test_probe_10b_explicit_mapping_wins():
    assert resolve_test_id("weird::name", {"TEST-1"}, {"weird::name": "TEST-1"}) == "TEST-1"


# -- Probe 11 --------------------------------------------------------------
def test_probe_11_report_ingested_only_once(project: Path, cli):
    """v3: tre refresh dello stesso report producevano tre righe identiche."""
    cli("init")
    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "auth", "--mandatory", "--actor", "qa", "--reason", "r")
    (project / "test-results" / "r1.xml").write_text(
        '<testsuite timestamp="2026-07-30T10:00:00Z">'
        '<testcase classname="suite" name="TEST-1_auth" time="0.1"/></testsuite>',
        encoding="utf-8",
    )
    counts = []
    for _ in range(3):
        _, out, _ = cli("refresh", "--json")
        counts.append(json.loads(out)["new_runs"])
    assert counts == [1, 0, 0], f"il report va importato una volta sola, ottenuto {counts}"


# -- Probe 12 e 13 ---------------------------------------------------------
def test_probe_12_junit_not_stamped_with_refresh_head(project: Path, cli):
    """v3: al report veniva assegnato l'HEAD del refresh, non la sua revisione."""
    cli("init")
    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "auth", "--mandatory", "--actor", "qa", "--reason", "r")
    (project / "test-results" / "r1.xml").write_text(
        '<testsuite timestamp="2026-07-30T10:00:00Z">'
        '<testcase classname="s" name="TEST-1_a" time="0.1"/></testsuite>',
        encoding="utf-8",
    )
    cli("refresh")
    runs = [json.loads(l) for l in (project / "requirement-burnup" / "state" / "test-runs.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    assert runs, "la run deve essere registrata"
    assert runs[0].get("source_revision", "") == "", "senza sidecar la revisione resta sconosciuta"
    assert runs[0]["revision_origin"] == "unknown"
    assert runs[0]["executed_at"] == "2026-07-30T10:00:00Z", "l'ora e' quella di esecuzione"


def test_probe_12b_sidecar_provides_real_revision(project: Path, cli):
    cli("init")
    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "auth", "--mandatory", "--actor", "qa", "--reason", "r")
    (project / "test-results" / "r1.xml").write_text(
        '<testsuite timestamp="2026-07-30T10:00:00Z"><testcase classname="s" name="TEST-1_a"/></testsuite>',
        encoding="utf-8",
    )
    (project / "test-results" / "r1.xml.meta.json").write_text(
        '{"source_revision": "deadbee", "executed_at": "2026-07-30T10:00:00Z"}', encoding="utf-8"
    )
    cli("refresh")
    runs = [json.loads(l) for l in (project / "requirement-burnup" / "state" / "test-runs.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    assert runs[0]["source_revision"] == "deadbee"
    assert runs[0]["revision_origin"] == "sidecar"


def test_probe_13_manual_confirmation_requires_a_confirmation(project: Path, cli):
    """v3: la policy `manual-confirmation` ritornava sempre True, senza conferme."""
    cli("init")
    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "auth", "--mandatory", "--actor", "qa", "--reason", "r")
    _, out, _ = cli("refresh", "--json")
    assert json.loads(out)["counts"]["tested"] == 0, "senza conferma non si raggiunge tested"

    cli("test", "confirm-manual", "TEST-1", "--result", "pass",
        "--evidence", "verbale.pdf", "--actor", "qa@team", "--reason", "collaudo superato")
    _, out, _ = cli("refresh", "--json")
    assert json.loads(out)["counts"]["tested"] == 1

    decisions = (project / "requirement-burnup" / "state" / "decisions.jsonl").read_text(encoding="utf-8")
    assert "qa@team" in decisions and "collaudo superato" in decisions, "la conferma deve essere auditabile"


# -- Probe 14 --------------------------------------------------------------
def test_probe_14_stale_test_link_is_dropped(project: Path, cli):
    """v3: i Test ID collegati non venivano mai rimossi (union senza sottrazione)."""
    cli("init")
    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "auth", "--mandatory", "--actor", "qa", "--reason", "r")
    cli("refresh")
    assert "TEST-1" in (project / "requirement-burnup" / "reports" / "traceability-matrix.md").read_text(encoding="utf-8")

    state = project / "requirement-burnup" / "state" / "test-definitions.json"
    state.write_text("[]", encoding="utf-8")
    cli("refresh")
    matrix = (project / "requirement-burnup" / "reports" / "traceability-matrix.md").read_text(encoding="utf-8")
    assert "TEST-1" not in matrix, "un collegamento rimosso non deve sopravvivere al refresh"


# -- Probe 15 --------------------------------------------------------------
def test_probe_15_scope_composition_change_is_detected():
    """v3: rimuovere e aggiungere un requisito a parita' di numero era 'no-change'."""
    from burnup.engine import should_snapshot
    from burnup.models import Counts

    before = scope_fingerprint(["f/FR-001", "f/FR-002", "f/FR-003"])
    after = scope_fingerprint(["f/FR-001", "f/FR-002", "f/FR-004"])
    assert before != after

    prev = {"scope": 3, "defined": 3, "implemented": 0, "tested": 0, "removed_total": 0, "scope_fingerprint": before}
    now = Counts(scope=3, defined=3, implemented=0, tested=0, removed_total=0, scope_fingerprint=after)
    appended, reason = should_snapshot(prev, now, forced=False)
    assert appended and reason == "scope-composition-change"


# -- Probe 16 --------------------------------------------------------------
def test_probe_16_run_ids_never_collide():
    """v3: con storico 001 e 003 rigenerava 003, perche' contava le righe."""
    ids = {run_id() for _ in range(5000)}
    assert len(ids) == 5000


def test_probe_16b_run_ids_sort_chronologically():
    from burnup.ids import ulid
    early, late = ulid(timestamp_ms=1_000_000), ulid(timestamp_ms=2_000_000)
    assert early < late


# -- Probe 17 --------------------------------------------------------------
def test_probe_17_duplicate_test_id_rejected(project: Path, cli):
    """v3: una dict comprehension teneva solo l'ultima definizione, in silenzio."""
    cli("init")
    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "prima", "--actor", "qa", "--reason", "r")
    code, _, err = cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
                       "--definition", "seconda", "--actor", "qa", "--reason", "r",
                       expect=ExitCode.CONFIG_ERROR)
    assert "esiste gia" in err.lower()

    cli("test", "define", "TEST-1", "--requirement", "001-demo/FR-001",
        "--definition", "seconda", "--replace", "--actor", "qa", "--reason", "r")
    defs = json.loads((project / "requirement-burnup" / "state" / "test-definitions.json").read_text(encoding="utf-8"))
    assert len(defs) == 1 and defs[0]["definition"] == "seconda"


# -- Probe 18 --------------------------------------------------------------
def test_probe_18_dual_specs_roots_hard_fail(project: Path):
    """v3: sceglieva la prima radice senza avvisare, perdendo meta' delle feature."""
    other = project / ".specify" / "specs" / "002-altra"
    other.mkdir(parents=True)
    (other / "spec.md").write_text("# Altra\n\n## Requirements\n\n- **FR-050**: x\n", encoding="utf-8")
    with pytest.raises(SpecsLayoutError) as exc:
        detect_specs_root(project)
    assert "DUE radici" in str(exc.value)


# -- Probe 19 --------------------------------------------------------------
def test_probe_19_malformed_nested_config_rejected_early(project: Path, cli):
    """v3: `inputs: []` superava il loader e crashava molto piu' tardi."""
    (project / "requirement-burnup-config.yml").write_text(
        'schema_version: "2.0"\noutput_dir: "requirement-burnup"\ninputs: []\n'
        "requirements: {}\ntraceability: {}\nstatus: {}\nsnapshots: {}\n",
        encoding="utf-8",
    )
    code, _, err = cli("refresh", expect=ExitCode.CONFIG_ERROR)
    assert "inputs" in err
    assert not (project / "requirement-burnup").exists(), "nessun file va creato se la config non e' valida"


# -- Probe 20 --------------------------------------------------------------
def test_probe_20_older_report_never_overwrites_newer():
    """v3: vinceva l'ultimo record processato, quindi l'ordine dei file decideva."""
    old = TestRun(run_id="RUN-A", run_identity="a", test_id="TEST-1", result="fail",
                  executed_at="2026-01-01T00:00:00Z", evidence_hash="h1")
    new = TestRun(run_id="RUN-B", run_identity="b", test_id="TEST-1", result="pass",
                  executed_at="2026-06-01T00:00:00Z", evidence_hash="h2")
    assert latest_run_by_test([old, new])["TEST-1"].result == "pass"
    assert latest_run_by_test([new, old])["TEST-1"].result == "pass", "l'ordine non deve contare"


def test_probe_20b_shuffled_input_is_deterministic():
    import random
    runs = [
        TestRun(run_id=f"RUN-{i:03d}", run_identity=str(i), test_id="TEST-1",
                result="pass" if i % 2 else "fail", executed_at=f"2026-01-{i + 1:02d}T00:00:00Z")
        for i in range(10)
    ]
    expected = latest_run_by_test(runs)["TEST-1"].run_id
    for seed in range(20):
        shuffled = list(runs)
        random.Random(seed).shuffle(shuffled)
        assert latest_run_by_test(shuffled)["TEST-1"].run_id == expected


# -- Probe 21 --------------------------------------------------------------
def test_probe_21_substring_does_not_create_false_task_link(project: Path):
    """v3: `XFR-001Y` dentro un task veniva collegato a FR-001."""
    (project / "specs" / "001-demo" / "tasks.md").write_text(
        "- [x] T001 Implement XFR-001Y helper\n"
        "- [x] T002 chore [NON-REQ: build]\n"
        "- [x] T010 real work for FR-001\n",
        encoding="utf-8",
    )
    feature = discover_features(detect_specs_root(project))[0]
    scan = link_tasks(feature, make_config(project))
    assert [t.task_id for t in scan.by_requirement.get("FR-001", [])] == ["T010"]
    assert "T001" in scan.unlinked_tasks


# -- Probe 22 --------------------------------------------------------------
def test_probe_22_marker_in_string_is_not_code_evidence(project: Path):
    """v3: `msg = "REQ: 001-demo/FR-001 ..."` contava come evidenza di codice."""
    (project / "src" / "auth.py").write_text(
        'msg = "REQ: 001-demo/FR-001 finto"\n'
        "# REQ: 001-demo/FR-002 vero\n"
        "x = 1  # REQ: 001-demo/NFR-001 in coda\n",
        encoding="utf-8",
    )
    evidence, anomalies = link_code_evidence(project, make_config(project))
    assert "001-demo/FR-001" not in evidence
    assert "001-demo/FR-002" in evidence
    assert "001-demo/NFR-001" in evidence
    assert any(t == "marker-outside-comment" for t, _ in anomalies)


def test_probe_22b_generated_reports_are_not_scanned_as_source(project: Path, cli):
    """N-07: senza esclusione, i marcatori nella Matrix generata si auto-alimentano."""
    cli("init")
    config = make_config(project, source_globs=["**/*"])
    evidence, _ = link_code_evidence(project, config)
    for refs in evidence.values():
        for ev in refs:
            assert "requirement-burnup" not in ev.path
