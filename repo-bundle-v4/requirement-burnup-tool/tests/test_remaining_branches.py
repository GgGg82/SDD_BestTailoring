"""Gli ultimi rami non esercitati.

Chiude la copertura. Ogni test qui resta legato a un comportamento osservabile —
un messaggio, un rifiuto, una riga scartata — non alla semplice esecuzione di
un'istruzione: coprire per il numero produrrebbe test che non falliscono mai
quando qualcosa si rompe davvero, che e' peggio di una riga scoperta.

Le uniche righe deliberatamente escluse sono marcate `# pragma: no cover` nel
sorgente, con la ragione accanto: il guard `__main__` e il gestore di
`KeyboardInterrupt`, che si raggiungono solo con un processo reale e un segnale
reale.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from burnup.config import load_config
from burnup.errors import ConfigError, ExitCode, LockError, PathConfinementError
from burnup.gates import GateDecision, evaluate_gates
from burnup.ids import now_iso
from burnup.ingest import parse_generic_json, parse_junit
from burnup.mdparse import escape_cell
from burnup.paths import expand_globs, resolve_under_root
from burnup.risk_link import parse_id_list
from burnup.status import StatusContext, evaluate_freshness
from burnup.store import Store, StoreData, StoreLock
from conftest import CONFIG_YML


def carica(tmp_path: Path, *sostituzioni: tuple[str, str]):
    testo = CONFIG_YML
    for prima, dopo in sostituzioni:
        testo = testo.replace(prima, dopo)
    percorso = tmp_path / "requirement-burnup-config.yml"
    percorso.write_text(testo, encoding="utf-8")
    return load_config(percorso, tmp_path)


# -- Configurazione: chiavi mancanti e valori fuori dominio ---------------

def test_sezione_obbligatoria_assente(tmp_path: Path):
    percorso = tmp_path / "requirement-burnup-config.yml"
    percorso.write_text('schema_version: "2.0"\noutput_dir: "out"\n', encoding="utf-8")
    with pytest.raises(ConfigError) as errore:
        load_config(percorso, tmp_path)
    assert "inputs" in str(errore.value) or "requirements" in str(errore.value)


def test_schema_version_vuoto(tmp_path: Path):
    with pytest.raises(ConfigError) as errore:
        carica(tmp_path, ('schema_version: "2.0"', 'schema_version: ""'))
    assert "schema_version" in (errore.value.hint or "") + str(errore.value)


def test_default_scope_state_fuori_dominio(tmp_path: Path):
    with pytest.raises(ConfigError) as errore:
        carica(tmp_path, ("requirements:", 'requirements:\n  default_scope_state: "inventato"'))
    assert "default_scope_state" in str(errore.value)


def test_marker_senza_gruppo_di_cattura(tmp_path: Path):
    """Il gruppo 1 deve catturare la chiave composita: senza, non c'e' nulla da leggere."""
    with pytest.raises(ConfigError) as errore:
        carica(tmp_path, ('code_evidence_marker: "REQ:\\\\s*([A-Za-z0-9_.\\\\-]+/[A-Za-z0-9_\\\\-]+)"',
                          'code_evidence_marker: "REQ:"'))
    assert "gruppo" in str(errore.value).lower() or "Esempio" in (errore.value.hint or "")


# -- Percorsi ---------------------------------------------------------------

def test_percorso_vuoto_rifiutato(tmp_path: Path):
    with pytest.raises(PathConfinementError):
        resolve_under_root(tmp_path, "   ", field="output_dir")


def test_percorso_con_segmenti_neutri(tmp_path: Path):
    """`./out/./` e `out` sono lo stesso percorso: i segmenti neutri si saltano."""
    assert resolve_under_root(tmp_path, "./out/.", field="output_dir") == (tmp_path / "out")


def test_pattern_vuoto_nella_lista_dei_glob(tmp_path: Path):
    (tmp_path / "vero.py").write_text("x", encoding="utf-8")
    trovati = expand_globs(tmp_path, ["", "   ", "**/*.py"], field="source_globs")
    assert [p.name for p in trovati] == ["vero.py"]


def test_lo_stesso_file_raggiunto_da_due_glob_conta_una_volta(tmp_path: Path):
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    trovati = expand_globs(tmp_path, ["**/*.py", "a.py"], field="source_globs")
    assert len(trovati) == 1


# -- Markdown e risk register ------------------------------------------------

def test_cella_nulla_diventa_stringa_vuota():
    """Il round-trip deve reggere anche su una cella assente."""
    assert escape_cell(None) == ""


def test_lista_di_id_vuota():
    assert parse_id_list("") == []
    assert parse_id_list("—") == []


# -- Importazione ------------------------------------------------------------

def test_esito_fuori_dominio_diventa_error(tmp_path: Path):
    """Un esito che non riconosciamo non puo' valere come `pass`."""
    report = tmp_path / "r.json"
    report.write_text(
        json.dumps([{"id": "TEST-1", "result": "verdolino", "timestamp": "2026-01-01T00:00:00Z"}]),
        encoding="utf-8",
    )
    assert parse_generic_json(report, {})[0].result == "error"


