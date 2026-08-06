"""Canonical store: unica fonte di verita', scritture atomiche, lock.

Chiude P0-05, P0-12, P1-19 e P1-20 dell'audit, e N-02.

Il principio che governa l'intero modulo:

    Il canonical store e' la verita'. Il Markdown e' una proiezione.
    Nessuna decisione umana viene mai registrata modificando un report generato.

La v3 rileggeva i propri stessi report Markdown per ricostruire lo stato. Con
un parser che non riconosceva gli escape prodotti dal suo writer, ogni refresh
poteva corrompere i dati. Qui l'engine scrive `reports/` e non li rilegge MAI.

Transazionalita': la v3 scriveva i tre artefatti in sequenza senza protezione,
quindi un errore a meta' lasciava tre file che descrivevano tre momenti
diversi. Qui tutte le scritture di un refresh sono preparate in memoria,
validate, e riversate su disco in un blocco con rename atomico; e un lock
impedisce a due refresh concorrenti di sovrascriversi.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .errors import InvariantError, LockError, StoreError
from .gates import GateDecision
from .models import Decision, Finding, Relation, Requirement, TestDefinition, TestRun

SCHEMA_VERSION = "2.0"

STATE_DIRNAME = "state"
REPORTS_DIRNAME = "reports"

_REQUIREMENTS = "requirements.json"
_RELATIONS = "relations.jsonl"
_TEST_DEFINITIONS = "test-definitions.json"
_TEST_RUNS = "test-runs.jsonl"
_FINDINGS = "findings.jsonl"
_DECISIONS = "decisions.jsonl"
_SNAPSHOTS = "snapshots.jsonl"
_GATES = "gate-decisions.jsonl"
_MANIFEST = "scan-manifest.json"
_SCHEMA = "schema-version.json"


# --------------------------------------------------------------------------
# Primitive di scrittura atomica
# --------------------------------------------------------------------------

def atomic_write_text(path: Path, content: str) -> None:
    """Scrive un file in modo che non possa mai essere osservato a meta'.

    Sequenza: file temporaneo nella stessa directory (perche' `os.replace` e'
    atomico solo dentro lo stesso filesystem) -> flush -> fsync -> replace.
    Senza fsync, un crash del sistema puo' lasciare un file di lunghezza
    corretta e contenuto nullo su diversi filesystem.

    `newline="\\n"` e' esplicito: senza, su Windows Python tradurrebbe i
    newline in scrittura e lo stesso stato produrrebbe byte diversi su sistemi
    diversi, rompendo la riproducibilita' richiesta dalla MSA.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp), str(path))
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreError(
            f"Il file di stato {path.name} non e' leggibile: {exc}",
            hint="Ripristina la versione precedente da Git, oppure rigenera con 'burnup init --reset'.",
        ) from exc


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise StoreError(
                    f"{path.name}, riga {lineno}: JSON non valido ({exc}).",
                    hint="Il file e' append-only: correggi o rimuovi la riga malformata.",
                ) from exc
    return out


def _dump_json(obj) -> str:
    # sort_keys + indent: i diff Git restano leggibili e lo stesso stato
    # produce sempre lo stesso file, che e' la base della repeatability.
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _dump_jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)


# --------------------------------------------------------------------------
# Lock di processo
# --------------------------------------------------------------------------

class StoreLock:
    """Lock esclusivo sul canonical store.

    Chiude la parte di P0-12 sui refresh concorrenti: due processi che
    scrivevano insieme potevano perdere storia. Implementato con
    `O_CREAT|O_EXCL`, che e' atomico su POSIX e su Windows.
    """

    def __init__(self, state_dir: Path, timeout: float = 10.0) -> None:
        self.path = state_dir / ".lock"
        self.timeout = timeout
        self._fd: int | None = None

    def __enter__(self) -> "StoreLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._fd, f"{os.getpid()}\n".encode())
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    holder = ""
                    try:
                        holder = self.path.read_text(encoding="utf-8").strip()
                    except OSError:
                        pass
                    raise LockError(
                        f"Un altro processo sta gia' scrivendo sul canonical store (pid {holder or 'sconosciuto'}).",
                        hint=f"Attendi il completamento, oppure rimuovi {self.path} se il processo e' morto.",
                    ) from None
                time.sleep(0.05)

    def __exit__(self, *exc) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self.path.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------

