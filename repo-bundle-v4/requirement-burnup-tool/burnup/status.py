"""Calcolo del ciclo di vita dei requisiti.

Chiude P0-06, P0-08, P1-30 dell'audit, ed e' il modulo che rende impossibile
il probe piu' grave riprodotto in analisi.

Regola che governa tutto: **l'evidenza vale solo se si riferisce al
fingerprint corrente del requisito.** Nella v3 l'evidenza era legata alla
chiave (`001-demo/FR-001`), che non cambia mai quando si riscrive il testo di
un requisito: da qui la possibilita' di certificare `tested` un requisito
completamente diverso da quello effettivamente testato.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Finding, Relation, Requirement, TestDefinition, TestRun


@dataclass
class StatusContext:
    freshness_policy: str
    current_revision: str
    worktree_dirty: bool
    require_tasks_for_implemented: bool


@dataclass
class FreshnessVerdict:
    fresh: bool
    reason: str = ""


def evaluate_freshness(run: TestRun, ctx: StatusContext) -> FreshnessVerdict:
    """Stabilisce se un'esecuzione conta come verifica valida *adesso*.

    `manual-confirmation` nella v3 ritornava incondizionatamente `True`: si
    chiamava "conferma manuale" ma non conteneva alcuna conferma, nessun
    attore, nessuna data. Era di fatto `latest-known` con un nome che
    prometteva un controllo umano inesistente (P0-08).

    Qui la conferma manuale e' un `Decision` registrato nello store, e questa
    funzione la pretende: e' il chiamante a fornire le run gia' validate.
    """
    if ctx.freshness_policy == "latest-known":
        return FreshnessVerdict(True)

    if ctx.freshness_policy == "manual-confirmation":
        if run.revision_origin == "manual":
            return FreshnessVerdict(True)
        if run.source_revision:
            return FreshnessVerdict(True)
        return FreshnessVerdict(
            False,
            "il risultato non ha né una revisione di origine né una conferma manuale registrata",
        )

    if ctx.freshness_policy == "current-revision":
        if not ctx.current_revision:
            return FreshnessVerdict(False, "impossibile determinare la revisione corrente del progetto")
        if not run.source_revision:
            return FreshnessVerdict(
                False,
                "il report non dichiara la revisione su cui il test e' stato eseguito "
                "(usa un sidecar <report>.meta.json prodotto dalla pipeline)",
            )
        if run.revision_origin == "unknown":
            return FreshnessVerdict(False, "l'origine della revisione dichiarata non e' verificabile")
        if run.source_revision != ctx.current_revision:
            return FreshnessVerdict(
                False,
                f"eseguito su {run.source_revision}, la revisione corrente e' {ctx.current_revision}",
            )
        if ctx.worktree_dirty:
            return FreshnessVerdict(
                False,
                "il working tree ha modifiche non committate: la revisione corrente non descrive il codice reale",
            )
        return FreshnessVerdict(True)

    return FreshnessVerdict(False, f"policy di freschezza sconosciuta: {ctx.freshness_policy}")


def current_relations(
    relations: list[Relation],
    requirement: Requirement,
    rel_type: str,
) -> list[Relation]:
    """Relazioni valide ORA per questo requisito nella sua forma corrente.

    Il filtro sul fingerprint e' il meccanismo che fa decadere l'evidenza
    quando il requisito cambia contenuto. Non serve alcuna logica di
    invalidazione esplicita: la relazione semplicemente smette di combaciare.
    """
    return [
        r
        for r in relations
        if r.from_key == requirement.key
        and r.rel_type == rel_type
        and r.is_current
        and r.requirement_fingerprint == requirement.fingerprint
    ]


def compute_status(
    requirements: list[Requirement],
    relations: list[Relation],
    task_completeness: dict[str, bool],
    test_defs_by_id: dict[str, TestDefinition],
    latest_runs: dict[str, TestRun],
    ctx: StatusContext,
    make_finding,
) -> list[Finding]:
    """Ricalcola `lifecycle_state` di ogni requisito attivo, in place.

    Funzione pura dell'evidenza corrente: se l'evidenza non c'e' piu', lo
    stato non viene raggiunto in questo giro. Le regressioni (test che passa a
    fail, marcatore rimosso, requisito riscritto) sono quindi automatiche e
    non richiedono logica dedicata.
    """
    findings: list[Finding] = []

    for req in requirements:
        if req.scope_state != "active":
            continue

        state = "defined"

        # -- implemented --------------------------------------------------
        task_rels = current_relations(relations, req, "implemented-by")
        code_rels = current_relations(relations, req, "evidenced-by")

        has_code = bool(code_rels)
        if task_rels:
            tasks_complete = all(task_completeness.get(r.to_ref, False) for r in task_rels)
        else:
            # P1-30: nella v3 l'assenza di task valeva come "task a posto",
            # quindi il solo marcatore nel codice portava a 'implemented'.
            # Ora e' una scelta di configurazione, e il default e' prudente.
            tasks_complete = not ctx.require_tasks_for_implemented

        if has_code and tasks_complete:
            state = "implemented"
        elif has_code and not tasks_complete:
            findings.append(
                make_finding(
                    severity="medium",
                    finding_type="incomplete-tasks",
                    subject=req.key,
                    subject_type="requirement",
                    feature_id=req.feature_id,
                    description="Evidenza di codice presente, ma non tutti i task collegati risultano completi.",
                    recommended_action="Completa i task residui, oppure correggi il collegamento se non pertinenti.",
                )
            )
        elif not has_code and task_rels and all(task_completeness.get(r.to_ref, False) for r in task_rels):
            findings.append(
                make_finding(
                    severity="medium",
                    finding_type="tasks-complete-without-code-evidence",
                    subject=req.key,
                    subject_type="requirement",
                    feature_id=req.feature_id,
                    description="Tutti i task collegati risultano completi, ma non esiste evidenza di codice per questo requisito.",
                    recommended_action="Aggiungi il marcatore REQ nel commento del codice che implementa il requisito.",
                )
            )

        # -- tested -------------------------------------------------------
        if state == "implemented":
            test_rels = current_relations(relations, req, "verified-by")
            linked_ids = [r.to_ref for r in test_rels]
            mandatory = [
                test_defs_by_id[t] for t in linked_ids if t in test_defs_by_id and test_defs_by_id[t].mandatory
            ]

            if not linked_ids:
                findings.append(
                    make_finding(
                        severity="high",
                        finding_type="missing-mandatory-test",
                        subject=req.key,
                        subject_type="requirement",
                        feature_id=req.feature_id,
                        description="Nessun test collegato: il requisito non puo' raggiungere 'tested'.",
                        recommended_action="Definisci un test con 'burnup test define' e collegalo al requisito.",
                    )
                )
            elif not mandatory:
                findings.append(
                    make_finding(
                        severity="high",
                        finding_type="missing-mandatory-test",
                        subject=req.key,
                        subject_type="requirement",
                        feature_id=req.feature_id,
                        description="Sono collegati solo test non obbligatori.",
                        recommended_action="Marca almeno un test collegato come mandatory, oppure aggiungine uno.",
                    )
                )
            else:
                all_ok = True
                for test in mandatory:
                    run = latest_runs.get(test.test_id)
                    if run is None:
                        all_ok = False
                        findings.append(
                            make_finding(
                                severity="high",
                                finding_type="test-never-run",
                                subject=test.test_id,
                                subject_type="test",
                                feature_id=req.feature_id,
                                description=f"Il test obbligatorio di {req.key} non ha alcuna esecuzione registrata.",
                                recommended_action="Esegui il test e importa il report, oppure registra una conferma manuale.",
                            )
                        )
                        continue

                    if run.result != "pass":
                        all_ok = False
                        findings.append(
                            make_finding(
                                severity="high",
                                finding_type="failing-mandatory-test",
                                subject=test.test_id,
                                subject_type="test",
                                feature_id=req.feature_id,
                                description=f"Ultimo esito '{run.result}' per un test obbligatorio di {req.key}.",
                                recommended_action="Correggi l'implementazione o il test, poi rilancia.",
                            )
                        )
                        continue

                    if not run.evidence_hash:
                        all_ok = False
                        findings.append(
                            make_finding(
                                severity="medium",
                                finding_type="missing-evidence",
                                subject=test.test_id,
                                subject_type="test",
                                feature_id=req.feature_id,
                                description="Esito 'pass' privo di evidenza verificabile.",
                                recommended_action="Importa il report del test, oppure registra una conferma manuale con evidenza.",
                            )
                        )
                        continue

                    verdict = evaluate_freshness(run, ctx)
                    if not verdict.fresh:
                        all_ok = False
                        findings.append(
                            make_finding(
                                severity="medium",
                                finding_type="stale-evidence",
                                subject=test.test_id,
                                subject_type="test",
                                feature_id=req.feature_id,
                                description=f"Evidenza non fresca secondo la policy '{ctx.freshness_policy}': {verdict.reason}.",
                                recommended_action="Rilancia il test sulla revisione corrente, oppure registra una conferma manuale motivata.",
                            )
                        )

                if all_ok:
                    state = "tested"

        req.lifecycle_state = state

    return findings
