"""CLI del Requirement Burn-up.

Chiude P0-03, P0-10 e P1-32 dell'audit.

Due novita' strutturali rispetto alla v3:

1. **Superficie di comando per le decisioni umane.** La v3 dichiarava che
   l'agente avrebbe confermato collegamenti, deciso rimozioni e validato test
   manuali, ma non esisteva alcun comando per farlo: l'unica strada era
   editare a mano le tabelle Markdown generate, cioe' proprio l'operazione
   che la documentazione vietava. Ogni decisione qui e' un comando, e
   produce un record permanente con attore, motivo e revisione.

2. **Exit code che significano qualcosa.** `refresh` restituiva 0 anche con
   findings `high`: verificato su un progetto simulato con un
   `missing-mandatory-test`. Nessuna pipeline poteva bloccare. Ora
   `--strict` restituisce 2 quando esistono finding bloccanti, distinto da 1
   (configurazione) e da 3 (bug dell'engine).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import CONFIG_SCHEMA_VERSION, load_config
from .engine import git_revision, run_scan
from .errors import BurnupError, ConfigError, ExitCode, QualityGateFailed
from .projectstate import render as render_project_state, streak_non_convergenza
from .gates import (
    CHANGE_CLASSES,
    DEFAULT_CHANGE_CLASS,
    GATE_NAMES,
    GATE_SEQUENCE,
    GateDecision,
    check_entry_criteria,
    evaluate_gates,
    format_gate_report,
    gates_for,
    is_promotion,
)
from .ids import decision_id, now_iso, run_id
from .models import Decision, Finding, Relation, TestDefinition, TestRun
from .render import render_dashboard, render_matrix, render_test_register
from .risk_link import read_open_risks
from .specscan import detect_specs_root, discover_features
from .store import Store, StoreLock, atomic_write_text

TEMPLATE_NAME = "requirement-burnup-config.template.yml"


def _config_path(args) -> Path:
    root = Path(args.project_root).resolve()
    return Path(args.config).resolve() if args.config else root / "requirement-burnup-config.yml"


def _load(args):
    root = Path(args.project_root).resolve()
    return root, load_config(_config_path(args), root)


def _emit(payload: dict, as_json: bool, lines: list[str]) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for line in lines:
            print(line)


def cmd_project_state(args) -> int:
    """Rigenera PROJECT-STATE.md dal canonical store.

    Il file e' una proiezione: non contiene nulla che non sia gia' nello store,
    e nessuno deve ricordarsi di aggiornarlo. In particolare il conteggio dei
    rigetti consecutivi sulla stessa causa e' **derivato** dai Gate Decision
    Record, non tenuto a mano — un contatore che qualcuno deve ricordarsi di
    incrementare non fa scattare nessuna regola.
    """
    project_root, config = _load(args)
    store = Store(config.output_dir)
    if not store.state_dir.exists():
        raise ConfigError(
            f"Nessun canonical store in {store.state_dir}.",
            "Esegui prima 'burnup init'.",
        )
    data = store.load()

    manifest = data.manifest
    revision, dirty, _ = git_revision(project_root, config.output_dir)
    specs_root = detect_specs_root(project_root)
    current = {f.feature_id: f.fingerprints(project_root) for f in discover_features(specs_root)}
    recorded = manifest.get("features", {})
    changed = sorted(fid for fid in set(current) | set(recorded) if current.get(fid) != recorded.get(fid))
    if changed:
        freschezza = "stale — artefatti cambiati dopo l'ultimo refresh"
    elif dirty:
        freschezza = "stale — working tree con modifiche non committate"
    elif not manifest.get("scanned_at"):
        freschezza = "unknown — nessun refresh registrato"
    else:
        freschezza = "fresh"

    feature_ids = sorted(
        {r.feature_id for r in data.requirements if r.feature_id}
        | {d.feature_id for d in data.gate_decisions if d.feature_id}
    )
    features = []
    for fid in feature_ids:
        attivi = [r for r in data.requirements if r.feature_id == fid and r.scope_state == "active"]
        stati = evaluate_gates(fid, data.gate_decisions, _feature_fingerprints(project_root, fid, data))
        classe = change_class_of(data, fid)
        features.append({
            "feature_id": fid,
            "change_class": classe,
            "gates": {g: s.status for g, s in sorted(stati.items()) if g in gates_for(classe)},
            "scope": len(attivi),
            "tested": sum(1 for r in attivi if r.lifecycle_state == "tested"),
            "progress_path": f"{specs_root.name}/{fid}/progress.md",
        })

    streaks = streak_non_convergenza(data.gate_decisions)
    aperti = [f for f in data.findings if f.status in ("open", "accepted")]

    testo = render_project_state(
        generato_il=now_iso(),
        versione_engine=f"requirement-burnup (config schema {CONFIG_SCHEMA_VERSION})",
        features=features,
        findings_aperti=aperti,
        streaks=streaks,
        freschezza=freschezza,
    )
    destinazione = project_root / "PROJECT-STATE.md"
    atomic_write_text(destinazione, testo)

    _emit(
        {
            "command": "project-state",
            "written": str(destinazione),
            "features": len(features),
            "non_convergence": streaks,
            "open_findings": len(aperti),
            "freshness": freschezza,
        },
        args.json,
        [
            f"Scritto {destinazione}",
            f"Feature: {len(features)} | Findings aperti: {len(aperti)} | Misurazione: {freschezza}",
        ] + (
            [f"⚠ Non-convergenza su {len(streaks)} causa/e: "
             + ", ".join(f"{s['finding_id']} ({s['rigetti_consecutivi']} rigetti)" for s in streaks)]
            if streaks else ["Nessun ciclo che non converge."]
        ),
    )
    return ExitCode.OK


def _build_reports(data, result, project_root) -> dict[str, str]:
    specs_root = detect_specs_root(project_root)
    open_risks = {f.feature_id: read_open_risks(f.directory) for f in discover_features(specs_root)}
    return {
        "traceability-matrix.md": render_matrix(data.requirements, data.relations, data.findings, data.manifest),
        "test-register.md": render_test_register(data.test_definitions, data.test_runs, data.manifest),
        "governance-dashboard.md": render_dashboard(
            data.requirements, data.findings, result.counts, data.snapshots, open_risks, data.manifest
        ),
    }


# --------------------------------------------------------------------------
# init / refresh / status
# --------------------------------------------------------------------------

def cmd_init(args) -> int:
    project_root, config = _load(args)
    store = Store(config.output_dir)
    if (store.state_dir).exists() and not args.reset:
        raise ConfigError(
            f"Il canonical store esiste gia' in {store.state_dir}.",
            hint="Usa 'refresh' per aggiornarlo, oppure 'init --reset' per ricrearlo da zero.",
        )
    with StoreLock(store.state_dir):
        result, data = run_scan(config, forced_snapshot=True)
        store.commit(data, _build_reports(data, result, project_root))

    _emit(
        {"command": "init", "counts": result.counts.to_json(), "features": result.n_features,
         "findings": len(result.findings), "output_dir": str(config.output_dir)},
        args.json,
        [
            "Inizializzazione completata.",
            f"Layout Spec Kit: {result.specs_root}",
            f"Feature scoperte: {result.n_features}",
            f"Scope attivo: {result.counts.scope} | Defined: {result.counts.defined} | "
            f"Implemented: {result.counts.implemented} | Tested: {result.counts.tested}",
            f"Findings: {len(result.findings)}",
            f"Canonical store: {store.state_dir}",
            f"Report generati: {store.reports_dir}",
        ],
    )
    return ExitCode.OK


#: Quanti finding bloccanti elencare per esteso nell'output leggibile.
#: Oltre questa soglia l'elenco diventa un muro: in simulazione, 486 requisiti
#: senza verifica producevano 491 righe. Il consumatore principale di questo
#: output e' un agente con una finestra di contesto finita, quindi la lunghezza
#: non puo' crescere con la dimensione del progetto. Il conteggio esatto resta
#: nella riga di riepilogo, l'elenco completo in `--json` e nei report.
MAX_FINDING_ELENCATI = 20


def _righe_finding(blocking: list) -> list[str]:
    """Elenca i finding bloccanti, raggruppando la coda invece di stamparla."""
    righe = [
        f"  [{f.finding_id}] {f.severity} {f.finding_type} — {f.subject}: {f.description}"
        for f in blocking[:MAX_FINDING_ELENCATI]
    ]
    resto = len(blocking) - MAX_FINDING_ELENCATI
    if resto > 0:
        per_tipo: dict[str, int] = {}
        for f in blocking[MAX_FINDING_ELENCATI:]:
            per_tipo[f.finding_type] = per_tipo.get(f.finding_type, 0) + 1
        dettaglio = ", ".join(f"{n}× {t}" for t, n in sorted(per_tipo.items(), key=lambda kv: -kv[1]))
        righe.append(f"  … e altri {resto} finding bloccanti ({dettaglio}).")
        righe.append("  Elenco completo: 'burnup refresh --json', oppure requirement-burnup/reports/.")
    return righe


def cmd_refresh(args) -> int:
    project_root, config = _load(args)
    store = Store(config.output_dir)
    with StoreLock(store.state_dir):
        result, data = run_scan(config, forced_snapshot=args.force_snapshot)
        store.commit(data, _build_reports(data, result, project_root))

    lines = [
        "Refresh completato.",
        f"Scope attivo: {result.counts.scope} | Defined: {result.counts.defined} | "
        f"Implemented: {result.counts.implemented} | Tested: {result.counts.tested}",
        f"Snapshot: {'aggiunto' if result.snapshot_appended else 'non necessario'} ({result.snapshot_reason})",
        f"Nuove esecuzioni importate: {result.new_runs} (duplicati ignorati: {result.skipped_duplicates})",
        f"Findings aperti: {len(result.findings)} — bloccanti: {len(result.blocking)}",
    ]
    lines.extend(_righe_finding(result.blocking))

    payload = {
        "command": "refresh",
        "counts": result.counts.to_json(),
        "snapshot_appended": result.snapshot_appended,
        "new_runs": result.new_runs,
        "skipped_duplicates": result.skipped_duplicates,
        "findings": [f.to_json() for f in result.findings],
        "blocking_findings": [f.to_json() for f in result.blocking],
        "strict": bool(args.strict),
    }
    _emit(payload, args.json, lines)

    if args.strict and result.blocking:
        raise QualityGateFailed(
            f"{len(result.blocking)} finding bloccanti impediscono l'approvazione del gate.",
            blocking=[f.finding_id for f in result.blocking],
            hint="Risolvili, oppure registra un waiver motivato con 'burnup finding waive'.",
        )
    return ExitCode.OK


def cmd_status(args) -> int:
    """Sola lettura, e dichiara esplicitamente se lo stato e' fresco.

    Chiude P1-18: la v3 leggeva gli artefatti e li presentava come attuali
    senza verificare se spec, tasks o codice fossero cambiati dopo l'ultimo
    refresh. Un numero vecchio presentato come corrente e' peggio di un
    numero assente.
    """
    project_root, config = _load(args)
    store = Store(config.output_dir)
    if not store.state_dir.exists():
        raise ConfigError(
            f"Nessun canonical store in {store.state_dir}.",
            hint="Esegui prima 'burnup init'.",
        )
    data = store.load()
    manifest = data.manifest

    revision, dirty, _ = git_revision(project_root, config.output_dir)
    specs_root = detect_specs_root(project_root)
    current = {f.feature_id: f.fingerprints(project_root) for f in discover_features(specs_root)}
    recorded = manifest.get("features", {})

    changed = sorted(
        fid for fid in set(current) | set(recorded)
        if current.get(fid) != recorded.get(fid)
    )
    if changed:
        freshness, detail = "stale", f"artefatti cambiati dopo l'ultimo refresh: {', '.join(changed)}"
    elif dirty:
        freshness, detail = "stale", "il working tree ha modifiche non committate"
    elif not manifest.get("scanned_at"):
        freshness, detail = "unknown", "lo store non registra alcun refresh"
    else:
        freshness, detail = "fresh", ""

    active = [r for r in data.requirements if r.scope_state == "active"]
    tested = sum(1 for r in active if r.lifecycle_state == "tested")
    open_findings = [f for f in data.findings if f.status in ("open", "accepted")]
    blocking = [f for f in open_findings if f.is_blocking]

    _emit(
        {
            "command": "status", "freshness": freshness, "freshness_detail": detail,
            "last_scan": manifest.get("scanned_at", ""), "scan_revision": manifest.get("source_revision", ""),
            "current_revision": revision, "worktree_dirty": dirty,
            "scope": len(active), "tested": tested,
            "open_findings": len(open_findings), "blocking_findings": len(blocking),
        },
        args.json,
        [
            f"Freschezza: {freshness.upper()}" + (f" — {detail}" if detail else ""),
            f"Ultimo refresh: {manifest.get('scanned_at', 'mai')} (revisione {manifest.get('source_revision') or 'UNKNOWN'})",
            f"Revisione corrente: {revision or 'UNKNOWN'}{' [dirty]' if dirty else ''}",
            f"Scope attivo: {len(active)} | Tested: {tested}"
            + (f" ({100 * tested / len(active):.1f}%)" if active else ""),
            f"Findings aperti: {len(open_findings)} — bloccanti: {len(blocking)}",
            "(Nessun file modificato: 'status' e' in sola lettura.)",
        ],
    )
    return ExitCode.OK


# --------------------------------------------------------------------------
# Comandi di decisione (P0-03)
# --------------------------------------------------------------------------

def _record_decision(store: Store, data, *, kind, subject, actor, reason, revision, fingerprint="", payload=None) -> Decision:
    decided_at = now_iso()
    decision = Decision(
        decision_id=decision_id(kind, subject, decided_at),
        kind=kind, subject=subject, actor=actor, reason=reason,
        decided_at=decided_at, source_revision=revision,
        requirement_fingerprint=fingerprint, payload=payload or {},
    )
    data.decisions.append(decision)
    return decision


def cmd_test_define(args) -> int:
    project_root, config = _load(args)
    store = Store(config.output_dir)
    with StoreLock(store.state_dir):
        data = store.load()
        known = {r.key for r in data.requirements}
        unknown = [k for k in args.requirement if k not in known]
        if unknown and not args.allow_unknown:
            raise ConfigError(
                f"Requisiti non presenti nello store: {', '.join(unknown)}.",
                hint="Esegui 'burnup refresh', correggi la chiave, oppure usa --allow-unknown.",
            )
        # Chiude P1-12: la v3 costruiva il catalogo con una dict comprehension,
        # quindi due definizioni con lo stesso Test ID si sovrascrivevano in
        # silenzio e vinceva l'ultima letta.
        if any(t.test_id == args.test_id for t in data.test_definitions) and not args.replace:
            raise ConfigError(
                f"Il Test ID '{args.test_id}' esiste gia'.",
                hint="Usa un ID diverso, oppure aggiungi --replace per sostituire la definizione esistente.",
            )

        # C-02: si registra il fingerprint del requisito COM'E' ADESSO. La
        # dichiarazione "questo test verifica questo requisito" e' una
        # decisione umana, e riguarda il testo che l'autore aveva davanti. Se
        # domani quel testo cambia, la dichiarazione va riaffermata.
        fingerprints = {r.key: r.fingerprint for r in data.requirements if r.key in set(args.requirement)}

        # C-09: TEST-REGISTER-SPEC dichiara `definition` obbligatorio —
        # "cosa si verifica e qual e' l'esito atteso". Un catalogo di test
        # senza criterio di esito e' un elenco di nomi.
        if not (args.definition or "").strip():
            raise ConfigError(
                "'--definition' e' obbligatorio e non puo' essere vuoto.",
                hint="Descrivi cosa verifica il test e qual e' l'esito atteso.",
            )

        data.test_definitions = [t for t in data.test_definitions if t.test_id != args.test_id]
        data.test_definitions.append(
            TestDefinition(
                test_id=args.test_id,
                requirement_keys=list(args.requirement),
                kind=args.kind,
                mandatory=args.mandatory,
                definition=args.definition,
                location_or_command=args.command or "",
                owner=args.owner or "",
                environment=args.environment or "",
                requirement_fingerprints=fingerprints,
            )
        )
        revision, _, _ = git_revision(project_root)
        _record_decision(
            store, data, kind="test-define", subject=args.test_id, actor=args.actor,
            reason=args.reason or "definizione del test", revision=revision,
            payload={"requirement_keys": list(args.requirement), "mandatory": args.mandatory},
        )
        store.commit(data)

    _emit({"command": "test define", "test_id": args.test_id}, args.json,
          [f"Test '{args.test_id}' definito e collegato a: {', '.join(args.requirement)}.",
           "Esegui 'burnup refresh' per aggiornare stato e report."])
    return ExitCode.OK


def cmd_test_confirm_manual(args) -> int:
    """Registra una conferma manuale come esecuzione di prima classe.

    Chiude la parte piu' insidiosa di P0-08: la policy `manual-confirmation`
    della v3 ritornava sempre 'fresco' senza contenere alcuna conferma —
    nessun attore, nessuna data, nessuna evidenza. Qui una conferma manuale e'
    una run con attore, motivo, revisione ed evidenza dichiarata.
    """
    project_root, config = _load(args)
    store = Store(config.output_dir)
    with StoreLock(store.state_dir):
        data = store.load()
        if not any(t.test_id == args.test_id for t in data.test_definitions):
            raise ConfigError(
                f"Test ID '{args.test_id}' non definito.",
                hint="Definiscilo prima con 'burnup test define'.",
            )
        revision, dirty, _ = git_revision(project_root, config.output_dir)
        executed_at = args.executed_at or now_iso()
        from .ids import run_identity

        data.test_runs.append(
            TestRun(
                run_id=run_id(),
                run_identity=run_identity(
                    report_hash=f"manual:{args.actor}:{args.evidence}",
                    adapter="manual", test_id=args.test_id,
                    executed_at=executed_at, result=args.result,
                ),
                test_id=args.test_id, result=args.result, executed_at=executed_at,
                source_revision=revision, revision_origin="manual",
                evidence_path=args.evidence, evidence_hash=f"manual:{args.actor}",
                adapter="manual", adapter_version="2.0", imported_at=now_iso(),
                worktree_dirty=dirty, notes=args.reason,
            )
        )
        _record_decision(
            store, data, kind="test-confirm-manual", subject=args.test_id, actor=args.actor,
            reason=args.reason, revision=revision,
            payload={"result": args.result, "evidence": args.evidence, "executed_at": executed_at},
        )
        store.commit(data)

    _emit({"command": "test confirm-manual", "test_id": args.test_id, "result": args.result}, args.json,
          [f"Conferma manuale registrata per '{args.test_id}': {args.result} (attore: {args.actor}).",
           "Esegui 'burnup refresh' per aggiornare stato e report."])
    return ExitCode.OK


def cmd_link_confirm(args) -> int:
    project_root, config = _load(args)
    store = Store(config.output_dir)
    with StoreLock(store.state_dir):
        data = store.load()
        req = next((r for r in data.requirements if r.key == args.requirement), None)
        if req is None:
            raise ConfigError(f"Requisito '{args.requirement}' non presente nello store.")
        revision, _, _ = git_revision(project_root)
        data.relations.append(
            Relation(
                from_key=req.key, to_ref=args.target, rel_type=args.type,
                status="confirmed", source=f"decision:{args.actor}",
                requirement_fingerprint=req.fingerprint, valid_from=now_iso(),
                decided_by=args.actor, reason=args.reason,
            )
        )
        _record_decision(
            store, data, kind="link-confirm", subject=f"{req.key}->{args.target}",
            actor=args.actor, reason=args.reason, revision=revision, fingerprint=req.fingerprint,
            payload={"type": args.type},
        )
        store.commit(data)

    _emit({"command": "link confirm", "requirement": args.requirement, "target": args.target}, args.json,
          [f"Collegamento confermato: {args.requirement} --{args.type}--> {args.target}.",
           "Resta valido finche' il contenuto del requisito non cambia."])
    return ExitCode.OK


def cmd_requirement_remove(args) -> int:
    project_root, config = _load(args)
    store = Store(config.output_dir)
    with StoreLock(store.state_dir):
        data = store.load()
        req = next((r for r in data.requirements if r.key == args.requirement), None)
        if req is None:
            raise ConfigError(f"Requisito '{args.requirement}' non presente nello store.")
        revision, _, _ = git_revision(project_root)
        req.scope_state = "removed"
        req.removed_reason = args.reason
        req.removed_by = args.actor
        req.removed_at = now_iso()
        _record_decision(
            store, data, kind="requirement-remove", subject=req.key, actor=args.actor,
            reason=args.reason, revision=revision, fingerprint=req.fingerprint,
        )
        store.commit(data)

    _emit({"command": "requirement remove", "requirement": args.requirement}, args.json,
          [f"Requisito '{args.requirement}' marcato come rimosso dallo scope attivo.",
           "La storia resta nello store. Esegui 'burnup refresh' per aggiornare i report."])
    return ExitCode.OK


def cmd_finding_waive(args) -> int:
    project_root, config = _load(args)
    store = Store(config.output_dir)
    with StoreLock(store.state_dir):
        data = store.load()
        finding = next((f for f in data.findings if f.finding_id == args.finding_id), None)
        if finding is None:
            raise ConfigError(f"Finding '{args.finding_id}' non presente nello store.")
        revision, _, _ = git_revision(project_root)
        finding.status = "waived"
        finding.waiver_reason = args.reason
        finding.waived_by = args.actor
        finding.waived_at = now_iso()
        finding.waiver_expires = args.expires or ""
        _record_decision(
            store, data, kind="finding-waive", subject=finding.finding_id, actor=args.actor,
            reason=args.reason, revision=revision, payload={"expires": args.expires or ""},
        )
        store.commit(data)

    _emit({"command": "finding waive", "finding_id": args.finding_id, "expires": args.expires or ""}, args.json,
          [f"Finding '{args.finding_id}' sospeso da {args.actor}."
           + (f" Scadenza: {args.expires} (dopo la quale torna aperto automaticamente)." if args.expires else
              " Senza scadenza: valuta se impostarne una.")])
    return ExitCode.OK


def cmd_finding_close(args) -> int:
    project_root, config = _load(args)
    store = Store(config.output_dir)
    with StoreLock(store.state_dir):
        data = store.load()
        finding = next((f for f in data.findings if f.finding_id == args.finding_id), None)
        if finding is None:
            raise ConfigError(f"Finding '{args.finding_id}' non presente nello store.")
        revision, _, _ = git_revision(project_root)
        finding.status = "verified" if args.verified else "resolved"
        _record_decision(
            store, data, kind="finding-close", subject=finding.finding_id, actor=args.actor,
            reason=args.reason, revision=revision,
        )
        store.commit(data)

    _emit({"command": "finding close", "finding_id": args.finding_id, "status": finding.status}, args.json,
          [f"Finding '{args.finding_id}' chiuso come '{finding.status}'.",
           "Se la condizione che lo ha generato persiste, il prossimo refresh lo riaprira'."])
    return ExitCode.OK



# --------------------------------------------------------------------------
# Phase gate (P1-26, P1-27, P1-28)
# --------------------------------------------------------------------------

def _feature_fingerprints(project_root, feature_id: str, data) -> dict[str, str]:
    """Fingerprint correnti degli artefatti di una feature.

    Legge dal filesystem, non dal manifest: lo stato dei gate deve riflettere
    la realta' adesso, non l'ultima volta che qualcuno ha lanciato un refresh.
    """
    features = {f.feature_id: f for f in discover_features(detect_specs_root(project_root))}
    feature = features.get(feature_id)
    if feature is None:
        raise ConfigError(
            f"Feature '{feature_id}' non trovata.",
            hint=f"Feature disponibili: {', '.join(sorted(features)) or 'nessuna'}.",
        )
    fps = feature.fingerprints(project_root)
    # Il "codice" e' rappresentato dall'insieme delle relazioni di evidenza
    # correnti: e' cio' che il Gate 4 approva davvero.
    code_refs = sorted(
        r.to_ref for r in data.relations
        if r.rel_type == "evidenced-by" and r.is_current and r.from_key.startswith(f"{feature_id}/")
    )
    if code_refs:
        from .fingerprint import sha256_hex
        fps["code"] = sha256_hex(*code_refs)
    return fps


def change_class_of(data, feature: str) -> str:
    """Classe di change corrente di una feature.

    C-10: non serve un campo nuovo nel canonical store. La classe e' una
    decisione umana, e le decisioni hanno gia' una casa in `decisions.jsonl`
    con attore, motivo e data. La classe corrente e' semplicemente l'ultima
    decisione registrata per quella feature.
    """
    dichiarata = declared_class_of(data, feature)
    return dichiarata if dichiarata else DEFAULT_CHANGE_CLASS


def declared_class_of(data, feature: str) -> str:
    """La classe ESPLICITAMENTE dichiarata, o stringa vuota se non lo e' mai stata.

    Serve a distinguere due casi che il divieto di retrocessione tratterebbe
    altrimenti allo stesso modo: la prima dichiarazione di una feature nuova
    non e' una retrocessione, anche quando sceglie una classe piu' leggera del
    default. Il documento parla di promozione *in corsa*, cioe' dopo che una
    classe esiste.
    """
    scelte = [
        d for d in data.decisions
        if d.kind == "feature-class" and d.subject == feature
    ]
    return scelte[-1].payload.get("change_class", "") if scelte else ""


def cmd_feature_class(args) -> int:
    project_root, config = _load(args)
    store = Store(config.output_dir)
    with StoreLock(store.state_dir):
        data = store.load()
        attuale = declared_class_of(data, args.feature)
        if attuale and not is_promotion(attuale, args.change_class):
            raise ConfigError(
                f"La feature '{args.feature}' e' in classe '{attuale}': "
                f"non puo' essere retrocessa a '{args.change_class}'.",
                hint=(
                    "La promozione e' ammessa in corsa, la retrocessione no: significherebbe "
                    "rimuovere un controllo dopo aver visto cosa avrebbe trovato."
                ),
            )
        revision, _, _ = git_revision(project_root)
        _record_decision(
            store, data, kind="feature-class", subject=args.feature, actor=args.actor,
            reason=args.reason, revision=revision,
            payload={"change_class": args.change_class, "previous": attuale},
        )
        store.commit(data)

    gate_previsti = ", ".join(map(str, gates_for(args.change_class)))
    _emit(
        {"command": "feature class", "feature": args.feature,
         "change_class": args.change_class, "previous": attuale,
         "gates": list(gates_for(args.change_class))},
        args.json,
        [f"Feature '{args.feature}': classe '{attuale or 'non dichiarata'}' -> '{args.change_class}'.",
         f"Gate previsti: {gate_previsti}.",
         "Tracciabilita', test obbligatori e 'refresh --strict' restano identici in ogni classe."],
    )
    return ExitCode.OK


def cmd_gate_status(args) -> int:
    project_root, config = _load(args)
    data = Store(config.output_dir).load()
    fps = _feature_fingerprints(project_root, args.feature, data)
    states = evaluate_gates(args.feature, data.gate_decisions, fps)
    classe = change_class_of(data, args.feature)

    _emit(
        {
            "command": "gate status",
            "feature": args.feature,
            "change_class": classe,
            "gates_required": list(gates_for(classe)),
            "current_fingerprints": fps,
            "gates": {
                str(g): {
                    "status": s.status,
                    "name": GATE_NAMES[g],
                    "approver": s.decision.approver if s.decision else "",
                    "approved_at": s.decision.approved_at if s.decision else "",
                    "invalidated_by": s.invalidated_by,
                    "conditions": s.decision.conditions if s.decision else [],
                }
                for g, s in states.items()
            },
        },
        args.json,
        format_gate_report(args.feature, states, classe),
    )
    return ExitCode.OK


def cmd_gate_approve(args) -> int:
    """Approva un gate registrando un evidence package completo.

    Rifiuta l'approvazione se i criteri di ingresso non sono soddisfatti. E'
    la differenza sostanziale con la v3, dove approvare un gate significava
    spuntare una casella in un file Markdown: nulla verificava che il gate
    precedente esistesse, né che i finding bloccanti fossero stati chiusi.
    """
    project_root, config = _load(args)
    store = Store(config.output_dir)
    with StoreLock(store.state_dir):
        data = store.load()
        fps = _feature_fingerprints(project_root, args.feature, data)
        states = evaluate_gates(args.feature, data.gate_decisions, fps)

        open_findings = [
            f for f in data.findings
            if f.feature_id == args.feature and f.status in ("open", "accepted")
        ]
        blocking = [f for f in open_findings if f.is_blocking]

        unmet = check_entry_criteria(
            args.gate, states, fps, blocking, change_class_of(data, args.feature)
        )
        if unmet and not args.force:
            raise QualityGateFailed(
                f"Il Gate {args.gate} ({GATE_NAMES[args.gate]}) non e' approvabile: "
                f"{len(unmet)} criteri di ingresso non soddisfatti.\n  - " + "\n  - ".join(unmet),
                blocking=[f.finding_id for f in blocking],
                hint="Risolvi i criteri elencati. --force registra comunque la decisione, ma la marca conditionally-approved.",
            )

        outcome = "conditionally-approved" if (unmet or args.condition) else "approved"
        approved_at = now_iso()
        revision, dirty, _ = git_revision(project_root, config.output_dir)

        active = [r for r in data.requirements if r.feature_id == args.feature and r.scope_state == "active"]
        decision = GateDecision(
            decision_id=f"GATE-{args.gate}-{args.feature}-{approved_at.replace(':', '').replace('-', '')}",
            feature_id=args.feature,
            gate=args.gate,
            outcome=outcome,
            approver=args.actor,
            approved_at=approved_at,
            rationale=args.reason,
            source_revision=revision,
            artifact_fingerprints=fps,
            open_findings=[f.finding_id for f in open_findings],
            waivers=[f.finding_id for f in data.findings if f.feature_id == args.feature and f.status == "waived"],
            conditions=list(args.condition or []) + ([f"criterio non soddisfatto: {u}" for u in unmet] if args.force else []),
            burnup_counts={
                "scope": len(active),
                "tested": sum(1 for r in active if r.lifecycle_state == "tested"),
                "worktree_dirty": dirty,
            },
        )
        data.gate_decisions.append(decision)
        store.commit(data)

    lines = [
        f"Gate {args.gate} ({GATE_NAMES[args.gate]}) — {outcome.upper()} per '{args.feature}'.",
        f"  decision_id: {decision.decision_id}",
        f"  approvato da: {args.actor} il {approved_at}",
        f"  baseline: " + ", ".join(f"{k}={v[:12]}" for k, v in sorted(fps.items())),
        f"  findings aperti: {len(decision.open_findings)} | waiver: {len(decision.waivers)}",
    ]
    for c in decision.conditions:
        lines.append(f"  condizione: {c}")
    if outcome == "conditionally-approved":
        lines.append("  ⚠ approvazione condizionata: le condizioni vanno chiuse prima del gate successivo.")

    _emit({"command": "gate approve", "decision": decision.to_json()}, args.json, lines)
    return ExitCode.OK


def cmd_gate_reject(args) -> int:
    project_root, config = _load(args)
    store = Store(config.output_dir)
    with StoreLock(store.state_dir):
        data = store.load()
        fps = _feature_fingerprints(project_root, args.feature, data)
        revision, _, _ = git_revision(project_root)
        approved_at = now_iso()
        decision = GateDecision(
            decision_id=f"GATE-{args.gate}-{args.feature}-{approved_at.replace(':', '').replace('-', '')}",
            feature_id=args.feature, gate=args.gate, outcome="rejected",
            approver=args.actor, approved_at=approved_at, rationale=args.reason,
            source_revision=revision, artifact_fingerprints=fps,
        )
        data.gate_decisions.append(decision)
        store.commit(data)

    _emit({"command": "gate reject", "decision": decision.to_json()}, args.json,
          [f"Gate {args.gate} RESPINTO per '{args.feature}' da {args.actor}.",
           f"  motivo: {args.reason}",
           "  Il Maker competente deve correggere e richiedere una nuova approvazione."])
    return ExitCode.OK


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    """Parser che rispetta il contratto degli exit code.

    C-08: `ExitCode.USAGE_ERROR = 4` era definito e mai usato. Argparse esce di
    default con 2, che qui significa "quality gate fallito" ed e' contratto
    pubblico: una pipeline non poteva distinguere un refuso sulla riga di
    comando da un gate respinto, cioe' "hai sbagliato a scrivere" da "il codice
    non e' pronto".

    I sottoparser ereditano questa classe: `add_subparsers` usa `type(self)`.
    """

    def error(self, message: str):  # noqa: D102
        self.print_usage(sys.stderr)
        print(f"ERRORE [usage-error]: {message}", file=sys.stderr)
        raise SystemExit(ExitCode.USAGE_ERROR)


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project-root", default=".", help="Radice del progetto Spec Kit (default: directory corrente)")
    common.add_argument("--config", default=None, help="Percorso di requirement-burnup-config.yml")
    common.add_argument("--json", action="store_true", help="Output machine-readable")

    actor = argparse.ArgumentParser(add_help=False)
    actor.add_argument("--actor", required=True, help="Chi prende la decisione (obbligatorio: una decisione senza autore non e' auditabile)")
    actor.add_argument("--reason", required=True, help="Motivo della decisione")

    p = _Parser(prog="burnup", description="Requirement Burn-up per Spec Kit")
    p.add_argument("--version", action="version", version="requirement-burnup 4.0.1 "
                                                          f"(config schema {CONFIG_SCHEMA_VERSION})")
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", parents=[common], help="Crea il canonical store ed esegue la prima scansione")
    p_init.add_argument("--reset", action="store_true", help="Ricrea lo store da zero (la storia esistente viene persa)")
    p_init.set_defaults(func=cmd_init)

    p_ref = sub.add_parser("refresh", parents=[common], help="Aggiorna stato e report")
    p_ref.add_argument("--force-snapshot", action="store_true", help="Registra uno snapshot anche a conteggi invariati")
    p_ref.add_argument("--strict", action="store_true",
                       help="Esce con codice 2 se esistono finding bloccanti (da usare PRIMA dell'approvazione del Gate 4)")
    p_ref.set_defaults(func=cmd_refresh)

    p_st = sub.add_parser("status", parents=[common], help="Stato corrente e sua freschezza (sola lettura)")
    p_st.set_defaults(func=cmd_status)

    p_ps = sub.add_parser("project-state", parents=[common],
                          help="Rigenera PROJECT-STATE.md dal canonical store")
    p_ps.set_defaults(func=cmd_project_state)

    # -- test -------------------------------------------------------------
    p_test = sub.add_parser("test", help="Gestione delle definizioni di test")
    test_sub = p_test.add_subparsers(dest="subcommand", required=True)

    p_td = test_sub.add_parser("define", parents=[common, actor], help="Definisce un test e lo collega ai requisiti")
    p_td.add_argument("test_id")
    p_td.add_argument("--requirement", action="append", required=True, help="Chiave del requisito (ripetibile)")
    p_td.add_argument("--definition", required=True, help="Cosa verifica il test e quale sia l'esito atteso")
    p_td.add_argument("--kind", default="unit", choices=["unit", "integration", "e2e", "manual", "performance", "security"])
    p_td.add_argument("--mandatory", action="store_true", help="Il requisito non puo' raggiungere 'tested' senza questo test")
    p_td.add_argument("--command", default="", help="Comando o percorso per eseguirlo")
    p_td.add_argument("--owner", default="")
    p_td.add_argument("--environment", default="")
    p_td.add_argument("--replace", action="store_true", help="Sostituisce una definizione esistente con lo stesso ID")
    p_td.add_argument("--allow-unknown", action="store_true", help="Consente di collegare requisiti non ancora nello store")
    p_td.set_defaults(func=cmd_test_define)

    p_tc = test_sub.add_parser("confirm-manual", parents=[common, actor], help="Registra una conferma manuale di esecuzione")
    p_tc.add_argument("test_id")
    p_tc.add_argument("--result", default="pass", choices=["pass", "fail", "blocked", "error"])
    p_tc.add_argument("--evidence", required=True, help="Riferimento all'evidenza: screenshot, verbale, ticket")
    p_tc.add_argument("--executed-at", default="", help="Ora di esecuzione ISO-8601 (default: adesso)")
    p_tc.set_defaults(func=cmd_test_confirm_manual)

    # -- link -------------------------------------------------------------
    p_link = sub.add_parser("link", help="Conferma di collegamenti non deducibili automaticamente")
    link_sub = p_link.add_subparsers(dest="subcommand", required=True)
    p_lc = link_sub.add_parser("confirm", parents=[common, actor])
    p_lc.add_argument("requirement")
    p_lc.add_argument("target", help="Task ID, percorso:riga, o Test ID")
    p_lc.add_argument("--type", default="implemented-by", choices=["implemented-by", "evidenced-by", "verified-by", "derived-from"])
    p_lc.set_defaults(func=cmd_link_confirm)

    # -- requirement ------------------------------------------------------
    p_req = sub.add_parser("requirement", help="Decisioni di scope sui requisiti")
    req_sub = p_req.add_subparsers(dest="subcommand", required=True)
    p_rr = req_sub.add_parser("remove", parents=[common, actor])
    p_rr.add_argument("requirement")
    p_rr.set_defaults(func=cmd_requirement_remove)

    # -- finding ----------------------------------------------------------
    p_find = sub.add_parser("finding", help="Ciclo di vita dei rilievi")
    find_sub = p_find.add_subparsers(dest="subcommand", required=True)
    p_fw = find_sub.add_parser("waive", parents=[common, actor])
    p_fw.add_argument("finding_id")
    p_fw.add_argument("--expires", default="", help="Scadenza ISO-8601: dopo, il finding torna aperto da solo")
    p_fw.set_defaults(func=cmd_finding_waive)
    p_fc = find_sub.add_parser("close", parents=[common, actor])
    p_fc.add_argument("finding_id")
    p_fc.add_argument("--verified", action="store_true", help="Chiusura verificata da un Checker indipendente")
    p_fc.set_defaults(func=cmd_finding_close)

    # -- gate -------------------------------------------------------------
    p_feat = sub.add_parser("feature", help="Proprieta' di una feature")
    feat_sub = p_feat.add_subparsers(dest="subcommand", required=True)
    p_class = feat_sub.add_parser(
        "class", parents=[common, actor],
        help="Dichiara la classe di change (docs/SCALE-ADAPTIVE-FLOW.md)",
    )
    p_class.add_argument("feature")
    p_class.add_argument("change_class", choices=CHANGE_CLASSES)
    p_class.set_defaults(func=cmd_feature_class)

    p_gate = sub.add_parser("gate", help="Phase gate: stato, approvazione, rifiuto")
    gate_sub = p_gate.add_subparsers(dest="subcommand", required=True)

    p_gs = gate_sub.add_parser("status", parents=[common], help="Stato dei gate di una feature")
    p_gs.add_argument("feature")
    p_gs.set_defaults(func=cmd_gate_status)

    p_ga = gate_sub.add_parser("approve", parents=[common, actor], help="Approva un gate con evidence package")
    p_ga.add_argument("feature")
    p_ga.add_argument("gate", type=int, choices=list(GATE_SEQUENCE))
    p_ga.add_argument("--condition", action="append", help="Condizione di approvazione (ripetibile)")
    p_ga.add_argument("--force", action="store_true",
                      help="Registra la decisione anche con criteri non soddisfatti, marcandola conditionally-approved")
    p_ga.set_defaults(func=cmd_gate_approve)

    p_gr = gate_sub.add_parser("reject", parents=[common, actor], help="Respinge un gate")
    p_gr.add_argument("feature")
    p_gr.add_argument("gate", type=int, choices=list(GATE_SEQUENCE))
    p_gr.set_defaults(func=cmd_gate_reject)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # `--help` e `--version` escono con 0; gli errori d'uso con
        # ExitCode.USAGE_ERROR grazie a `_Parser.error`. Ritornare il codice
        # invece di propagare l'eccezione mantiene `main()` una funzione che
        # restituisce un exit code, com'è per tutti gli altri percorsi.
        return int(exc.code or ExitCode.OK)
    try:
        return args.func(args)
    except BurnupError as exc:
        if getattr(args, "json", False):
            print(json.dumps(exc.as_dict(), ensure_ascii=False, indent=2), file=sys.stderr)
        else:
            print(f"ERRORE [{exc.kind}]: {exc.message}", file=sys.stderr)
            if exc.hint:
                print(f"  → {exc.hint}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:  # pragma: no cover - richiede un segnale reale
        print("Interrotto.", file=sys.stderr)
        return ExitCode.ENGINE_ERROR
    except Exception as exc:
        # Senza questo ramo, qualunque eccezione non prevista risaliva come
        # traceback grezzo e il processo usciva con 1 — che il contratto
        # riserva a CONFIG_ERROR, "correggi il file". Chi legge veniva mandato
        # a cercare un errore nella propria configurazione mentre il guasto
        # era nell'engine. E' il difetto che il docstring di `errors.py`
        # dichiara chiuso dalla v3 in avanti; era rimasto aperto qui.
        #
        # Riprodotto in simulazione: su un filesystem che nega `unlink`, il
        # rilascio del lock del canonical store ha prodotto un
        # `PermissionError` e dodici righe di traceback.
        if getattr(args, "json", False):
            print(
                json.dumps(
                    {
                        "error": "engine-error",
                        "message": f"{type(exc).__name__}: {exc}",
                        "hint": "E' un bug dell'engine: segnalalo, non aggirarlo.",
                        "exit_code": ExitCode.ENGINE_ERROR,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
        else:
            print(f"ERRORE [engine-error]: {type(exc).__name__}: {exc}", file=sys.stderr)
            print("  → E' un bug dell'engine, non un problema della tua configurazione.", file=sys.stderr)
            print("     Segnalalo allegando il comando eseguito. Nessun aggiramento è previsto.", file=sys.stderr)
        return ExitCode.ENGINE_ERROR


if __name__ == "__main__":  # pragma: no cover - punto d'ingresso del processo
    raise SystemExit(main())