@dataclass
class StoreData:
    requirements: list[Requirement] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    test_definitions: list[TestDefinition] = field(default_factory=list)
    test_runs: list[TestRun] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    gate_decisions: list[GateDecision] = field(default_factory=list)
    snapshots: list[dict] = field(default_factory=list)
    manifest: dict = field(default_factory=dict)


class Store:
    """Accesso al canonical store. Le scritture passano sempre da `commit`."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.state_dir = output_dir / STATE_DIRNAME
        self.reports_dir = output_dir / REPORTS_DIRNAME

    # -- lettura ----------------------------------------------------------

    def check_schema(self) -> None:
        path = self.state_dir / _SCHEMA
        if not path.exists():
            return
        data = _read_json(path, {})
        found = str(data.get("schema_version", ""))
        if found and found != SCHEMA_VERSION:
            raise StoreError(
                f"Il canonical store e' allo schema {found}, l'engine richiede {SCHEMA_VERSION}.",
                hint="Esegui 'burnup migrate' per aggiornare lo store.",
            )

    def load(self) -> StoreData:
        self.check_schema()
        s = self.state_dir
        return StoreData(
            requirements=[Requirement.from_json(d) for d in _read_json(s / _REQUIREMENTS, [])],
            relations=[Relation.from_json(d) for d in _read_jsonl(s / _RELATIONS)],
            test_definitions=[TestDefinition.from_json(d) for d in _read_json(s / _TEST_DEFINITIONS, [])],
            test_runs=[TestRun.from_json(d) for d in _read_jsonl(s / _TEST_RUNS)],
            findings=[Finding.from_json(d) for d in _read_jsonl(s / _FINDINGS)],
            decisions=[Decision.from_json(d) for d in _read_jsonl(s / _DECISIONS)],
            gate_decisions=[GateDecision.from_json(d) for d in _read_jsonl(s / _GATES)],
            snapshots=_read_jsonl(s / _SNAPSHOTS),
            manifest=_read_json(s / _MANIFEST, {}),
        )

    # -- scrittura --------------------------------------------------------

    def commit(self, data: StoreData, reports: dict[str, str] | None = None) -> None:
        """Riversa stato e report in un'unica transazione.

        L'ordine e' deliberato: prima si serializza TUTTO in memoria, cosi' un
        errore di serializzazione fallisce prima di aver toccato il disco.
        E' la correzione di N-02: la v3 creava i file dai template all'inizio
        del refresh, quindi un crash successivo lasciava nel repository
        artefatti vuoti che il refresh seguente trattava come stato valido.
        """
        payload: list[tuple[Path, str]] = []
        s = self.state_dir

        try:
            payload.append((s / _SCHEMA, _dump_json({"schema_version": SCHEMA_VERSION})))
            payload.append((s / _REQUIREMENTS, _dump_json([r.to_json() for r in data.requirements])))
            payload.append((s / _RELATIONS, _dump_jsonl([r.to_json() for r in data.relations])))
            payload.append((s / _TEST_DEFINITIONS, _dump_json([t.to_json() for t in data.test_definitions])))
            payload.append((s / _TEST_RUNS, _dump_jsonl([r.to_json() for r in data.test_runs])))
            payload.append((s / _FINDINGS, _dump_jsonl([f.to_json() for f in data.findings])))
            payload.append((s / _DECISIONS, _dump_jsonl([d.to_json() for d in data.decisions])))
            payload.append((s / _GATES, _dump_jsonl([g.to_json() for g in data.gate_decisions])))
            payload.append((s / _SNAPSHOTS, _dump_jsonl(data.snapshots)))
            payload.append((s / _MANIFEST, _dump_json(data.manifest)))
            for name, content in (reports or {}).items():
                payload.append((self.reports_dir / name, content))
        except (TypeError, ValueError) as exc:
            raise InvariantError(
                f"Stato non serializzabile: {exc}",
                hint="E' un bug dell'engine: nessun file e' stato modificato.",
            ) from exc

        written: list[Path] = []
        try:
            for path, content in payload:
                atomic_write_text(path, content)
                written.append(path)
        except OSError as exc:
            raise StoreError(
                f"Scrittura fallita su {exc.filename or 'file sconosciuto'}: {exc}",
                hint=(
                    f"Scritti {len(written)}/{len(payload)} file. Lo store puo' essere incoerente: "
                    "ripristina da Git ed esegui di nuovo il refresh."
                ),
            ) from exc

    def gitignore_hint(self) -> str:
        return "# Il canonical store VA versionato: e' la storia del progetto.\n# Solo il lock e' transitorio.\nstate/.lock\n"
