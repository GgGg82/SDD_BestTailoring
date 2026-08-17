"""State machine dei phase gate, con invalidazione automatica.

Chiude P1-26, P1-27, P1-28 dell'audit e l'incremento C2 del piano (Gate
Decision Record in forma PMI).

Nella v3 lo stato dei gate viveva in `progress.md`, una checklist Markdown
editata a mano dall'Orchestratore. Tre conseguenze, tutte verificate:

1. **nessuna transizione controllata** — nulla impediva di spuntare il Gate 3
   senza che il Gate 2 fosse mai stato approvato;
2. **nessuna invalidazione** — modificare `spec.md` dopo l'approvazione del
   Gate 1 non invalidava nulla, e i gate a valle restavano formalmente validi
   pur riferendosi a una baseline che non esisteva piu';
3. **nessun evidence package** — il template registrava soltanto "approvato da"
   e una data: non la versione degli artefatti approvati, non i finding
   aperti, non i waiver, non le condizioni di approvazione.

Qui un gate approvato e' un record immutabile che *cita i fingerprint degli
artefatti al momento dell'approvazione*. L'invalidazione non e' una procedura
che qualcuno deve ricordarsi di eseguire: e' il confronto tra quei fingerprint
e quelli correnti.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

from .errors import ConfigError
from .models import Finding

# Ordine dei gate e artefatto che ciascuno mette sotto baseline.
GATE_SEQUENCE = (1, 2, 3, 4)

# Classi di change (docs/SCALE-ADAPTIVE-FLOW.md), in ordine crescente di rigore.
#
# C-10: il documento e' normativo e prescrive per Fast Track "Gate: 1 e 4", ma
# l'engine non aveva alcuna nozione di classe: la sequenza era sempre 1-2-3-4 e
# il Gate 4 risultava irraggiungibile senza i Gate 2 e 3. La classe viveva solo
# in `progress.md`, dichiarata dall'Orchestratore, e nessun meccanismo la
# leggeva.
#
# Cio' che scala e' il numero di gate e di artefatti, MAI il rigore della
# misurazione: tracciabilita', test obbligatori e `refresh --strict` prima del
# Gate 4 valgono identici in tutte le classi, ed e' garantito dal fatto che il
# finding `requirement-not-verified` e' `high` e non configurabile.
CHANGE_CLASSES = ("fast-track", "standard", "high-risk")
DEFAULT_CHANGE_CLASS = "standard"

GATES_BY_CLASS: dict[str, tuple[int, ...]] = {
    "fast-track": (1, 4),
    "standard": (1, 2, 3, 4),
    "high-risk": (1, 2, 3, 4),
}


def gates_for(change_class: str) -> tuple[int, ...]:
    return GATES_BY_CLASS.get(change_class, GATE_SEQUENCE)


def is_promotion(attuale: str, nuova: str) -> bool:
    """La promozione e' ammessa in corsa, la retrocessione no.

    Retrocedere significherebbe rimuovere un controllo dopo aver visto cosa
    avrebbe trovato.
    """
    return CHANGE_CLASSES.index(nuova) >= CHANGE_CLASSES.index(attuale)

GATE_NAMES = {
    1: "Requirements Baseline",
    2: "Solution Baseline",
    3: "Implementation Readiness",
    4: "Release Readiness",
}

# Artefatto la cui versione viene congelata dall'approvazione del gate.
GATE_BASELINE_ARTIFACT = {1: "spec", 2: "plan", 3: "tasks", 4: "code"}

# Quali gate decadono quando cambia un artefatto.
#
# La direzione e' quella naturale del flusso SDD: cambiare il COSA invalida
# ogni decisione presa a valle, perche' tutte poggiavano su una descrizione del
# problema che non e' piu' quella.
INVALIDATION_MAP = {
    "spec": (1, 2, 3, 4),
    "plan": (2, 3, 4),
    "tasks": (3, 4),
    "code": (4,),
}

OUTCOMES = ("approved", "conditionally-approved", "rejected")


@dataclass
class GateDecision:
    """Gate Decision Record. Immutabile: una revisione produce un nuovo record.

    Campi allineati alla pratica PMI di stage-gate: chi ha approvato, su quale
    versione degli artefatti, con quali finding aperti, quali waiver e a quali
    condizioni. Senza questi campi un'approvazione non e' verificabile a
    posteriori — si sa che qualcuno ha detto di si', non su cosa.
    """

    decision_id: str
    feature_id: str
    gate: int
    outcome: str
    approver: str
    approved_at: str
    rationale: str
    source_revision: str = ""
    artifact_fingerprints: dict = field(default_factory=dict)
    open_findings: list = field(default_factory=list)
    waivers: list = field(default_factory=list)
    conditions: list = field(default_factory=list)
    burnup_counts: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_json(d: dict) -> "GateDecision":
        known = GateDecision.__dataclass_fields__.keys()
        return GateDecision(**{k: v for k, v in d.items() if k in known})


@dataclass
class GateState:
    """Stato corrente di un gate, calcolato — mai memorizzato.

    Memorizzare lo stato "valido/non valido" reintrodurrebbe il difetto della
    v3: un valore che qualcuno deve ricordarsi di aggiornare. Qui e' sempre
    derivato dal confronto tra i fingerprint del record e quelli attuali.
    """

    gate: int
    status: str          # "not-approved" | "valid" | "invalidated" | "rejected"
    decision: GateDecision | None = None
    invalidated_by: list[str] = field(default_factory=list)
    detail: str = ""


def evaluate_gates(
    feature_id: str,
    decisions: list[GateDecision],
    current_fingerprints: dict[str, str],
) -> dict[int, GateState]:
    """Calcola lo stato di tutti i gate di una feature.

    `current_fingerprints` contiene le chiavi 'spec', 'plan', 'tasks' e
    facoltativamente 'code'.
    """
    latest: dict[int, GateDecision] = {}
    for d in decisions:
        if d.feature_id != feature_id:
            continue
        prior = latest.get(d.gate)
        if prior is None or d.approved_at >= prior.approved_at:
            latest[d.gate] = d

    states: dict[int, GateState] = {}
    for gate in GATE_SEQUENCE:
        decision = latest.get(gate)
        if decision is None:
            states[gate] = GateState(gate=gate, status="not-approved")
            continue
        if decision.outcome == "rejected":
            states[gate] = GateState(gate=gate, status="rejected", decision=decision,
                                     detail="ultima decisione: respinto")
            continue

        changed: list[str] = []
        for artifact, gates in INVALIDATION_MAP.items():
            if gate not in gates:
                continue
            recorded = decision.artifact_fingerprints.get(artifact)
            current = current_fingerprints.get(artifact)
            if recorded is None and current is None:
                continue
            if recorded != current:
                changed.append(artifact)

        if changed:
            states[gate] = GateState(
                gate=gate, status="invalidated", decision=decision, invalidated_by=changed,
                detail=(
                    f"{', '.join(sorted(changed))} e' cambiato dopo l'approvazione: "
                    "la baseline approvata non e' piu' quella corrente"
                ),
            )
        else:
            states[gate] = GateState(gate=gate, status="valid", decision=decision)

    return states


def check_entry_criteria(
    gate: int,
    states: dict[int, GateState],
    current_fingerprints: dict[str, str],
    blocking_findings: list[Finding],
    change_class: str = DEFAULT_CHANGE_CLASS,
) -> list[str]:
    """Ritorna l'elenco dei criteri di ingresso non soddisfatti.

    Lista vuota significa che il gate e' approvabile. Il controllo sul gate
    precedente e' cio' che rende la sequenza una vera state machine: nella v3
    si poteva spuntare il Gate 3 senza che il Gate 2 fosse mai esistito.
    """
    unmet: list[str] = []

    if gate not in GATE_SEQUENCE:
        raise ConfigError(f"Gate '{gate}' sconosciuto. Valori ammessi: {', '.join(map(str, GATE_SEQUENCE))}.")

    # Il predecessore e' il gate precedente NELLA SEQUENZA DELLA CLASSE, non
    # `gate - 1`: in Fast Track il Gate 4 segue direttamente il Gate 1.
    sequenza = gates_for(change_class)
    if gate not in sequenza:
        unmet.append(
            f"il Gate {gate} ({GATE_NAMES[gate]}) non fa parte della classe '{change_class}': "
            f"gate previsti {', '.join(map(str, sequenza))}"
        )
        return unmet

    posizione = sequenza.index(gate)
    if posizione > 0:
        previous = sequenza[posizione - 1]
        prev_state = states.get(previous)
        if prev_state is None or prev_state.status != "valid":
            status = prev_state.status if prev_state else "not-approved"
            unmet.append(
                f"il Gate {previous} ({GATE_NAMES[previous]}) non e' valido: stato '{status}'"
                + (f" — {prev_state.detail}" if prev_state and prev_state.detail else "")
            )

    required_artifact = {1: "spec", 2: "plan", 3: "tasks"}.get(gate)
    if required_artifact and not current_fingerprints.get(required_artifact):
        unmet.append(f"l'artefatto '{required_artifact}' richiesto dal Gate {gate} non esiste")

    # Il Gate 4 e' l'unico che si misura sull'evidenza prodotta, non solo sulla
    # presenza degli artefatti: e' li' che il burn-up diventa un quality gate.
    if gate == 4 and blocking_findings:
        ids = ", ".join(f.finding_id for f in blocking_findings[:5])
        more = f" (+{len(blocking_findings) - 5})" if len(blocking_findings) > 5 else ""
        unmet.append(
            f"{len(blocking_findings)} finding bloccanti aperti: {ids}{more}. "
            "Risolvili, oppure registra un waiver motivato con 'burnup finding waive'."
        )

    return unmet


def format_gate_report(
    feature_id: str, states: dict[int, GateState], change_class: str = ""
) -> list[str]:
    """Righe leggibili per la CLI.

    La classe di change compare qui perche' decide **quali gate esistono**: su
    una Fast Track i Gate 2 e 3 non vanno attraversati. Senza dirlo, l'elenco
    li mostrava come `not-approved` accanto agli altri, cioe' come lavoro
    ancora da fare — e la stessa informazione risultava corretta in `--json`
    (campo `change_class`) e assente nella vista che legge una persona.
    Trovato in simulazione su progetto reale, 2026-08-09.
    """
    previsti = set(gates_for(change_class)) if change_class else set(GATE_SEQUENCE)
    intestazione = f"Gate della feature '{feature_id}':"
    if change_class:
        elenco = ", ".join(str(g) for g in sorted(previsti))
        intestazione += f"  [classe: {change_class} — gate previsti: {elenco}]"
    lines = [intestazione]
    symbol = {"valid": "✓", "invalidated": "⚠", "not-approved": "·", "rejected": "✗"}
    for gate in GATE_SEQUENCE:
        state = states[gate]
        if gate not in previsti:
            lines.append(
                f"  – Gate {gate} — {GATE_NAMES[gate]}: non previsto in classe '{change_class}'"
            )
            continue
        head = f"  {symbol.get(state.status, '?')} Gate {gate} — {GATE_NAMES[gate]}: {state.status}"
        if state.decision and state.status != "not-approved":
            head += f" (approvato da {state.decision.approver} il {state.decision.approved_at})"
        lines.append(head)
        if state.detail:
            lines.append(f"      {state.detail}")
        if state.decision and state.decision.conditions:
            for c in state.decision.conditions:
                lines.append(f"      condizione: {c}")
    return lines
