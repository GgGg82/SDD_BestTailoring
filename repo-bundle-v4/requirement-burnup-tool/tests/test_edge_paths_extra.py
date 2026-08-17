"""Ultimi percorsi non esercitati: validazioni residue, stati intermedi, guasti di I/O.

Completa `test_edge_paths.py`. Vale la stessa regola: ogni test asserisce un
comportamento dichiarato, non la semplice esecuzione di una riga.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from burnup.config import load_config
from burnup.errors import ConfigError, ExitCode, InvariantError, PathConfinementError, SpecsLayoutError, StoreError
from burnup.gates import check_entry_criteria, evaluate_gates
from burnup.ids import now_iso
from burnup.ingest import _iso, parse_generic_json, parse_junit, resolve_test_id
from burnup.mdparse import parse_document, read_text
from burnup.models import Requirement, TestDefinition, TestRun
from burnup.paths import expand_globs, is_excluded, relative_label
from burnup.specscan import detect_specs_root
from burnup.status import StatusContext, compute_status
from burnup.store import Store, StoreData
from conftest import CONFIG_YML


def config_con(tmp_path: Path, *sostituzioni: tuple[str, str]):
    testo = CONFIG_YML
    for prima, dopo in sostituzioni:
        testo = testo.replace(prima, dopo)
    percorso = tmp_path / "requirement-burnup-config.yml"
    percorso.write_text(testo, encoding="utf-8")
    return load_config(percorso, tmp_path)


# -- Validazioni di configurazione residue --------------------------------

@pytest.mark.parametrize(
    "sostituzione,atteso",
    [
        (("requirements:", "requirements: non-una-mappa\nignorato:"), "requirements"),
        (("traceability:", "traceability: non-una-mappa\nignorato:"), "traceability"),
        (("status:", "status: non-una-mappa\nignorato:"), "status"),
        (("gates:", "gates: non-una-mappa\nignorato:"), "gates"),
        (("inputs:", "inputs: non-una-mappa\nignorato:"), "inputs"),
    ],
)
def test_una_sezione_che_non_e_una_mappa(tmp_path: Path, sostituzione, atteso):
    with pytest.raises(ConfigError) as errore:
        config_con(tmp_path, sostituzione)
    assert atteso in str(errore.value)


def test_test_id_mapping_deve_essere_una_mappa(tmp_path: Path):
    with pytest.raises(ConfigError) as errore:
        config_con(tmp_path, ("status:", "  test_id_mapping: [1, 2]\nstatus:"))
    assert "test_id_mapping" in str(errore.value)


def test_comment_prefixes_non_puo_essere_vuota(tmp_path: Path):
    with pytest.raises(ConfigError) as errore:
        config_con(tmp_path, ("status:", "  comment_prefixes: []\nstatus:"))
    assert "comment_prefixes" in str(errore.value)


def test_code_evidence_marker_deve_essere_una_regex_valida(tmp_path: Path):
    with pytest.raises(ConfigError) as errore:
        config_con(tmp_path, ('code_evidence_marker: "REQ:', 'code_evidence_marker: "([("'))
    assert "code_evidence_marker" in str(errore.value) or "Esempio" in (errore.value.hint or "")


# -- Percorsi ---------------------------------------------------------------

def test_glob_che_non_combacia_con_nulla(tmp_path: Path):
    assert expand_globs(tmp_path, ["non-esiste/**/*"], field="source_globs") == []


def test_directory_escluse_sempre(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "m.js").write_text("x", encoding="utf-8")
    (tmp_path / "vero.py").write_text("x", encoding="utf-8")
    trovati = {p.name for p in expand_globs(tmp_path, ["**/*"], field="source_globs")}
    assert "vero.py" in trovati and "config" not in trovati and "m.js" not in trovati


def test_un_percorso_fuori_dalla_radice_e_escluso_per_definizione(tmp_path: Path):
    assert is_excluded(tmp_path.parent / "altrove" / "x.py", tmp_path, ())


def test_relative_label_su_radici_incomparabili(tmp_path: Path):
    etichetta = relative_label(Path("/tmp") / "assoluto" / "x", tmp_path)
    assert "assoluto" in etichetta


# -- Importazione ------------------------------------------------------------

def test_conversione_di_un_epoch():
    assert _iso(0).startswith("1970-01-01T")


def test_array_json_con_elementi_non_oggetto(tmp_path: Path):
    report = tmp_path / "r.json"
    report.write_text('["solo una stringa"]', encoding="utf-8")
    with pytest.raises(ValueError):
        parse_generic_json(report, {})


def test_esito_error_nel_json_generico(tmp_path: Path):
    report = tmp_path / "r.json"
    report.write_text(
        json.dumps([{"id": "TEST-1", "result": "error", "timestamp": "2026-01-01T00:00:00Z"}]),
        encoding="utf-8",
    )
    assert parse_generic_json(report, {})[0].result == "error"


def test_nome_gia_uguale_a_un_test_id():
    assert resolve_test_id("TEST-1", {"TEST-1"}, {}) == "TEST-1"


def test_junit_con_testcase_fuori_da_ogni_testsuite(tmp_path: Path):
    """Forma degenere ma legale: il parser non deve perdere il caso."""
    report = tmp_path / "j.xml"
    report.write_text(
        '<?xml version="1.0"?><testsuites timestamp="2026-01-01T00:00:00">'
        '<testcase classname="c" name="T1"/></testsuites>',
        encoding="utf-8",
    )
    risultati = parse_junit(report, {})
    assert len(risultati) == 1 and risultati[0].executed_at.startswith("2026-01-01")


def test_risultato_senza_nome_viene_segnalato(project: Path, cli):
    (project / "test-results" / "j.xml").write_text(
        '<?xml version="1.0"?><testsuites><testsuite name="s" timestamp="2026-01-01T00:00:00">'
        '<testcase/></testsuite></testsuites>',
        encoding="utf-8",
    )
    cli("init")
    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "unnamed-test-result" in tipi


def test_report_illeggibile_viene_segnalato(project: Path, cli):
    (project / "test-results" / "j.xml").write_text("non è XML", encoding="utf-8")
    cli("init")
    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "unreadable-report" in tipi


# -- Markdown ----------------------------------------------------------------

def test_bom_e_newline_normalizzati(tmp_path: Path):
    """Il BOM faceva fallire il match del frontmatter: e' il caso che
    `read_text` esiste per gestire."""
    percorso = tmp_path / "d.md"
    percorso.write_bytes("\ufeff---\r\nchiave: v\r\n---\r\n# corpo\r\n".encode("utf-8"))
    testo = read_text(percorso)
    assert not testo.startswith("\ufeff") and "\r" not in testo


def test_testo_di_una_sezione(tmp_path: Path):
    percorso = tmp_path / "d.md"
    percorso.write_text("# T\n\n## S\n\nprima riga\nseconda riga\n", encoding="utf-8")
    sezione = parse_document(read_text(percorso)).sections_matching("s")[0]
    assert "prima riga" in sezione.text() and "seconda riga" in sezione.text()


def test_find_table_si_ferma_alla_prima(tmp_path: Path):
    percorso = tmp_path / "d.md"
    percorso.write_text(
        "# T\n\n| A |\n|---|\n| 1 |\n\ntesto\n\n| B |\n|---|\n| 2 |\n", encoding="utf-8"
    )
    trovata = parse_document(read_text(percorso)).find_table("T")
    assert trovata is not None and trovata[0] == ["A"]


# -- Modelli -----------------------------------------------------------------

@pytest.mark.parametrize("valore,atteso", [("si", True), ("yes", True), ("1", True), ("no", False)])
def test_mandatory_scritto_come_stringa(valore, atteso):
    assert TestDefinition.from_json({"test_id": "T1", "mandatory": valore}).mandatory is atteso


# -- Stati intermedi del calcolo --------------------------------------------

def _ctx() -> StatusContext:
    return StatusContext(freshness_policy="latest-known", current_revision="abc",
                         worktree_dirty=False, require_tasks_for_implemented=True)


def _requisito(**kwargs) -> Requirement:
    base = dict(key="001-x/FR-001", requirement_id="FR-001", feature_id="001-x",
                text="il sistema deve fare qualcosa", fingerprint="fp1")
    base.update(kwargs)
    return Requirement(**base)


def _raccogli():
    trovati: list[dict] = []

    def factory(**kwargs):
        trovati.append(kwargs)
        return kwargs

    return trovati, factory


def test_test_collegato_ma_non_obbligatorio(project: Path, cli):
    """"Sono collegati solo test non obbligatori": il requisito non puo'
    raggiungere `tested`."""
    (project / "specs" / "001-demo" / "tasks.md").write_text(
        "# Task\n- [x] T001 [REQ:FR-001] auth in src/auth.py\n", encoding="utf-8")
    cli("init")
    cli("test", "define", "TEST-1", "--actor", "qa", "--reason", "r",
        "--requirement", "001-demo/FR-001", "--definition", "verifica")  # senza --mandatory
    cli("refresh")
    aperti = [
        json.loads(l) for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    assert any(f["finding_type"] == "missing-mandatory-test"
               and "non obbligatori" in f["description"] for f in aperti)


def test_task_completi_senza_evidenza_di_codice(project: Path, cli):
    (project / "specs" / "001-demo" / "tasks.md").write_text(
        "# Task\n- [x] T001 [REQ:NFR-001] latency\n", encoding="utf-8")
    cli("init")
    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "tasks-complete-without-code-evidence" in tipi


def test_esito_pass_senza_evidenza_verificabile(project: Path, cli):
    """"Esito 'pass' privo di evidenza verificabile": il pass non conta."""
    (project / "specs" / "001-demo" / "tasks.md").write_text(
        "# Task\n- [x] T001 [REQ:FR-001] auth in src/auth.py\n", encoding="utf-8")
    cli("init")
    cli("test", "define", "TEST-1", "--actor", "qa", "--reason", "r",
        "--requirement", "001-demo/FR-001", "--definition", "verifica", "--mandatory")
    cli("refresh")

    percorso = project / "requirement-burnup" / "state" / "test-runs.jsonl"
    percorso.write_text(json.dumps({
        "run_id": "R1", "test_id": "TEST-1", "result": "pass", "executed_at": now_iso(),
        "evidence_hash": "", "run_identity": "manuale-1",
    }) + "\n", encoding="utf-8")
    cli("refresh")

    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "missing-evidence" in tipi


def test_test_obbligatorio_fallito(project: Path, cli):
    (project / "specs" / "001-demo" / "tasks.md").write_text(
        "# Task\n- [x] T001 [REQ:FR-001] auth in src/auth.py\n", encoding="utf-8")
    cli("init")
    cli("test", "define", "TEST-1", "--actor", "qa", "--reason", "r",
        "--requirement", "001-demo/FR-001", "--definition", "verifica", "--mandatory")
    cli("test", "confirm-manual", "TEST-1", "--actor", "qa", "--reason", "esito reale",
        "--result", "fail", "--evidence", "verbale")
    cli("refresh")
    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "failing-mandatory-test" in tipi


def test_relazione_confermata_a_mano_sopravvive_al_refresh(project: Path, cli):
    cli("init")
    cli("link", "confirm", "001-demo/FR-001", "T900", "--type", "implemented-by",
        "--actor", "tl", "--reason", "task in un altro repository")
    cli("refresh")
    relazioni = [
        json.loads(l) for l in (project / "requirement-burnup" / "state" / "relations.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    assert any(r["to_ref"] == "T900" for r in relazioni)


def test_test_orphan(project: Path, cli):
    cli("init")
    cli("test", "define", "TEST-1", "--actor", "qa", "--reason", "r", "--allow-unknown",
        "--requirement", "001-demo/FR-777", "--definition", "verifica un requisito inesistente")
    cli("refresh")
    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "test-orphan" in tipi


# -- Store -------------------------------------------------------------------

def test_stato_non_serializzabile(tmp_path: Path):
    store = Store(tmp_path / "out")
    dati = StoreData(manifest={"non_serializzabile": {1, 2, 3}})
    with pytest.raises(InvariantError):
        store.commit(dati)


def test_lo_store_dichiara_di_dover_essere_versionato():
    """Il canonical store e' la storia del progetto, non un artefatto
    rigenerabile: il modulo lo dice a chi genera il .gitignore."""
    from burnup import store as modulo

    testo = "\n".join(
        str(v) for v in vars(modulo).values() if isinstance(v, str)
    ) + modulo.__doc__
    assert "verita" in testo.lower() or "versionat" in testo.lower()


# -- Layout ------------------------------------------------------------------

def test_nessuna_cartella_di_spec(tmp_path: Path):
    with pytest.raises(SpecsLayoutError):
        detect_specs_root(tmp_path)


def test_sorgente_illeggibile_viene_segnalato(project: Path, cli, monkeypatch):
    from burnup import specscan

    originale = Path.read_text

    def rifiuta(self, *args, **kwargs):
        if self.name == "auth.py":
            raise OSError("permesso negato")
        return originale(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", rifiuta)
    cli("init")
    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "unreadable-source" in tipi


# -- CLI ---------------------------------------------------------------------

def test_conferma_manuale_con_test_id_sconosciuto(project: Path, cli):
    cli("init")
    cli("test", "confirm-manual", "TEST-IGNOTO", "--actor", "qa", "--reason", "r",
        "--result", "pass", "--evidence", "e", expect=ExitCode.CONFIG_ERROR)


def test_chiusura_di_un_finding_inesistente(project: Path, cli):
    cli("init")
    cli("finding", "close", "FND-IGNOTO", "--actor", "u", "--reason", "r",
        expect=ExitCode.CONFIG_ERROR)


def test_primo_snapshot_e_marcato_initial(project: Path, cli):
    cli("init")
    snapshot = [
        json.loads(l) for l in (project / "requirement-burnup" / "state" / "snapshots.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    assert snapshot and snapshot[0]["reason"] in ("initial", "forced")


def test_gate_reject_registra_il_rifiuto(project: Path, cli):
    cli("init")
    cli("gate", "reject", "001-demo", "1", "--actor", "pm", "--reason", "requisiti ambigui")
    _, out, _ = cli("gate", "status", "001-demo", "--json")
    assert json.loads(out)["gates"]["1"]["status"] == "rejected"


# -- Guasti di sistema -------------------------------------------------------

def test_output_dir_non_confrontabile_con_la_radice(tmp_path: Path, monkeypatch):
    """Se `output_dir` non e' esprimibile come relativo alla radice, il calcolo
    dello sporco non deve saltare: si limita a non escludere nulla."""
    from burnup import engine

    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "i"], cwd=tmp_path, check=True, capture_output=True)

    revisione, _, motivo = engine.git_revision(tmp_path, Path("/tmp") / "del-tutto-altrove")
    assert revisione and not motivo


def test_git_status_che_fallisce_non_interrompe(tmp_path: Path, monkeypatch):
    from burnup import engine

    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@e"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "i"], cwd=tmp_path, check=True, capture_output=True)

    originale = engine.subprocess.run
    chiamate = {"n": 0}

    def prima_ok_poi_esplode(*args, **kwargs):
        chiamate["n"] += 1
        if chiamate["n"] == 1:
            return originale(*args, **kwargs)
        raise OSError("git status non disponibile")

    monkeypatch.setattr(engine.subprocess, "run", prima_ok_poi_esplode)
    revisione, sporco, _ = engine.git_revision(tmp_path, tmp_path / "out")
    assert revisione and sporco is False


def test_scrittura_su_directory_non_scrivibile(tmp_path: Path, monkeypatch):
    from burnup import store as modulo

    def rifiuta(*args, **kwargs):
        raise OSError("disco pieno")

    monkeypatch.setattr(modulo, "atomic_write_text", rifiuta)
    with pytest.raises(StoreError):
        Store(tmp_path / "out").commit(StoreData())


def test_store_senza_alcun_refresh_registrato(project: Path, cli):
    cli("init")
    manifesto = project / "requirement-burnup" / "state" / "scan-manifest.json"
    contenuto = json.loads(manifesto.read_text(encoding="utf-8"))
    contenuto.pop("scanned_at", None)
    manifesto.write_text(json.dumps(contenuto), encoding="utf-8")
    _, out, _ = cli("status", "--json")
    assert json.loads(out)["freshness"] == "unknown"
