"""Difetti trovati facendo girare il framework su un progetto vero.

Ogni test qui nasce da una riproduzione in simulazione end-to-end (2026-08-09),
non da una lettura del codice: un progetto Spec Kit reale, sei agenti
impersonati nell'ordine prescritto da `CLAUDE.md`, pytest vero, JUnit vero,
Git vero. Sono i difetti che nessuna suite unitaria poteva vedere, perche'
stanno nell'attrito fra l'engine e gli strumenti che lo circondano.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from burnup.errors import ExitCode
from burnup.specscan import _TASK_LINE_RE
from burnup.status import StatusContext, evaluate_freshness
from burnup.models import TestRun


# -- C-21: confronto fra revisione abbreviata e revisione completa ----------
#
# L'engine legge la propria revisione con `git rev-parse --short HEAD` (7
# caratteri) e la confronta per uguaglianza di stringa con quella dichiarata
# dal sidecar del report. Una pipeline che scrive `git rev-parse HEAD` — la
# forma canonica, quella che si ottiene senza flag — produce 40 caratteri:
# stesso commit, confronto fallito, evidenza dichiarata stantia per sempre.
#
# Conseguenza riprodotta in simulazione: `current-revision`, che il template
# della configurazione presenta come "la policy rigorosa", non e' soddisfabile;
# ogni requisito resta `implemented`, `requirement-not-verified` (high) resta
# aperto e il Gate 4 non e' mai approvabile. Il messaggio diagnostico stampa
# le due stringhe una accanto all'altra — "eseguito su e8d3138e4915...,
# la revisione corrente e' e8d3138" — e si legge come se fossero due commit
# diversi.

SHA_LUNGO = "e8d3138e49155e8feefe20a9fe3ceb0432a0d96c"
SHA_CORTO = "e8d3138"


def _contesto(revisione_corrente: str) -> StatusContext:
    return StatusContext(
        freshness_policy="current-revision",
        current_revision=revisione_corrente,
        worktree_dirty=False,
        require_tasks_for_implemented=True,
    )


def _esecuzione(revisione: str) -> TestRun:
    return TestRun(
        run_id="RUN-1",
        run_identity="id-1",
        test_id="TEST-001",
        result="pass",
        executed_at="2026-08-09T10:00:00Z",
        source_revision=revisione,
        revision_origin="sidecar",
    )


def test_sidecar_con_sha_completo_soddisfa_la_policy():
    """`git rev-parse HEAD` e `git rev-parse --short HEAD` sono lo stesso commit."""
    verdetto = evaluate_freshness(_esecuzione(SHA_LUNGO), _contesto(SHA_CORTO))
    assert verdetto.fresh, verdetto.reason


def test_revisione_corrente_completa_e_sidecar_abbreviato():
    """Vale anche al contrario: l'engine potrebbe avere la forma lunga."""
    assert evaluate_freshness(_esecuzione(SHA_CORTO), _contesto(SHA_LUNGO)).fresh


def test_due_commit_diversi_restano_distinti():
    """Il confronto tollerante non deve diventare permissivo."""
    verdetto = evaluate_freshness(_esecuzione("a" * 40), _contesto("b234567"))
    assert not verdetto.fresh


def test_prefisso_troppo_corto_non_basta():
    """Un prefisso di 4 caratteri e' ambiguo: non vale come identita'."""
    assert not evaluate_freshness(_esecuzione("e8d3"), _contesto(SHA_LUNGO)).fresh


# -- C-20: una riga di task non riconosciuta sparisce senza rilievo ---------
#
# La regex pretende l'ID del task nudo subito dopo la casella. Un ID in
# grassetto — `- [x] **T001** [REQ:FR-001] ...`, forma frequentissima nel
# Markdown generato — non combacia, e la riga viene saltata in silenzio.
#
# Il sintomo osservato in simulazione non punta alla causa: ogni requisito
# riceve `incomplete-tasks`, quindi si va a guardare `tasks.md`, lo si trova
# tutto spuntato, e si conclude che l'engine sbaglia i conti. L'engine ha un
# vocabolario ricco di rilievi per "ho visto qualcosa e non ho potuto usarlo"
# (`unreadable-report`, `unnamed-test-result`, `marker-inside-string`,
# `unmatched-test-report`): per i task, che sono l'input primario della
# tracciabilita', non ne aveva nessuno.

@pytest.mark.parametrize(
    "riga",
    [
        "- [x] **T001** [REQ:FR-001] Registrare un prestito",
        "- [ ] **T002** [REQ:FR-002] Rifiutare la copia",
        "- [x] __T003__ [REQ:FR-003] Registrare la restituzione",
        "- [x] `T004` [REQ:FR-004] Elencare gli scaduti",
    ],
)
def test_id_del_task_con_enfasi_markdown(riga):
    """L'enfasi e' formattazione, non semantica: l'ID sotto e' lo stesso."""
    m = _TASK_LINE_RE.match(riga)
    assert m is not None, f"riga non riconosciuta: {riga}"
    assert m.group(2).upper().startswith("T")


