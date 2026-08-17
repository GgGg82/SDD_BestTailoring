"""Terzo giro di collaudo (2026-08-07): i perimetri fuori dall'engine.

Il primo giro ha battuto il comportamento, il secondo il contratto della CLI e
della configurazione. Restavano il hook di allowlist, i documenti normativi non
ancora verificati, la CI e i file agente.

Questi test leggono file che stanno **fuori** dal pacchetto Python. Se il
pacchetto e' installato da solo, senza il bundle attorno, vengono saltati invece
di fallire: la loro assenza non e' un difetto del pacchetto.

Difetti chiusi qui:

* **C-11** — il hook validava solo il primo segmento di una catena, quindi
  `ls && npm install <qualunque cosa>` passava.
* **C-12** — senza il nome dell'agente nel payload, il hook applicava
  l'allowlist dei Checker a chiunque, bloccando i Maker che hanno Bash.
* **C-13** — la tabella degli agenti in `CLAUDE.md` ometteva lo step 0.1, che
  la prosa dello stesso file, il file agente e il progress-template assegnano
  tutti al Solutions Architect.
* **C-14** — la tabella dei finding in `OPERATING-PROCEDURE.md` non elencava
  tutti i tipi che l'engine sa emettere.
* **C-15** — la tabella degli exit code dello stesso documento non riportava
  il codice 4.
* **C-16** — il nome del job della CI dichiarava un numero di probe diverso da
  quello reale.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

BUNDLE = Path(__file__).resolve().parent.parent.parent
HOOK = BUNDLE / ".claude" / "hooks" / "auditor-bash-allowlist.py"
DOCS = BUNDLE / "docs"
CLAUDE_MD = BUNDLE / "CLAUDE.md"
CI = BUNDLE / ".github" / "workflows" / "ci.yml"

fuori_bundle = pytest.mark.skipif(
    not HOOK.exists(), reason="pacchetto installato senza il bundle attorno"
)


def esegui_hook(command: str, agent: str | None = "technical-auditor") -> int:
    payload: dict = {"tool_input": {"command": command}}
    if agent is not None:
        payload["agent"] = agent
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True,
    )
    return proc.returncode


# -- C-11 · catene di comandi ---------------------------------------------
@fuori_bundle
@pytest.mark.parametrize(
    "command",
    [
        "ls && npm install pacchetto-arbitrario",
        "ls; make install",
        "pytest && ./script.sh",
        "cat file | make deploy",
        "echo ok && bash -c 'qualunque cosa'",
    ],
)
def test_hook_valida_ogni_segmento_di_una_catena(command):
    """Il hook dichiara di coprire "gli usi accidentali e le scorciatoie".

    Concatenare con `&&` e' la scorciatoia per eccellenza: prima del fix bastava
    aprire con un comando consentito perche' tutto il resto passasse.
    """
    assert esegui_hook(command) == 2, f"segmento non consentito lasciato passare: {command}"


@fuori_bundle
@pytest.mark.parametrize(
    "command",
    [
        "burnup refresh --strict",
        "pytest -q && ruff check .",
        "git status && git diff",
        "ls | grep REQ",
    ],
)
def test_hook_lascia_passare_le_catene_lecite(command):
    """Nessun falso positivo: se ogni segmento e' consentito, la catena lo e'."""
    assert esegui_hook(command) == 0, f"catena lecita bloccata: {command}"


# -- C-12 · agente sconosciuto --------------------------------------------
@fuori_bundle
def test_hook_non_vincola_quando_l_agente_e_sconosciuto():
    """Se il payload non dichiara l'agente, il hook non puo' sapere se sia un
    Checker — e Solutions Architect e Software Engineer hanno Bash per lavorare.

    Il README del hook detta da se' il criterio: "un hook che blocca il lavoro
    normale viene disattivato, e a quel punto non protegge piu' nulla".
    """
    assert esegui_hook("npm run build", agent=None) == 0


@fuori_bundle
def test_hook_non_vincola_i_maker():
    assert esegui_hook("npm run build", agent="software-engineer") == 0


@fuori_bundle
@pytest.mark.parametrize(
    "command", ["rm -rf x", "echo ciao > file", "git commit -m x", "make build", "pip install requests"]
)
def test_hook_blocca_i_checker_sui_comandi_che_modificano(command):
    assert esegui_hook(command) == 2


# -- C-13 · coerenza fra CLAUDE.md e i file agente ------------------------
@fuori_bundle
def test_la_tabella_degli_agenti_combacia_con_i_file_agente():
    """Due fonti che descrivono la stessa cosa devono dire la stessa cosa."""
    tabella: dict[str, set[str]] = {}
    for riga in re.finditer(r"^\| `@([a-z-]+)` \| \w+ \| ([^|]+)\|", CLAUDE_MD.read_text(encoding="utf-8"), re.M):
        nome, steps = riga.group(1), riga.group(2)
        tabella[nome] = set(re.findall(r"-?\d+\.\d+(?:-[a-z]+)?", steps))

    dichiarati: dict[str, set[str]] = {}
    for percorso in sorted((BUNDLE / ".claude" / "agents").glob("*.md")):
        testo = percorso.read_text(encoding="utf-8")
        corpo = testo.split("# Responsabilità")[0]
        dichiarati[percorso.stem] = set(re.findall(r"-?\d+\.\d+(?:-[a-z]+)?", corpo))

    for nome, steps in dichiarati.items():
        assert nome in tabella, f"@{nome} non compare nella tabella di CLAUDE.md"
        mancanti = steps - tabella[nome]
        assert not mancanti, (
            f"@{nome}: step dichiarati nel file agente ma assenti dalla tabella "
            f"di CLAUDE.md: {sorted(mancanti)}"
        )


# -- C-18 · i prompt agente devono conoscere l'engine che invocano --------
#
# Il difetto che questi tre test chiudono l'ho introdotto io: ho aggiunto un
# comando e tre tipi di finding all'engine, e i sei prompt sono rimasti a
# descrivere la versione precedente. E' la stessa classe di scostamento che il
# collaudo ha passato tre giri a trovare — il codice avanza, la documentazione
# resta indietro — questa volta commessa correggendo.
#
# Il test di coerenza esistente confrontava solo gli STEP fra `CLAUDE.md` e i
# file agente: il buco stava fuori dal perimetro che avevo definito.

def _testo_agenti() -> dict[str, str]:
    return {
        p.stem: p.read_text(encoding="utf-8")
        for p in sorted((BUNDLE / ".claude" / "agents").glob("*.md"))
    }


@fuori_bundle
def test_nessun_prompt_agente_cita_un_comando_inesistente():
    from burnup.cli import build_parser

    parser = build_parser()
    esposti: set[str] = set()
    for action in parser._actions:
        if getattr(action, "choices", None) and isinstance(action.choices, dict):
            for nome, sub in action.choices.items():
                esposti.add(nome)
                for sub_action in sub._actions:
                    if getattr(sub_action, "choices", None) and isinstance(sub_action.choices, dict):
                        esposti.update(f"{nome} {c}" for c in sub_action.choices)

    inesistenti: dict[str, set[str]] = {}
    for agente, testo in {**_testo_agenti(), "CLAUDE.md": CLAUDE_MD.read_text(encoding="utf-8")}.items():
        citati = {
            m.strip() for m in re.findall(r"burnup ([a-z][a-z-]*(?: [a-z][a-z-]*)?)", testo)
        }
        fuori = {c for c in citati if c not in esposti and c.split()[0] not in esposti}
        if fuori:
            inesistenti[agente] = fuori
    assert not inesistenti, f"comandi citati e non esposti dalla CLI: {inesistenti}"


@fuori_bundle
def test_l_auditor_conosce_ogni_finding_che_puo_bloccare_un_gate():
    """Il Technical Auditor esegue `refresh --strict` e riporta i finding
    bloccanti: deve sapere cosa sono e a chi vanno girati.

    Solo i `high`, perche' sono quelli che fermano il Gate 4 con la
    configurazione di default. I `medium` e i `low` restano nel runbook.
    """
    sorgente = Path(__file__).resolve().parent.parent / "burnup"
    bloccanti: set[str] = set()
    for percorso in sorgente.glob("*.py"):
        testo = percorso.read_text(encoding="utf-8")
        bloccanti.update(re.findall(r'severity="high",\s*\n\s*finding_type="([a-z-]+)"', testo))
        bloccanti.update(re.findall(r'^\s*"([a-z-]+)": "high",', testo, re.M))

    prompt = _testo_agenti()["technical-auditor"]
    ignoti = {f for f in bloccanti if f not in prompt}
    assert not ignoti, (
        "il Technical Auditor riporta i finding bloccanti ma il suo prompt non "
        f"nomina: {sorted(ignoti)}"
    )


@fuori_bundle
def test_ogni_exit_code_e_noto_a_chi_lo_deve_interpretare():
    """E' l'Auditor a leggere l'exit code di `refresh --strict` e a tradurlo in
    un verdetto: una tabella incompleta gli lascia un codice senza significato."""
    from burnup.errors import ExitCode

    prompt = _testo_agenti()["technical-auditor"]
    reali = {
        v for k, v in vars(ExitCode).items()
        if not k.startswith("_") and isinstance(v, int)
    }
    mancanti = {c for c in reali if f"`{c}`" not in prompt}
    assert not mancanti, f"exit code non spiegati nel prompt dell'Auditor: {sorted(mancanti)}"


# -- C-14 · tabella dei finding completa ----------------------------------
@fuori_bundle
def test_ogni_tipo_di_finding_e_documentato_nel_runbook():
    """`OPERATING-PROCEDURE.md` dice a chi legge come si chiude ogni rilievo.

    Un tipo che l'engine sa emettere e che il runbook non elenca lascia
    l'operatore senza istruzioni proprio quando il gate si blocca.
    """
    sorgente = Path(__file__).resolve().parent.parent / "burnup"
    emessi: set[str] = set()
    for percorso in sorgente.glob("*.py"):
        testo = percorso.read_text(encoding="utf-8")
        emessi.update(re.findall(r'finding_type="([a-z-]+)"', testo))
        emessi.update(re.findall(r'^\s*"([a-z-]+)": "(?:low|medium|high)",', testo, re.M))

    runbook = (DOCS / "OPERATING-PROCEDURE.md").read_text(encoding="utf-8")
    documentati = set(re.findall(r"\| `([a-z-]+)` \| (?:low|medium|high) \|", runbook))

    mancanti = emessi - documentati
    assert not mancanti, f"tipi di finding non documentati nel runbook: {sorted(mancanti)}"


@fuori_bundle
def test_il_runbook_non_documenta_finding_inesistenti():
    sorgente = Path(__file__).resolve().parent.parent / "burnup"
    emessi: set[str] = set()
    for percorso in sorgente.glob("*.py"):
        testo = percorso.read_text(encoding="utf-8")
        emessi.update(re.findall(r'finding_type="([a-z-]+)"', testo))
        emessi.update(re.findall(r'^\s*"([a-z-]+)": "(?:low|medium|high)",', testo, re.M))

    runbook = (DOCS / "OPERATING-PROCEDURE.md").read_text(encoding="utf-8")
    documentati = set(re.findall(r"\| `([a-z-]+)` \| (?:low|medium|high) \|", runbook))
    inventati = documentati - emessi
    assert not inventati, f"il runbook documenta rilievi che l'engine non emette: {sorted(inventati)}"


# -- C-15 · tabella degli exit code ---------------------------------------
@fuori_bundle
def test_ogni_exit_code_e_documentato_nel_runbook():
    from burnup.errors import ExitCode

    runbook = (DOCS / "OPERATING-PROCEDURE.md").read_text(encoding="utf-8")
    documentati = {int(m) for m in re.findall(r"^\|\s*(\d)\s*\|", runbook, re.M)}
    reali = {
        v for k, v in vars(ExitCode).items()
        if not k.startswith("_") and isinstance(v, int)
    }
    assert reali <= documentati, (
        f"exit code non documentati nel runbook: {sorted(reali - documentati)}"
    )


# -- C-16 · la CI non deve dichiarare numeri sbagliati --------------------
@fuori_bundle
def test_il_nome_del_job_della_ci_non_dichiara_conteggi():
    """Un conteggio scritto a mano in un nome di job invecchia al primo test
    aggiunto, ed e' la stessa classe di disallineamento che l'audit ha punito
    con P1-22. Meglio non dichiararlo affatto che dichiararlo sbagliato."""
    testo = CI.read_text(encoding="utf-8")
    for riga in testo.splitlines():
        if riga.strip().startswith("- name:") and "probe" in riga.lower():
            assert not re.search(r"\d+\s*(probe|test)", riga, re.I), (
                f"la CI dichiara un conteggio che invecchia: {riga.strip()}"
            )