def test_testsuite_annidati_non_duplicano_i_casi(tmp_path: Path):
    """JUnit ammette `<testsuite>` dentro `<testsuite>`: ogni caso va contato una volta."""
    report = tmp_path / "j.xml"
    report.write_text(
        '<?xml version="1.0"?><testsuites>'
        '<testsuite name="esterno" timestamp="2026-01-01T00:00:00">'
        '<testsuite name="interno" timestamp="2026-01-01T00:00:00">'
        '<testcase classname="c" name="T1"/>'
        "</testsuite></testsuite></testsuites>",
        encoding="utf-8",
    )
    assert len(parse_junit(report, {})) == 1


def test_file_con_estensione_non_supportata_viene_saltato(project: Path, cli):
    (project / "test-results" / "note.txt").write_text("non è un report", encoding="utf-8")
    config = project / "requirement-burnup-config.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            'test_report_globs: ["test-results/**/*.xml", "test-results/**/*.json"]',
            'test_report_globs: ["test-results/**/*"]',
        ),
        encoding="utf-8",
    )
    cli("init")  # non deve sollevare né segnalare un report illeggibile
    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "unreadable-report" not in tipi


# -- Specscan ----------------------------------------------------------------

def test_requisito_senza_testo_normativo_non_entra_nello_scope(project: Path, cli):
    spec = project / "specs" / "001-demo" / "spec.md"
    spec.write_text(
        spec.read_text(encoding="utf-8") + "\n- **FR-500**:\n", encoding="utf-8"
    )
    cli("init")
    chiavi = {
        r["requirement_id"]
        for r in json.loads(
            (project / "requirement-burnup" / "state" / "requirements.json").read_text(encoding="utf-8")
        )
    }
    assert "FR-500" not in chiavi