def test_il_formato_del_preset_resta_valido():
    """La forma prescritta da `sdd-traceability-preset` non deve regredire."""
    riga = "- [ ] T014 [P] [US2] [REQ:FR-003,NFR-002] Implementa la validazione"
    m = _TASK_LINE_RE.match(riga)
    assert m is not None and m.group(2) == "T014"


def test_riga_che_non_e_un_task_resta_esclusa():
    """La tolleranza non deve far entrare righe che task non sono."""
    assert _TASK_LINE_RE.match("- [x] Sistemare la build") is None
    assert _TASK_LINE_RE.match("Testo qualsiasi con T001 dentro") is None


# -- C-19: un'eccezione inattesa esce con il codice sbagliato ---------------
#
# `main()` intercetta `BurnupError` e `KeyboardInterrupt`. Qualunque altra
# eccezione — un errore del filesystem, un bug dell'engine — risale come
# traceback grezzo e il processo esce con 1, che il contratto riserva a
# CONFIG_ERROR: "correggi il file; nessun artefatto e' stato scritto".
#
# E' esattamente il difetto che il docstring di `errors.py` dichiara di aver
# chiuso: "la v3 [...] intercettava solo due tipi di eccezione, lasciando
# propagare tutto il resto come traceback grezzo con exit code 1".
#
# Riprodotto per caso in simulazione: su un filesystem che nega `unlink`, il
# rilascio del lock del canonical store ha prodotto un `PermissionError` e un
# traceback di dodici righe.

def test_eccezione_inattesa_esce_con_engine_error(monkeypatch, capsys):
    from burnup import cli

    def esplodi(_args):
        raise OSError("il filesystem non permette unlink")

    monkeypatch.setattr(cli, "cmd_status", esplodi, raising=False)
    parser = cli.build_parser()
    args = parser.parse_args(["status"])
    args.func = esplodi

    monkeypatch.setattr(cli, "build_parser", lambda: _ParserFinto(args))
    assert cli.main(["status"]) == ExitCode.ENGINE_ERROR
    assert "traceback" not in capsys.readouterr().err.lower()


class _ParserFinto:
    def __init__(self, args):
        self._args = args

    def parse_args(self, argv=None):
        return self._args


def test_il_messaggio_dice_che_e_un_bug(monkeypatch, capsys):
    """Chi legge deve capire che non e' colpa della sua configurazione."""
    from burnup import cli

    def esplodi(_args):
        raise RuntimeError("invariante rotta")

    args = cli.build_parser().parse_args(["status"])
    args.func = esplodi
    monkeypatch.setattr(cli, "build_parser", lambda: _ParserFinto(args))

    assert cli.main(["status"]) == ExitCode.ENGINE_ERROR
    err = capsys.readouterr().err.lower()
    assert "bug" in err or "engine" in err


# -- C-26: l'elenco dei finding non puo' crescere con il progetto ----------
#
# In simulazione, 486 requisiti senza verifica producevano 491 righe di output.
# Il consumatore principale e' un agente con una finestra di contesto finita:
# la lunghezza dell'output non puo' dipendere dalla dimensione del progetto.

def _finding_finti(n: int, tipo: str = "requirement-not-verified"):
    from burnup.models import Finding

    return [
        Finding(
            finding_id=f"FND-{i:04X}",
            severity="high",
            finding_type=tipo,
            subject=f"001-f/FR-{i:03d}",
            subject_type="requirement",
            feature_id="001-f",
            description="Requisito attivo non verificato.",
            recommended_action="Verificalo.",
        )
        for i in range(n)
    ]


def test_pochi_finding_sono_elencati_per_esteso():
    from burnup.cli import _righe_finding

    righe = _righe_finding(_finding_finti(3))
    assert len(righe) == 3
    assert all("e altri" not in r for r in righe)


def test_molti_finding_vengono_riassunti():
    from burnup.cli import MAX_FINDING_ELENCATI, _righe_finding

    righe = _righe_finding(_finding_finti(486))
    assert len(righe) == MAX_FINDING_ELENCATI + 2
    coda = righe[-2]
    assert f"altri {486 - MAX_FINDING_ELENCATI}" in coda
    assert "requirement-not-verified" in coda, "il riassunto deve dire di che tipo sono"
    assert "--json" in righe[-1], "deve indicare dove leggere l'elenco completo"


def test_il_riassunto_raggruppa_per_tipo():
    from burnup.cli import MAX_FINDING_ELENCATI, _righe_finding

    misti = _finding_finti(MAX_FINDING_ELENCATI + 5) + _finding_finti(3, "failing-mandatory-test")
    coda = _righe_finding(misti)[-2]
    assert "failing-mandatory-test" in coda and "requirement-not-verified" in coda


# -- C-24: la vista umana deve dire quali gate esistono --------------------

def test_gate_non_previsti_sono_marcati_tali():
    from burnup.gates import GATE_SEQUENCE, GateState, format_gate_report

    stati = {g: GateState(gate=g, status="not-approved", decision=None) for g in GATE_SEQUENCE}
    righe = format_gate_report("002-refuso", stati, "fast-track")
    testo = "\n".join(righe)
    assert "fast-track" in righe[0] and "gate previsti: 1, 4" in righe[0]
    assert "Gate 2 — Solution Baseline: non previsto" in testo
    assert "Gate 3 — Implementation Readiness: non previsto" in testo
    assert "Gate 1 — Requirements Baseline: not-approved" in testo


