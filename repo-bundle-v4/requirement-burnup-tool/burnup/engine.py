"""Orchestrazione di uno scan completo.

Chiude P0-06, P0-10, P1-10, P1-16, P1-18 e P1-27 dell'audit.

Il flusso e' deliberatamente lineare e senza scritture intermedie: si legge
tutto, si calcola tutto in memoria, si valida, e solo alla fine si affida al
canonical store una singola transazione. La v3 creava i file di output
all'inizio (N-02) e li scriveva a blocchi durante il percorso, quindi
qualunque errore lasciava artefatti a meta'.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import BurnupConfig
from .fingerprint import scope_fingerprint
from .ids import finding_id, now_iso, snapshot_id
from .ingest import ingest_reports, latest_run_by_test
from .models import Counts, Finding, Relation, Requirement, TestDefinition, TestRun
from .paths import relative_label
from .specscan import (
    Feature,
    detect_specs_root,
    discover_features,
    extract_requirements,
    link_code_evidence,
    link_tasks,
)
from .status import StatusContext, compute_status
from .store import Store, StoreData

# Anomalie strutturali e severita' associata. Tenerle in un unico posto evita
# che la stessa condizione risulti 'high' in un punto e 'low' in un altro.
ANOMALY_SEVERITY = {
    "reference-outside-requirements": "low",
    "duplicate-requirement-id": "high",
    "unreadable-source": "medium",
    "marker-outside-comment": "low",
    "marker-inside-string": "low",
    "unreadable-report": "medium",
    "unmatched-test-report": "low",
    "unnamed-test-result": "low",
    "missing-execution-timestamp": "medium",
}


@dataclass
class ScanResult:
    counts: Counts
    findings: list[Finding]
    blocking: list[Finding]
    requirements: list[Requirement]
    snapshot_appended: bool
    snapshot_reason: str
    n_features: int
    specs_root: Path
    new_runs: int
    skipped_duplicates: int
    reports: dict[str, str] = field(default_factory=dict)


def git_revision(project_root: Path) -> tuple[str, bool, str]:
    """Ritorna (revisione, working tree sporco, motivo se sconosciuta).

    Chiude N-05: la v3 restituiva stringa vuota per qualunque motivo — git
    assente, directory non un repository, comando fallito — rendendo
    indistinguibili situazioni molto diverse, e non guardava affatto lo stato
    del working tree (P0-08).
    """
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root, capture_output=True, text=True, timeout=10,
        )
    except FileNotFoundError:
        return "", False, "git non e' installato o non e' nel PATH"
    except (OSError, subprocess.SubprocessError) as exc:
        return "", False, f"esecuzione di git fallita: {exc}"

    if rev.returncode != 0:
        detail = (rev.stderr or "").strip().splitlines()
        return "", False, detail[0] if detail else "la directory non e' un repository Git con almeno un commit"

    revision = rev.stdout.strip()

    dirty = False
    try:
        st = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=project_root, capture_output=True, text=True, timeout=10,
        )
        dirty = st.returncode == 0 and bool(st.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass

    return revision, dirty, ""


class FindingFactory:
    """Crea Finding con ID stabile e ciclo di vita preservato tra refresh.

    Chiude P1-16: nella v3 gli ID erano riassegnati da zero ad ogni giro
    (`FND-001`, `FND-002`, ...), quindi lo stesso problema cambiava identita'
    continuamente e non era possibile misurarne l'eta' né applicargli un
    waiver che sopravvivesse.
    """

    def __init__(self, previous: list[Finding], timestamp: str) -> None:
        self.previous = {f.finding_id: f for f in previous}
        self.timestamp = timestamp
        self.produced: dict[str, Finding] = {}

    def __call__(
        self,
        *,
        severity: str,
        finding_type: str,
        subject: str,
        subject_type: str,
        feature_id: str,
        description: str,
        recommended_action: str,
    ) -> Finding:
        fid = finding_id(finding_type, subject, feature_id)
        prior = self.previous.get(fid)
        finding = Finding(
            finding_id=fid,
            severity=severity,
            finding_type=finding_type,
            subject=subject,
            subject_type=subject_type,
            feature_id=feature_id,
            description=description,
            recommended_action=recommended_action,
            status=prior.status if prior else "open",
            first_seen=prior.first_seen if prior and prior.first_seen else self.timestamp,
            last_changed=self.timestamp,  # ricalcolato subito sotto se nulla e' cambiato
            waiver_reason=prior.waiver_reason if prior else "",
            waived_by=prior.waived_by if prior else "",
            waived_at=prior.waived_at if prior else "",
            waiver_expires=prior.waiver_expires if prior else "",
        )
        # Un waiver scaduto torna aperto da solo: un'eccezione a tempo che non
        # si riapre e' un'eccezione permanente travestita.
        if finding.status == "waived" and finding.waiver_expires and finding.waiver_expires < self.timestamp:
            finding.status = "open"
            finding.description += " [waiver scaduto il " + finding.waiver_expires + "]"

        # Se il finding e' identico a quello del giro precedente, si preserva il
        # timestamp: un rilievo che non e' cambiato non e' cambiato.
        if prior is not None:
            same = (
                prior.severity == finding.severity
                and prior.status == finding.status
                and prior.description == finding.description
                and prior.recommended_action == finding.recommended_action
            )
            if same:
                finding.last_changed = prior.last_changed or prior.first_seen or self.timestamp
        self.produced[fid] = finding
        return finding

    def resolved(self) -> list[Finding]:
        """Finding presenti in passato e non piu' riprodotti: chiusi automaticamente."""
        out = []
        for fid, prior in self.previous.items():
            if fid in self.produced:
                continue
            if prior.status in ("resolved", "verified"):
                out.append(prior)
                continue
            closed = Finding.from_json(prior.to_json())
            closed.status = "resolved"
            closed.last_changed = self.timestamp
            out.append(closed)
        return out


