"""
Calcolo dello stato di ciclo di vita (defined/implemented/tested) per ogni requisito.

Scelta di design: lo stato viene ricalcolato da zero ad ogni refresh, come
funzione pura dell'evidenza attualmente disponibile — non come una macchina a
stati che si muove solo in avanti. Questo implementa automaticamente le
regressioni descritte in STATUS-RULES.md (es. test che fallisce riporta
'tested' a 'implemented') senza bisogno di logica speciale: se l'evidenza
non c'è più, lo stato semplicemente non viene raggiunto in questo giro.
"""
from __future__ import annotations

from dataclasses import dataclass

from .requirements import Finding, RequirementRow
from .tests_register import TestDefinition


@dataclass
class StatusContext:
    freshness_policy: str  # "current-revision" | "latest-known" | "manual-confirmation"
    current_source_revision: str  # es. output di `git rev-parse --short HEAD`, oppure "" se non disponibile


def _test_is_fresh(test: TestDefinition, ctx: StatusContext) -> tuple[bool, str]:
    """Ritorna (is_fresh, motivo_se_non_fresco)."""
    if ctx.freshness_policy == "manual-confirmation":
        # Politica meno rigorosa per default (vedi DESIGN-DECISIONS del framework):
        # un risultato 'pass' registrato conta come valido finché non viene
        # esplicitamente invalidato (nessun controllo automatico di revisione).
        return True, ""

    if ctx.freshness_policy == "latest-known":
        return True, ""

    if ctx.freshness_policy == "current-revision":
        if not ctx.current_source_revision:
            return False, "impossibile determinare la revisione corrente del progetto (repo Git assente o non leggibile)"
        if not test.source_revision:
            return False, "il test non riporta alcuna source_revision"
        if test.source_revision != ctx.current_source_revision:
            return False, f"la revisione del test ({test.source_revision}) non è quella corrente ({ctx.current_source_revision})"
        return True, ""

    return False, f"policy di freschezza sconosciuta: {ctx.freshness_policy}"


def compute_status(
    rows: list[RequirementRow],
    task_links_by_feature: dict[str, dict[str, dict]],
    test_defs_by_id: dict[str, TestDefinition],
    ctx: StatusContext,
) -> tuple[list[RequirementRow], list[Finding]]:
    findings: list[Finding] = []
    finding_seq = 1

    def next_finding_id() -> str:
        nonlocal finding_seq
        fid = f"FND-STATUS-{finding_seq:03d}"
        finding_seq += 1
        return fid

    for row in rows:
        if row.scope_state != "active":
            continue  # i requisiti rimossi mantengono l'ultimo stato noto, non si ricalcolano

        # --- defined ---
        # già garantito dall'estrazione (chiave stabile + testo non vuoto): resta 'defined' come base.
        state = "defined"

        # --- implemented ---
        has_code_evidence = bool(row.code_evidence) and row.link_state == "confirmed"
        task_info = task_links_by_feature.get(row.feature, {}).get(row.requirement_id)
        tasks_ok = (task_info is None) or task_info.get("all_complete", False)

        if has_code_evidence and tasks_ok:
            state = "implemented"
        elif has_code_evidence and not tasks_ok:
            findings.append(
                Finding(
                    finding_id=next_finding_id(),
                    severity="medium",
                    finding_type="incomplete-tasks",
                    subject=row.requirement_key,
                    description="Evidenza di codice presente ma non tutti i task collegati risultano completi.",
                    recommended_action="Completa i task residui o correggi il collegamento se non pertinenti.",
                )
            )

        # --- tested ---
        if state == "implemented":
            linked_test_ids = [t.strip().strip("`") for t in row.test_ids.split(",") if t.strip()]
            mandatory_tests = [test_defs_by_id[tid] for tid in linked_test_ids if tid in test_defs_by_id and test_defs_by_id[tid].mandatory == "yes"]

            if not linked_test_ids:
                findings.append(
                    Finding(
                        finding_id=next_finding_id(),
                        severity="high",
                        finding_type="missing-mandatory-test",
                        subject=row.requirement_key,
                        description="Nessun test collegato: il requisito non può raggiungere 'tested'.",
                        recommended_action="Definisci almeno un test obbligatorio nel Test Register e collegalo.",
                    )
                )
            elif not mandatory_tests:
                findings.append(
                    Finding(
                        finding_id=next_finding_id(),
                        severity="high",
                        finding_type="missing-mandatory-test",
                        subject=row.requirement_key,
                        description="Sono collegati solo test non obbligatori (mandatory=no).",
                        recommended_action="Marca almeno un test collegato come mandatory=yes, o aggiungine uno.",
                    )
                )
            else:
                all_pass = True
                for test in mandatory_tests:
                    if test.last_result != "pass":
                        all_pass = False
                        findings.append(
                            Finding(
                                finding_id=next_finding_id(),
                                severity="high",
                                finding_type="failing-mandatory-test",
                                subject=test.test_id,
                                description=f"Risultato attuale '{test.last_result}' per un test obbligatorio di {row.requirement_key}.",
                                recommended_action="Correggi l'implementazione o il test, poi rilancia.",
                            )
                        )
                        continue
                    if not test.evidence:
                        all_pass = False
                        findings.append(
                            Finding(
                                finding_id=next_finding_id(),
                                severity="medium",
                                finding_type="missing-evidence",
                                subject=test.test_id,
                                description="Risultato 'pass' privo di un riferimento a evidenza (report o conferma manuale).",
                                recommended_action="Allega il percorso del report o la conferma manuale nella colonna Evidence.",
                            )
                        )
                        continue
                    fresh, reason = _test_is_fresh(test, ctx)
                    if not fresh:
                        all_pass = False
                        findings.append(
                            Finding(
                                finding_id=next_finding_id(),
                                severity="medium",
                                finding_type="stale-evidence",
                                subject=test.test_id,
                                description=f"Evidenza non fresca secondo la policy '{ctx.freshness_policy}': {reason}.",
                                recommended_action="Rilancia il test sulla revisione corrente, oppure conferma manualmente la validità.",
                            )
                        )
                if all_pass:
                    state = "tested"

        row.lifecycle_state = state

    return rows, findings