def test_senza_classe_si_mostrano_tutti_i_gate():
    """Compatibilita': il chiamante che non passa la classe vede tutto."""
    from burnup.gates import GATE_SEQUENCE, GateState, format_gate_report

    stati = {g: GateState(gate=g, status="not-approved", decision=None) for g in GATE_SEQUENCE}
    testo = "\n".join(format_gate_report("001-f", stati))
    assert "non previsto" not in testo


# -- C-23: il rilievo deve nominare i file sporchi -------------------------

def test_elenco_sporchi_nomina_i_file():
    from burnup.engine import _elenco_sporchi

    assert _elenco_sporchi(["src/a.py", "specs/001/spec.md"]) == "src/a.py, specs/001/spec.md"


def test_elenco_sporchi_si_ferma_e_riassume():
    from burnup.engine import _MAX_SPORCHI, _elenco_sporchi

    testo = _elenco_sporchi([f"f{i}.py" for i in range(_MAX_SPORCHI + 4)])
    assert testo.endswith("e altri 4")


def test_elenco_sporchi_senza_dati():
    from burnup.engine import _elenco_sporchi

    assert "non disponibile" in _elenco_sporchi([])


def test_percorsi_sporchi_su_directory_non_git(tmp_path):
    from burnup.engine import percorsi_sporchi

    assert percorsi_sporchi(tmp_path) == []


def test_percorsi_sporchi_elenca_le_modifiche(tmp_path):
    from burnup.engine import percorsi_sporchi

    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("uno", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "c"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("due", encoding="utf-8")
    assert percorsi_sporchi(tmp_path) == ["a.py"]


def test_percorsi_sporchi_esclude_la_directory_di_output(tmp_path):
    from burnup.engine import percorsi_sporchi

    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "r.md").write_text("uno", encoding="utf-8")
    (tmp_path / "a.py").write_text("uno", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "c"], cwd=tmp_path, check=True)
    (tmp_path / "out" / "r.md").write_text("due", encoding="utf-8")
    assert percorsi_sporchi(tmp_path, tmp_path / "out") == []


def test_percorsi_sporchi_con_output_fuori_dalla_radice(tmp_path):
    """`relative_to` fallisce: si ricade sul confronto senza esclusione."""
    from burnup.engine import percorsi_sporchi

    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    assert percorsi_sporchi(tmp_path, tmp_path.parent / "altrove") == []


def test_revisione_vuota_non_e_mai_uguale():
    from burnup.status import stessa_revisione

    assert not stessa_revisione("", SHA_LUNGO)
    assert not stessa_revisione(SHA_LUNGO, "")


def test_percorsi_sporchi_quando_git_fallisce(tmp_path, monkeypatch):
    """`git status` che esce non-zero non deve inventare un elenco."""
    from burnup import engine

    class _Esito:
        returncode = 128
        stdout = ""

    monkeypatch.setattr(engine.subprocess, "run", lambda *a, **k: _Esito())
    assert engine.percorsi_sporchi(tmp_path) == []


def test_percorsi_sporchi_quando_git_non_si_avvia(tmp_path, monkeypatch):
    from burnup import engine

    def esplodi(*a, **k):
        raise OSError("git assente")

    monkeypatch.setattr(engine.subprocess, "run", esplodi)
    assert engine.percorsi_sporchi(tmp_path) == []


def test_percorsi_sporchi_ignora_righe_troppo_corte(tmp_path, monkeypatch):
    from burnup import engine

    class _Esito:
        returncode = 0
        stdout = " M src/a.py\n\nXY\n"

    monkeypatch.setattr(engine.subprocess, "run", lambda *a, **k: _Esito())
    assert engine.percorsi_sporchi(tmp_path) == ["src/a.py"]


def test_percorsi_sporchi_su_rinomina(tmp_path, monkeypatch):
    """`R  vecchio -> nuovo`: il file che conta e' la destinazione."""
    from burnup import engine

    class _Esito:
        returncode = 0
        stdout = "R  specs/vecchio.md -> specs/nuovo.md\n"

    monkeypatch.setattr(engine.subprocess, "run", lambda *a, **k: _Esito())
    assert engine.percorsi_sporchi(tmp_path) == ["specs/nuovo.md"]


def test_errore_inatteso_in_json(monkeypatch, capsys):
    """Anche in `--json` l'errore deve essere machine-readable, non un traceback."""
    from burnup import cli

    def esplodi(_args):
        raise RuntimeError("invariante rotta")

    args = cli.build_parser().parse_args(["status", "--json"])
    args.func = esplodi
    monkeypatch.setattr(cli, "build_parser", lambda: _ParserFinto(args))

    assert cli.main(["status", "--json"]) == ExitCode.ENGINE_ERROR
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "engine-error"
    assert payload["exit_code"] == ExitCode.ENGINE_ERROR