def compute_counts(requirements: list[Requirement]) -> Counts:
    active = [r for r in requirements if r.scope_state == "active"]
    removed = [r for r in requirements if r.scope_state == "removed"]
    counts = Counts(
        scope=len(active),
        defined=sum(1 for r in active if r.lifecycle_state in ("defined", "implemented", "tested")),
        implemented=sum(1 for r in active if r.lifecycle_state in ("implemented", "tested")),
        tested=sum(1 for r in active if r.lifecycle_state == "tested"),
        removed_total=len(removed),
        scope_fingerprint=scope_fingerprint([r.key for r in active]),
    )
    if not (counts.tested <= counts.implemented <= counts.defined <= counts.scope):
        from .errors import InvariantError

        # Sostituisce l'`assert` della v3 (N-01): un assert sparisce sotto
        # `python -O` proprio quando l'integrita' conta di piu', e produceva un
        # traceback non intercettato dalla CLI.
        raise InvariantError(
            f"Invariante di burn-up violata: tested={counts.tested} implemented={counts.implemented} "
            f"defined={counts.defined} scope={counts.scope}",
            hint="E' un bug dell'engine nel calcolo degli stati. Nessun file e' stato modificato.",
        )
    return counts


def should_snapshot(previous: dict | None, counts: Counts, forced: bool) -> tuple[bool, str]:
    """Decide se registrare uno snapshot storico.

    Chiude P1-10: la v3 confrontava solo i conteggi, quindi rimuovere un
    requisito e aggiungerne un altro nello stesso refresh risultava
    'no-change' e non lasciava alcuna traccia storica di una modifica di
    scope sostanziale. Qui si confronta anche il fingerprint della
    composizione dello scope.
    """
    if forced:
        return True, "forced"
    if not previous:
        return True, "initial"
    if previous.get("scope_fingerprint") != counts.scope_fingerprint:
        return True, "scope-composition-change"
    for key in ("scope", "defined", "implemented", "tested", "removed_total"):
        if int(previous.get(key, -1)) != getattr(counts, key):
            return True, "status-change"
    return False, "no-change"


