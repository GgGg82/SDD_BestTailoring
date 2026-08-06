"""Entita' del canonical store.

Chiude P0-06, P1-16, P1-17 e P1-21 dell'audit.

Differenze sostanziali rispetto alla v3:

* ogni entita' ha un'identita' stabile e un fingerprint del contenuto;
* le relazioni sono tipizzate e datate, non stringhe dentro una cella;
* i Finding hanno un ID stabile tra refresh e un ciclo di vita, quindi si puo'
  misurarne l'aging e chiuderli formalmente;
* ogni Finding porta un `feature_id` esplicito invece di farlo dedurre da uno
  split del subject (P1-21);
* le decisioni umane sono record di prima classe, non note in una tabella.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# --------------------------------------------------------------------------
# Vocabolari chiusi
# --------------------------------------------------------------------------

LIFECYCLE_STATES = ("defined", "implemented", "tested")
SCOPE_STATES = ("active", "removed")
RESULT_VALUES = ("not-run", "pass", "fail", "blocked", "error")
SEVERITIES = ("low", "medium", "high")
FINDING_STATUSES = ("open", "accepted", "waived", "resolved", "verified")
RELATION_TYPES = ("implemented-by", "evidenced-by", "verified-by", "derived-from")
RELATION_STATUSES = ("confirmed", "proposed", "superseded")
DECISION_KINDS = (
    "link-confirm",
    "requirement-remove",
    "test-define",
    "test-confirm-manual",
    "finding-waive",
    "finding-close",
)


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v not in (None, [], {})}


@dataclass
class Requirement:
    """Un requisito nella sua forma canonica.

    `fingerprint` e' calcolato sul contenuto normativo. Tutta l'evidenza e'
    legata a questo valore: se cambia, l'evidenza precedente decade
    automaticamente e lo stato retrocede. E' la correzione strutturale del
    difetto piu' grave della v3.
    """

    key: str                       # "001-demo/FR-001"
    feature_id: str
    requirement_id: str
    text: str
    fingerprint: str
    source: str                    # percorso relativo di spec.md
    source_line: int = 0
    section_path: tuple[str, ...] = ()
    user_story: str = ""           # popolata SOLO da appartenenza strutturale o tag inline
    user_story_origin: str = ""    # "structural" | "inline" | "" — rende auditabile il come
    acceptance_criteria: str = ""
    nfr_refs: list[str] = field(default_factory=list)
    scope_state: str = "active"
    lifecycle_state: str = "defined"
    notes: str = ""                # esclusivamente umane: nessun metadato macchina
    first_seen: str = ""
    # "ultima modifica", non "ultima osservazione": si aggiorna solo quando il
    # contenuto cambia davvero. Un campo che si aggiorna ad ogni scansione
    # produrrebbe un diff Git ad ogni refresh anche a input invariati, e
    # violerebbe la proprieta' MSA "nessun cambio di stato senza cambio di
    # input". Quando e' avvenuta l'ultima scansione lo dice `scan-manifest.json`.
    last_changed: str = ""
    removed_reason: str = ""
    removed_by: str = ""
    removed_at: str = ""

    def to_json(self) -> dict:
        d = asdict(self)
        d["section_path"] = list(self.section_path)
        return _clean(d)

    @staticmethod
    def from_json(d: dict) -> "Requirement":
        d = dict(d)
        d["section_path"] = tuple(d.get("section_path", []))
        d["nfr_refs"] = list(d.get("nfr_refs", []))
        known = Requirement.__dataclass_fields__.keys()
        return Requirement(**{k: v for k, v in d.items() if k in known})


@dataclass
class Relation:
    """Relazione tipizzata tra un requisito e un'evidenza.

    `requirement_fingerprint` e' il campo che rende la relazione invalidabile:
    quando il requisito cambia contenuto, le relazioni che puntano al vecchio
    fingerprint restano nello store come storia, ma smettono di essere
    evidenza corrente.
    """

    from_key: str
    to_ref: str                    # "T014", "src/auth.py:42", "TEST-001"
    rel_type: str
    status: str = "confirmed"
    source: str = ""               # "tasks.md", "src/auth.py", "decision:DEC-0003"
    requirement_fingerprint: str = ""
    artifact_fingerprint: str = ""
    valid_from: str = ""
    valid_to: str | None = None
    decided_by: str = ""           # valorizzato solo per relazioni confermate a mano
    reason: str = ""

    @property
    def is_current(self) -> bool:
        return self.valid_to is None and self.status == "confirmed"

    def to_json(self) -> dict:
        return _clean(asdict(self))

    @staticmethod
    def from_json(d: dict) -> "Relation":
        known = Relation.__dataclass_fields__.keys()
        return Relation(**{k: v for k, v in d.items() if k in known})


@dataclass
class TestDefinition:
    """Definizione di un test. Vive in `state/test-definitions.json`.

    Nella v3 il Test Register era una tabella Markdown senza owner né percorso
    di scrittura: l'unico modo di definire un test era editare a mano la
    tabella generata, cioe' proprio l'operazione che la documentazione
    vietava (P0-03). Qui la sorgente e' un file di stato, e ci si scrive
    tramite `burnup test define`.
    """

    # Il prefisso "Test" fa credere a pytest che sia una classe di test: questo
    # attributo glielo impedisce. E' un modello di dominio, non un test.
    __test__ = False

    test_id: str
    requirement_keys: list[str] = field(default_factory=list)
    kind: str = "unit"
    mandatory: bool = False
    definition: str = ""
    location_or_command: str = ""
    owner: str = ""
    environment: str = ""
    notes: str = ""

    def to_json(self) -> dict:
        return _clean(asdict(self))

    @staticmethod
    def from_json(d: dict) -> "TestDefinition":
        d = dict(d)
        mandatory = d.get("mandatory", False)
        if isinstance(mandatory, str):
            d["mandatory"] = mandatory.strip().lower() in ("yes", "true", "y", "1", "si", "sì")
        d["requirement_keys"] = list(d.get("requirement_keys", []))
        known = TestDefinition.__dataclass_fields__.keys()
        return TestDefinition(**{k: v for k, v in d.items() if k in known})


@dataclass
class TestRun:
    """Esecuzione di un test. Append-only reale in `state/test-runs.jsonl`.

    `run_identity` e' la chiave di deduplica che chiude P0-07: la v3
    reimportava lo stesso report a ogni refresh, producendo tre righe identiche
    in tre refresh. Qui una run gia' presente viene riconosciuta e ignorata.
    """

    __test__ = False  # come per TestDefinition

    run_id: str                    # ULID: ordinabile e senza collisioni
    run_identity: str              # hash(report + adapter + test + timestamp)
    test_id: str
    result: str
    executed_at: str               # timestamp dell'ESECUZIONE, non del refresh
    source_revision: str = ""      # revisione su cui il test e' girato davvero
    revision_origin: str = ""      # "report" | "sidecar" | "manual" | "unknown"
    duration: str = ""
    evidence_path: str = ""
    evidence_hash: str = ""
    adapter: str = ""
    adapter_version: str = ""
    imported_at: str = ""
    worktree_dirty: bool = False
    notes: str = ""

    def to_json(self) -> dict:
        return _clean(asdict(self))

    @staticmethod
    def from_json(d: dict) -> "TestRun":
        known = TestRun.__dataclass_fields__.keys()
        return TestRun(**{k: v for k, v in d.items() if k in known})


@dataclass
class Finding:
    """Rilievo con identita' stabile e ciclo di vita.

    Nella v3 i Finding ID erano rigenerati a ogni refresh (`FND-001`,
    `FND-002`, ...), quindi lo stesso problema cambiava identita' ad ogni giro:
    impossibile misurarne l'aging o chiuderlo formalmente (P1-16).
    Qui l'ID e' derivato dal contenuto, quindi lo stesso problema conserva lo
    stesso ID finche' esiste.
    """

    finding_id: str
    severity: str
    finding_type: str
    subject: str
    subject_type: str              # "requirement" | "test" | "task" | "report" | "config"
    feature_id: str                # esplicito, mai dedotto dal subject (P1-21)
    description: str
    recommended_action: str
    status: str = "open"
    first_seen: str = ""
    last_changed: str = ""   # vedi la nota su Requirement.last_changed
    waiver_reason: str = ""
    waived_by: str = ""
    waived_at: str = ""
    waiver_expires: str = ""

    @property
    def is_blocking(self) -> bool:
        """Blocca un gate se e' `high` e non e' stato formalmente neutralizzato."""
        return self.severity == "high" and self.status in ("open", "accepted")

    def to_json(self) -> dict:
        return _clean(asdict(self))

    @staticmethod
    def from_json(d: dict) -> "Finding":
        known = Finding.__dataclass_fields__.keys()
        return Finding(**{k: v for k, v in d.items() if k in known})


@dataclass
class Decision:
    """Atto umano registrato in modo permanente.

    Chiude P0-03: la v3 dichiarava che l'agente avrebbe confermato link,
    deciso rimozioni e validato test manuali, ma non esisteva alcun percorso
    tecnico per farlo. Ogni decisione qui porta con se' chi, quando, perche' e
    su quale versione dell'artefatto — quindi sopravvive ai refresh e resta
    verificabile.
    """

    decision_id: str
    kind: str
    subject: str
    actor: str
    reason: str
    decided_at: str
    source_revision: str = ""
    requirement_fingerprint: str = ""
    expires_at: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict:
        return _clean(asdict(self))

    @staticmethod
    def from_json(d: dict) -> "Decision":
        known = Decision.__dataclass_fields__.keys()
        return Decision(**{k: v for k, v in d.items() if k in known})


@dataclass
class Counts:
    scope: int = 0
    defined: int = 0
    implemented: int = 0
    tested: int = 0
    removed_total: int = 0
    scope_fingerprint: str = ""

    def to_json(self) -> dict:
        return asdict(self)
