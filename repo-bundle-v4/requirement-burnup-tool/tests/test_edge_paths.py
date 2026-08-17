"""Percorsi d'errore e casi limite: la parte del codice che si vede solo quando
qualcosa va storto.

Perche' vale la pena coprirli. Un percorso d'errore non esercitato e' codice che
gira per la prima volta nel momento peggiore — quando il progetto e' gia' rotto
e chi legge il messaggio ha bisogno che sia esatto. Diversi difetti dei tre giri
di collaudo stavano proprio li': un suggerimento che rimandava a un comando
inesistente (C-05) e un exit code sbagliato (C-08) erano entrambi su percorsi
d'errore che nessun test attraversava.

Non e' una corsa alla percentuale: ogni test qui asserisce un comportamento
dichiarato — un messaggio, un exit code, una decisione di scarto — non
semplicemente l'esecuzione di una riga.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from burnup.config import load_config
from burnup.errors import ConfigError, ExitCode, PathConfinementError, SpecsLayoutError, StoreError
from burnup.gates import GATE_NAMES, GateDecision, check_entry_criteria, evaluate_gates, format_gate_report
from burnup.ids import now_iso
from burnup.ingest import _normalize_timestamp, _sidecar_metadata, parse_generic_json, parse_junit, resolve_test_id
from burnup.mdparse import parse_document, parse_table_lines, read_text, render_table
from burnup.models import TestRun
from burnup.paths import expand_globs, relative_label, resolve_under_root
from burnup.render import _burnup_chart
from burnup.risk_link import read_open_risks
from burnup.status import FreshnessVerdict, StatusContext, evaluate_freshness
from burnup.store import Store, StoreData
from conftest import CONFIG_YML, make_config


def scrivi_config(tmp_path: Path, yaml_text: str) -> Path:
    percorso = tmp_path / "requirement-burnup-config.yml"
    percorso.write_text(yaml_text, encoding="utf-8")
    return percorso


def carica(tmp_path: Path, sostituzioni: list[tuple[str, str]]):
    testo = CONFIG_YML
    for prima, dopo in sostituzioni:
        testo = testo.replace(prima, dopo)
    return load_config(scrivi_config(tmp_path, testo), tmp_path)


# --------------------------------------------------------------------------
# Configurazione: ogni errore deve dire cosa correggere
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "sostituzione,atteso",
    [
        (('schema_version: "2.0"', 'schema_version: "9.9"'), "schema_version"),
        (('output_dir: "requirement-burnup"', 'output_dir: "../fuori"'), "output_dir"),
        (('source_globs: ["src/**/*"]', 'source_globs: "non-una-lista"'), "source_globs"),
        (('source_globs: ["src/**/*"]', "source_globs: []"), "source_globs"),
        (('source_globs: ["src/**/*"]', "source_globs: [123]"), "source_globs"),
        (('test_report_globs: ["test-results/**/*.xml", "test-results/**/*.json"]',
          'test_report_globs: "no"'), "test_report_globs"),
        (('accepted_id_patterns: ["FR-[0-9]+", "NFR-[0-9]+"]', "accepted_id_patterns: []"),
         "accepted_id_patterns"),
        (('accepted_id_patterns: ["FR-[0-9]+", "NFR-[0-9]+"]', 'accepted_id_patterns: ["["]'),
         "pattern"),
        (('sections: ["Requirements"]', "sections: []"), "sections"),
        (('user_story_sections: ["User Scenarios"]', 'user_story_sections: "no"'),
         "user_story_sections"),
        (('test_freshness_policy: "manual-confirmation"', 'test_freshness_policy: "inventata"'),
         "test_freshness_policy"),
        (('strict_blocks_on: ["high"]', 'strict_blocks_on: ["gravissimo"]'), "strict_blocks_on"),
    ],
)
def test_ogni_errore_di_configurazione_nomina_il_campo(tmp_path: Path, sostituzione, atteso):
    with pytest.raises(ConfigError) as errore:
        carica(tmp_path, [sostituzione])
    assert atteso in str(errore.value) or atteso in (errore.value.hint or "")


def test_configurazione_assente(tmp_path: Path):
    with pytest.raises(ConfigError) as errore:
        load_config(tmp_path / "manca.yml", tmp_path)
    assert "init" in (errore.value.hint or "")


def test_yaml_malformato(tmp_path: Path):
    with pytest.raises(ConfigError) as errore:
        load_config(scrivi_config(tmp_path, "chiave: [non chiusa\n"), tmp_path)
    assert "YAML" in str(errore.value)


def test_yaml_che_non_e_una_mappa(tmp_path: Path):
    with pytest.raises(ConfigError) as errore:
        load_config(scrivi_config(tmp_path, "- solo\n- una\n- lista\n"), tmp_path)
    assert "mappa" in str(errore.value)


def test_exclude_dirs_deve_contenere_stringhe(tmp_path: Path):
    with pytest.raises(ConfigError):
        carica(tmp_path, [('source_globs: ["src/**/*"]', 'source_globs: ["src/**/*"]\n  exclude_dirs: [1, 2]')])


def test_percorso_del_risk_register(tmp_path: Path):
    config = carica(tmp_path, [])
    assert config.risk_register_path(tmp_path / "specs" / "001-x").name == "risk-register.md"


# --------------------------------------------------------------------------
# Percorsi: il confinamento al repository
# --------------------------------------------------------------------------

def test_glob_assoluto_rifiutato(tmp_path: Path):
    with pytest.raises(PathConfinementError):
        expand_globs(tmp_path, ["/etc/*"], field="source_globs")


def test_glob_che_risale_oltre_la_radice(tmp_path: Path):
    with pytest.raises(PathConfinementError):
        expand_globs(tmp_path, ["../**/*"], field="source_globs")


def test_percorso_assoluto_rifiutato(tmp_path: Path):
    with pytest.raises(PathConfinementError):
        resolve_under_root(tmp_path, "/tmp/fuori", field="output_dir")


def test_symlink_che_esce_dalla_radice_rifiutato(tmp_path: Path):
    (tmp_path / "dentro").mkdir()
    esterno = tmp_path.parent / "esterno-al-progetto"
    esterno.mkdir(exist_ok=True)
    collegamento = tmp_path / "dentro" / "uscita"
    try:
        collegamento.symlink_to(esterno, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink non supportati su questa piattaforma")
    with pytest.raises(PathConfinementError):
        resolve_under_root(tmp_path, "dentro/uscita", field="output_dir")


def test_relative_label_su_percorso_esterno(tmp_path: Path):
    fuori = tmp_path.parent / "altrove"
    assert "altrove" in relative_label(fuori, tmp_path)


# --------------------------------------------------------------------------
# Markdown: le forme che un file reale assume davvero
# --------------------------------------------------------------------------

def test_tabella_con_meno_celle_della_riga_di_intestazione():
    parsed = parse_table_lines(["| A | B | C |", "|---|---|---|", "| solo-una |"])
    assert parsed is not None
    _, righe = parsed
    assert righe[0]["A"] == "solo-una" and righe[0]["C"] == ""


def test_testo_che_non_e_una_tabella():
    assert parse_table_lines(["nessuna pipe qui", "nemmeno qui"]) is None


def test_tabella_senza_riga_di_separazione_resta_leggibile():
    """Il parser non pretende il separatore: una tabella senza `|---|` viene
    comunque letta, e la prima riga fa da intestazione."""
    intestazioni, righe = parse_table_lines(["| A | B |", "| 1 | 2 |"])
    assert intestazioni == ["A", "B"] and righe[0]["A"] == "1"


def test_il_contenuto_dentro_un_blocco_di_codice_non_e_una_sezione(tmp_path: Path):
    percorso = tmp_path / "d.md"
    percorso.write_text(
        "# Titolo\n\n```\n## Questa non e' una sezione\n```\n\n## Questa si\n\ntesto\n",
        encoding="utf-8",
    )
    documento = parse_document(read_text(percorso))
    titoli = [s.title for s in documento.sections]
    assert "Questa non e' una sezione" not in titoli
    assert "Questa si" in titoli


def test_selezione_delle_sezioni_per_nome(tmp_path: Path):
    percorso = tmp_path / "d.md"
    percorso.write_text("# T\n\n## Requirements\n\ntesto\n\n## Notes\n\naltro\n", encoding="utf-8")
    documento = parse_document(read_text(percorso))
    assert [s.title for s in documento.sections_matching("requirements")] == ["Requirements"]
    assert documento.sections_matching("inesistente") == []


def test_round_trip_di_una_tabella_vuota():
    assert parse_table_lines(render_table(["A"], []).splitlines()) is not None


# --------------------------------------------------------------------------
# Importazione dei report
# --------------------------------------------------------------------------

def test_timestamp_illeggibile_diventa_vuoto():
    assert _normalize_timestamp("non-una-data") == ""
    assert _normalize_timestamp("") == ""


def test_sidecar_malformato_viene_ignorato(tmp_path: Path):
    report = tmp_path / "j.xml"
    report.write_text("<testsuite/>", encoding="utf-8")
    (tmp_path / "j.xml.meta.json").write_text("{ non json", encoding="utf-8")
    assert _sidecar_metadata(report) == {}


def test_sidecar_assente(tmp_path: Path):
    assert _sidecar_metadata(tmp_path / "senza-sidecar.xml") == {}


@pytest.mark.parametrize(
    "elemento,atteso",
    [("<error/>", "error"), ("<failure/>", "fail"), ("<skipped/>", "blocked"), ("", "pass")],
)
def test_esiti_junit(tmp_path: Path, elemento, atteso):
    report = tmp_path / "j.xml"
    report.write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="s" timestamp="2026-01-01T00:00:00">'
        f'<testcase classname="c" name="T1">{elemento}</testcase></testsuite></testsuites>',
        encoding="utf-8",
    )
    assert parse_junit(report, {})[0].result == atteso


def test_junit_senza_classname_usa_il_solo_nome(tmp_path: Path):
    report = tmp_path / "j.xml"
    report.write_text(
        '<?xml version="1.0"?><testsuite name="s" timestamp="2026-01-01T00:00:00">'
        '<testcase name="T1"/></testsuite>',
        encoding="utf-8",
    )
    assert parse_junit(report, {})[0].test_name == "T1"


def test_report_json_generico(tmp_path: Path):
    report = tmp_path / "r.json"
    report.write_text(
        json.dumps([{"id": "TEST-1", "result": "pass", "timestamp": "2026-01-01T00:00:00Z",
                     "duration": "1.2s", "source_revision": "abc1234"}]),
        encoding="utf-8",
    )
    risultati = parse_generic_json(report, {})
    assert risultati[0].test_name == "TEST-1" and risultati[0].source_revision == "abc1234"


def test_report_json_che_non_e_un_array(tmp_path: Path):
    report = tmp_path / "r.json"
    report.write_text('{"non": "un array"}', encoding="utf-8")
    with pytest.raises(ValueError):
        parse_generic_json(report, {})


def test_test_id_ambiguo_viene_rifiutato():
    """"Un'attribuzione ambigua e' peggio di nessuna attribuzione"."""
    assert resolve_test_id("suite.TEST-1.TEST-2", {"TEST-1", "TEST-2"}, {}) is None


def test_confine_di_token_su_test_id():
    assert resolve_test_id("suite.TEST-10_login", {"TEST-1"}, {}) is None
    assert resolve_test_id("suite.TEST-1_login", {"TEST-1"}, {}) == "TEST-1"


# --------------------------------------------------------------------------
# Freschezza: i verdetti di ogni policy
# --------------------------------------------------------------------------

def _ctx(policy: str, *, revisione: str = "abc", sporco: bool = False) -> StatusContext:
    return StatusContext(freshness_policy=policy, current_revision=revisione,
                         worktree_dirty=sporco, require_tasks_for_implemented=True)


def _run(**kwargs) -> TestRun:
    base = dict(run_id="R1", test_id="T1", result="pass", executed_at=now_iso(),
                evidence_hash="abc", source_revision="", revision_origin="unknown",
                run_identity="x", worktree_dirty=False)
    base.update(kwargs)
    return TestRun(**base)


def test_latest_known_accetta_sempre():
    verdetto = evaluate_freshness(_run(), _ctx("latest-known"))
    assert verdetto.fresh


def test_current_revision_senza_revisione_corrente():
    contesto = _ctx("current-revision", revisione="")
    assert not evaluate_freshness(_run(source_revision="abc"), contesto).fresh


def test_current_revision_con_working_tree_sporco():
    contesto = _ctx("current-revision", revisione="abc", sporco=True)
    verdetto = evaluate_freshness(_run(source_revision="abc", revision_origin="sidecar"), contesto)
    assert not verdetto.fresh


def test_current_revision_con_origine_non_verificabile():
    contesto = _ctx("current-revision", revisione="abc")
    verdetto = evaluate_freshness(_run(source_revision="abc", revision_origin="unknown"), contesto)
    assert not verdetto.fresh


def test_current_revision_su_revisione_diversa():
    contesto = _ctx("current-revision", revisione="abc")
    verdetto = evaluate_freshness(_run(source_revision="xyz", revision_origin="sidecar"), contesto)
    assert not verdetto.fresh


def test_policy_sconosciuta_non_e_fresca():
    verdetto = evaluate_freshness(_run(), _ctx("inventata"))
    assert not verdetto.fresh and "sconosciuta" in verdetto.reason


# --------------------------------------------------------------------------
# Canonical store
# --------------------------------------------------------------------------

def test_riga_jsonl_malformata_indica_il_numero_di_riga(tmp_path: Path):
    store = Store(tmp_path / "out")
    store.state_dir.mkdir(parents=True)
    (store.state_dir / "relations.jsonl").write_text('{"a": 1}\n{ rotto\n', encoding="utf-8")
    with pytest.raises(StoreError) as errore:
        store.load()
    assert "riga 2" in str(errore.value)


def test_json_di_stato_illeggibile(tmp_path: Path):
    store = Store(tmp_path / "out")
    store.state_dir.mkdir(parents=True)
    (store.state_dir / "requirements.json").write_text("{ rotto", encoding="utf-8")
    with pytest.raises(StoreError) as errore:
        store.load()
    assert "init --reset" in (errore.value.hint or "")


def test_righe_vuote_nel_jsonl_sono_ignorate(tmp_path: Path):
    store = Store(tmp_path / "out")
    store.state_dir.mkdir(parents=True)
    (store.state_dir / "relations.jsonl").write_text(
        '\n\n{"from_key": "a", "to_ref": "T1", "rel_type": "implemented-by"}\n\n', encoding="utf-8")
    assert len(store.load().relations) == 1


def test_commit_e_lettura_completano_il_giro(tmp_path: Path):
    store = Store(tmp_path / "out")
    store.commit(StoreData(manifest={"scanned_at": "2026-01-01T00:00:00Z"}))
    assert store.load().manifest["scanned_at"] == "2026-01-01T00:00:00Z"


# --------------------------------------------------------------------------
# Risk register e grafico
# --------------------------------------------------------------------------

def test_risk_register_assente_non_e_un_errore(tmp_path: Path):
    assert read_open_risks(tmp_path) == []


def test_risk_register_senza_tabella(tmp_path: Path):
    (tmp_path / "risk-register.md").write_text("# Rischi\n\nNessuno.\n", encoding="utf-8")
    assert read_open_risks(tmp_path) == []


def test_grafico_senza_snapshot():
    assert "Nessuno snapshot" in _burnup_chart([])


# --------------------------------------------------------------------------
# Gate: casi limite della state machine
# --------------------------------------------------------------------------

def test_gate_fuori_dalla_classe_dichiarata():
    stati = evaluate_gates("f", [], {"spec": "fp"})
    unmet = check_entry_criteria(2, stati, {"spec": "fp"}, [], change_class="fast-track")
    assert unmet and "non fa parte della classe" in unmet[0]


def test_il_report_dei_gate_mostra_le_condizioni():
    decisione = GateDecision(
        decision_id="d", feature_id="f", gate=1, outcome="conditionally-approved",
        approver="pm", approved_at=now_iso(), rationale="ok",
        artifact_fingerprints={"spec": "fp"}, conditions=["aggiungere metriche a NFR-001"],
    )
    stati = evaluate_gates("f", [decisione], {"spec": "fp"})
    righe = "\n".join(format_gate_report("f", stati))
    assert "condizione: aggiungere metriche a NFR-001" in righe


def test_gate_respinto_resta_respinto():
    decisione = GateDecision(
        decision_id="d", feature_id="f", gate=1, outcome="rejected",
        approver="pm", approved_at=now_iso(), rationale="requisiti ambigui",
        artifact_fingerprints={"spec": "fp"},
    )
    stati = evaluate_gates("f", [decisione], {"spec": "fp"})
    assert stati[1].status == "rejected"
    assert GATE_NAMES[1] in "\n".join(format_gate_report("f", stati))


# --------------------------------------------------------------------------
# Sorgenti illeggibili e layout ambiguo
# --------------------------------------------------------------------------

def test_file_binario_non_e_codice_tracciabile(project: Path, cli):
    (project / "src" / "immagine.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\xff\xfe")
    cli("init")  # non deve sollevare


def test_due_cartelle_di_spec_popolate_sono_ambigue(project: Path, cli):
    alternativa = project / ".specify" / "specs" / "001-demo"
    alternativa.mkdir(parents=True)
    (alternativa / "spec.md").write_text("# S\n\n## Requirements\n\n- **FR-009**: x\n", encoding="utf-8")
    with pytest.raises(SpecsLayoutError):
        from burnup.specscan import detect_specs_root

        detect_specs_root(project)


def test_id_duplicato_nella_stessa_feature(project: Path, cli):
    spec = project / "specs" / "001-demo" / "spec.md"
    spec.write_text(
        spec.read_text(encoding="utf-8").replace(
            "- **NFR-001**: la risposta deve arrivare entro 100ms",
            "- **NFR-001**: la risposta deve arrivare entro 100ms\n"
            "- **FR-001**: definizione ripetuta dello stesso ID",
        ),
        encoding="utf-8",
    )
    cli("init")
    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "duplicate-requirement-id" in tipi


# --------------------------------------------------------------------------
# Comandi di decisione non ancora esercitati
# --------------------------------------------------------------------------

def test_rimozione_di_un_requisito_inesistente(project: Path, cli):
    cli("init")
    cli("requirement", "remove", "001-demo/FR-999", "--actor", "u", "--reason", "r",
        expect=ExitCode.CONFIG_ERROR)


def test_conferma_di_un_collegamento(project: Path, cli):
    cli("init")
    cli("link", "confirm", "001-demo/FR-001", "T900", "--type", "implemented-by",
        "--actor", "tl", "--reason", "task in un altro repository")
    relazioni = [
        json.loads(l) for l in
        (project / "requirement-burnup" / "state" / "relations.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    assert any(r["to_ref"] == "T900" and r["decided_by"] == "tl" for r in relazioni)


def test_waiver_di_un_finding_inesistente(project: Path, cli):
    cli("init")
    cli("finding", "waive", "FND-NON-ESISTE", "--actor", "u", "--reason", "r",
        expect=ExitCode.CONFIG_ERROR)


def test_gate_status_su_feature_inesistente(project: Path, cli):
    cli("init")
    cli("gate", "status", "999-non-esiste", expect=ExitCode.CONFIG_ERROR)


def test_status_senza_store(project: Path, cli):
    cli("status", expect=ExitCode.CONFIG_ERROR)


def test_init_due_volte_senza_reset(project: Path, cli):
    cli("init")
    cli("init", expect=ExitCode.CONFIG_ERROR)


def test_status_dichiara_stale_con_lavoro_non_committato(project: Path, cli):
    cli("init")
    (project / "src" / "auth.py").write_text("# modificato\n", encoding="utf-8")
    _, out, _ = cli("status", "--json")
    assert json.loads(out)["freshness"] == "stale"


# --------------------------------------------------------------------------
# Git assente
# --------------------------------------------------------------------------

def test_git_non_installato_e_dichiarato(tmp_path: Path, monkeypatch):
    """Non deve schiantarsi: deve dire che la revisione e' sconosciuta e perche'."""
    from burnup import engine

    def esplode(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(engine.subprocess, "run", esplode)
    revisione, sporco, motivo = engine.git_revision(tmp_path)
    assert revisione == "" and not sporco and "git" in motivo


def test_git_che_fallisce(tmp_path: Path, monkeypatch):
    from burnup import engine

    def esplode(*args, **kwargs):
        raise OSError("permesso negato")

    monkeypatch.setattr(engine.subprocess, "run", esplode)
    revisione, _, motivo = engine.git_revision(tmp_path)
    assert revisione == "" and "fallita" in motivo


def test_directory_senza_commit(tmp_path: Path):
    from burnup import engine

    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True, capture_output=True)
    revisione, _, motivo = engine.git_revision(tmp_path)
    assert revisione == "" and motivo