def run_scan(config: BurnupConfig, *, forced_snapshot: bool = False) -> tuple[ScanResult, StoreData]:
    project_root = config.project_root
    store = Store(config.output_dir)
    data = store.load()
    timestamp = now_iso()

    specs_root = detect_specs_root(project_root)
    specs_label = relative_label(specs_root, project_root)
    features = discover_features(specs_root)
    revision, dirty, revision_problem = git_revision(project_root)

    factory = FindingFactory(data.findings, timestamp)
    anomalies: list[tuple[str, str, str]] = []  # (tipo, dettaglio, feature)

    # -- 1. requisiti ------------------------------------------------------
    discovered: list[Requirement] = []
    task_scans: dict[str, object] = {}
    for feature in features:
        reqs, anom = extract_requirements(feature, config, specs_label)
        discovered.extend(reqs)
        anomalies.extend((t, d, feature.feature_id) for t, d in anom)
        task_scans[feature.feature_id] = link_tasks(feature, config)

    code_evidence, code_anom = link_code_evidence(project_root, config)
    anomalies.extend((t, d, "") for t, d in code_anom)

    # -- 2. riconciliazione ------------------------------------------------
    # Le note umane e le decisioni di scope si preservano; l'EVIDENZA no:
    # quella si ricostruisce interamente dallo stato corrente del repository.
    previous_by_key = {r.key: r for r in data.requirements}
    merged: dict[str, Requirement] = {}

    for req in discovered:
        prior = previous_by_key.get(req.key)
        if prior is not None:
            req.notes = prior.notes
            req.first_seen = prior.first_seen or timestamp
            req.scope_state = prior.scope_state
            req.removed_reason = prior.removed_reason
            req.removed_by = prior.removed_by
            req.removed_at = prior.removed_at
            if prior.fingerprint != req.fingerprint:
                factory(
                    severity="medium",
                    finding_type="requirement-changed",
                    subject=req.key,
                    subject_type="requirement",
                    feature_id=req.feature_id,
                    description=(
                        "Il contenuto normativo del requisito e' cambiato: tutta l'evidenza precedente "
                        "(task, codice, test) non si applica piu' e va riconfermata."
                    ),
                    recommended_action="Riesegui i test e verifica i collegamenti sulla nuova formulazione.",
                )
            # Il timestamp si muove solo se il requisito e' davvero cambiato.
            if prior.fingerprint == req.fingerprint and prior.scope_state == req.scope_state:
                req.last_changed = prior.last_changed or prior.first_seen or timestamp
            else:
                req.last_changed = timestamp
        else:
            req.first_seen = timestamp
            req.last_changed = timestamp
        merged[req.key] = req

    for key, prior in previous_by_key.items():
        if key in merged:
            continue
        merged[key] = prior
        if prior.scope_state == "active":
            factory(
                severity="high",
                finding_type="source-missing",
                subject=key,
                subject_type="requirement",
                feature_id=prior.feature_id,
                description="Il requisito era nello store ma non e' piu' presente in spec.md.",
                recommended_action=(
                    "Se e' stato rimosso di proposito registra la decisione con 'burnup requirement remove'; "
                    "se e' un rinomino, conferma l'alias."
                ),
            )

    requirements = sorted(merged.values(), key=lambda r: (r.feature_id, r.requirement_id))

    # -- 3. relazioni ricostruite dall'evidenza corrente --------------------
    # `valid_from` indica da quando la relazione e' valida, non quando l'abbiamo
    # osservata l'ultima volta: se una relazione identica esisteva gia', si
    # preserva la data originale. Rigenerarla ad ogni scansione perdeva
    # l'informazione "da quando esiste questo collegamento" e produceva un diff
    # Git ad ogni refresh.
    prior_valid_from = {
        (r.from_key, r.to_ref, r.rel_type, r.requirement_fingerprint): r.valid_from
        for r in data.relations
        if r.valid_from
    }

    def _since(from_key: str, to_ref: str, rel_type: str, fingerprint: str) -> str:
        return prior_valid_from.get((from_key, to_ref, rel_type, fingerprint), timestamp)

    relations: list[Relation] = []
    task_completeness: dict[str, bool] = {}

    for req in requirements:
        scan = task_scans.get(req.feature_id)
        if scan is not None:
            for link in getattr(scan, "by_requirement", {}).get(req.requirement_id, []):
                task_completeness[link.task_id] = link.complete
                relations.append(
                    Relation(
                        from_key=req.key,
                        to_ref=link.task_id,
                        rel_type="implemented-by",
                        source="tasks.md",
                        requirement_fingerprint=req.fingerprint,
                        valid_from=_since(req.key, link.task_id, "implemented-by", req.fingerprint),
                    )
                )
        for ev in code_evidence.get(req.key, []):
            relations.append(
                Relation(
                    from_key=req.key,
                    to_ref=ev.ref,
                    rel_type="evidenced-by",
                    source=ev.path,
                    requirement_fingerprint=req.fingerprint,
                    valid_from=_since(req.key, ev.ref, "evidenced-by", req.fingerprint),
                )
            )

    # I collegamenti ai test vengono dalla definizione del test, che e' la
    # fonte autorevole: e' un rispecchiamento, non un'inferenza.
    for td in data.test_definitions:
        for key in td.requirement_keys:
            req = merged.get(key)
            if req is None:
                factory(
                    severity="low",
                    finding_type="test-orphan",
                    subject=td.test_id,
                    subject_type="test",
                    feature_id=key.split("/")[0] if "/" in key else "",
                    description=f"Il test dichiara il requisito '{key}', che non esiste nello store.",
                    recommended_action="Correggi i requirement_keys del test, o verifica se il requisito e' stato rinominato.",
                )
                continue
            relations.append(
                Relation(
                    from_key=key,
                    to_ref=td.test_id,
                    rel_type="verified-by",
                    source="state/test-definitions.json",
                    requirement_fingerprint=req.fingerprint,
                    valid_from=_since(key, td.test_id, "verified-by", req.fingerprint),
                )
            )

    # Le relazioni confermate a mano restano valide finche' il fingerprint
    # combacia: e' cio' che rende le decisioni umane persistenti (P0-03).
    for rel in data.relations:
        if rel.decided_by and rel.is_current:
            req = merged.get(rel.from_key)
            if req is not None and rel.requirement_fingerprint == req.fingerprint:
                relations.append(rel)

    # -- 4. ingestione test ------------------------------------------------
    known_ids = {t.test_id for t in data.test_definitions}
    existing_identities = {r.run_identity for r in data.test_runs if r.run_identity}
    outcome = ingest_reports(config, project_root, known_ids, existing_identities, dirty)
    anomalies.extend((t, d, "") for t, d in outcome.anomalies)

    all_runs = data.test_runs + outcome.new_runs
    latest_runs = latest_run_by_test(all_runs)

    # -- 5. stato ----------------------------------------------------------
    ctx = StatusContext(
        freshness_policy=config.freshness_policy,
        current_revision=revision,
        worktree_dirty=dirty,
        require_tasks_for_implemented=config.require_tasks_for_implemented,
    )
    compute_status(
        requirements,
        relations,
        task_completeness,
        {t.test_id: t for t in data.test_definitions},
        latest_runs,
        ctx,
        factory,
    )

    # -- 6. anomalie strutturali come Finding ------------------------------
    for kind, detail, feature_id in anomalies:
        factory(
            severity=ANOMALY_SEVERITY.get(kind, "low"),
            finding_type=kind,
            subject=detail.split(":")[0][:120],
            subject_type="config" if kind.startswith("unreadable") else "requirement",
            feature_id=feature_id,
            description=detail,
            recommended_action="Correggi l'artefatto di origine indicato nel dettaglio.",
        )

    if revision_problem and config.freshness_policy == "current-revision":
        factory(
            severity="high",
            finding_type="revision-unavailable",
            subject="repository",
            subject_type="config",
            feature_id="",
            description=f"La policy 'current-revision' richiede la revisione Git, non determinabile: {revision_problem}.",
            recommended_action="Inizializza il repository Git, oppure scegli una policy di freschezza diversa.",
        )

    findings = sorted(factory.produced.values(), key=lambda f: (f.feature_id, f.severity, f.finding_id))
    all_findings = findings + factory.resolved()
    blocking = [f for f in findings if f.severity in config.strict_blocks_on and f.is_blocking]

    # -- 7. conteggi e snapshot --------------------------------------------
    counts = compute_counts(requirements)
    previous_snapshot = data.snapshots[-1] if data.snapshots else None
    do_snapshot, reason = should_snapshot(previous_snapshot, counts, forced_snapshot and config.allow_forced_snapshot)

    snapshots = list(data.snapshots)
    if do_snapshot:
        snapshots.append(
            {
                "snapshot_id": snapshot_id(len(snapshots) + 1),
                "timestamp": timestamp,
                "source_revision": revision or "UNKNOWN",
                "worktree_dirty": dirty,
                "reason": reason,
                **counts.to_json(),
            }
        )

    new_data = StoreData(
        requirements=requirements,
        relations=relations,
        test_definitions=data.test_definitions,
        test_runs=all_runs,
        findings=all_findings,
        decisions=data.decisions,
        snapshots=snapshots,
        manifest={
            "scanned_at": timestamp,
            "source_revision": revision,
            "worktree_dirty": dirty,
            "revision_problem": revision_problem,
            "specs_root": specs_label,
            "features": {f.feature_id: f.fingerprints(project_root) for f in features},
            "freshness_policy": config.freshness_policy,
            "engine_schema": "2.0",
        },
    )

    result = ScanResult(
        counts=counts,
        findings=findings,
        blocking=blocking,
        requirements=requirements,
        snapshot_appended=do_snapshot,
        snapshot_reason=reason,
        n_features=len(features),
        specs_root=specs_root,
        new_runs=len(outcome.new_runs),
        skipped_duplicates=outcome.skipped_duplicates,
    )
    return result, new_data