def test_marcatore_dentro_una_stringa_di_codice(project: Path, cli):
    """Il marcatore e' in un commento, ma dopo un apice aperto: sta dentro una
    stringa citata nel commento, non e' una dichiarazione di tracciabilita'."""
    (project / "src" / "auth.py").write_text(
        '"""Auth."""\n# esempio da non copiare: "REQ: 001-demo/FR-001\ndef auth(): return True\n',
        encoding="utf-8",
    )
    cli("init")
    tipi = {
        json.loads(l)["finding_type"]
        for l in (project / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "marker-inside-string" in tipi


# -- Stato e gate ------------------------------------------------------------

def test_current_revision_senza_revisione_dichiarata_dal_report():
    contesto = StatusContext(freshness_policy="current-revision", current_revision="abc",
                             worktree_dirty=False, require_tasks_for_implemented=True)
    from burnup.models import TestRun

    run = TestRun(run_id="R1", test_id="T1", result="pass", executed_at=now_iso(),
                  evidence_hash="h", source_revision="", revision_origin="unknown",
                  run_identity="x")
    verdetto = evaluate_freshness(run, contesto)
    assert not verdetto.fresh and "revisione" in verdetto.reason


def test_gate_su_un_artefatto_che_non_e_mai_esistito():
    """`code` non e' registrato ne' presente: non e' un cambiamento."""
    decisione = GateDecision(
        decision_id="d", feature_id="f", gate=4, outcome="approved", approver="u",
        approved_at=now_iso(), rationale="ok", artifact_fingerprints={"spec": "fp"},
    )
    stati = evaluate_gates("f", [decisione], {"spec": "fp"})
    assert stati[4].status == "valid"


def test_primo_snapshot_senza_storia_precedente(tmp_path: Path):
    from burnup.engine import should_snapshot
    from burnup.models import Counts

    conteggi = Counts(scope=1, defined=1, implemented=0, tested=0, removed_total=0,
                      scope_fingerprint="fp")
    fatto, motivo = should_snapshot(None, conteggi, False)
    assert fatto and motivo == "initial"


def test_revisione_non_disponibile_con_policy_rigorosa(tmp_path: Path):
    """Senza Git e con `current-revision`, il sistema deve dirlo invece di
    lasciar credere che i test siano freschi."""
    (tmp_path / "specs" / "001-x").mkdir(parents=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "specs" / "001-x" / "spec.md").write_text(
        "# S\n\n## Requirements\n\n- **FR-001**: il sistema deve fare qualcosa\n", encoding="utf-8")
    (tmp_path / "requirement-burnup-config.yml").write_text(
        CONFIG_YML.replace('test_freshness_policy: "manual-confirmation"',
                           'test_freshness_policy: "current-revision"'),
        encoding="utf-8",
    )
    from burnup.cli import main
    import contextlib
    import io

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        codice = main(["init", "--project-root", str(tmp_path)])
    assert codice == ExitCode.OK

    tipi = {
        json.loads(l)["finding_type"]
        for l in (tmp_path / "requirement-burnup" / "state" / "findings.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()
    }
    assert "revision-unavailable" in tipi


# -- Relazioni non correnti nella Matrix -------------------------------------

def test_una_relazione_decaduta_non_compare_come_evidenza(project: Path, cli):
    cli("init")
    percorso = project / "requirement-burnup" / "state" / "relations.jsonl"
    righe = percorso.read_text(encoding="utf-8").splitlines()
    decaduta = json.loads(righe[0])
    decaduta["valid_to"] = now_iso()
    decaduta["to_ref"] = "T-DECADUTA"
    percorso.write_text("\n".join(righe + [json.dumps(decaduta)]) + "\n", encoding="utf-8")

    from burnup.render import render_matrix
    from burnup.store import Store

    dati = Store(project / "requirement-burnup").load()
    assert "T-DECADUTA" not in render_matrix(
        dati.requirements, dati.relations, dati.findings, dati.manifest
    )


# -- Lock --------------------------------------------------------------------

def test_lock_gia_preso(tmp_path: Path):
    stato = tmp_path / "state"
    stato.mkdir(parents=True)
    with StoreLock(stato, timeout=0.1):
        with pytest.raises(LockError) as errore:
            with StoreLock(stato, timeout=0.1):
                pass
    assert "processo" in str(errore.value)


def test_lock_con_file_illeggibile(tmp_path: Path, monkeypatch):
    """Se il file di lock non e' leggibile, il messaggio dice comunque
    qualcosa di utile invece di propagare l'errore di I/O."""
    stato = tmp_path / "state"
    stato.mkdir(parents=True)
    with StoreLock(stato, timeout=0.1):
        originale = Path.read_text

        def rifiuta(self, *args, **kwargs):
            if self.name == ".lock":
                raise OSError("illeggibile")
            return originale(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", rifiuta)
        with pytest.raises(LockError) as errore:
            with StoreLock(stato, timeout=0.1):
                pass
    assert "sconosciuto" in str(errore.value)


def test_il_suggerimento_per_il_gitignore_dello_store(tmp_path: Path):
    testo = Store(tmp_path / "out").gitignore_hint()
    assert "VA versionato" in testo


# -- CLI: rami di errore residui ---------------------------------------------

def test_test_define_su_requisito_inesistente(project: Path, cli):
    cli("init")
    cli("test", "define", "TEST-1", "--actor", "qa", "--reason", "r",
        "--requirement", "001-demo/FR-999", "--definition", "verifica",
        expect=ExitCode.CONFIG_ERROR)


def test_requirement_remove_su_chiave_inesistente(project: Path, cli):
    cli("init")
    cli("requirement", "remove", "001-demo/FR-888", "--actor", "u", "--reason", "fuori perimetro",
        expect=ExitCode.CONFIG_ERROR)


def test_link_confirm_su_requisito_inesistente(project: Path, cli):
    """`link confirm` conferma una relazione: il requisito deve esistere."""
    cli("init")
    cli("link", "confirm", "001-demo/FR-404", "T900", "--type", "implemented-by",
        "--actor", "tl", "--reason", "collegamento a un task esterno",
        expect=ExitCode.CONFIG_ERROR)


def test_percorso_con_segmento_corrente_esplicito(tmp_path: Path):
    """`out/./sotto` e `out/sotto` sono lo stesso percorso: il segmento `.`
    va saltato senza contare come discesa."""
    assert resolve_under_root(tmp_path, "out/./sotto", field="output_dir") == (
        tmp_path / "out" / "sotto"
    )


def test_riga_con_id_ma_senza_testo_non_e_un_requisito(project: Path, cli):
    """Un ID senza testo normativo non descrive nulla: non entra nello scope
    e non genera nemmeno un rimando."""
    spec = project / "specs" / "001-demo" / "spec.md"
    spec.write_text(
        spec.read_text(encoding="utf-8").replace(
            "- **NFR-001**: la risposta deve arrivare entro 100ms",
            "- **NFR-001**: la risposta deve arrivare entro 100ms\n- **FR-700**:   ",
        ),
        encoding="utf-8",
    )
    cli("init")
    presenti = {
        r["requirement_id"]
        for r in json.loads(
            (project / "requirement-burnup" / "state" / "requirements.json").read_text(encoding="utf-8")
        )
    }
    assert "FR-700" not in presenti and "FR-001" in presenti
