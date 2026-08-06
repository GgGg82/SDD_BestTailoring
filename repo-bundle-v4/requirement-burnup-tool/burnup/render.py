"""Proiezioni Markdown del canonical store.

Chiude P0-05 e P1-19 dell'audit.

Questo modulo produce testo e basta. Non legge nulla, non decide nulla, e i
suoi output non rientrano MAI nell'engine. E' la differenza strutturale con la
v3, dove gli stessi file erano contemporaneamente report leggibile e database
transazionale: da li' nascevano sia la corruzione da escape dei pipe sia
l'impossibilita' di garantire l'append-only.

Conseguenza pratica per chi usa il framework: cancellare i file in `reports/`
non perde nulla. Si rigenerano dallo stato.
"""
from __future__ import annotations

from .fingerprint import short
from .mdparse import render_table
from .models import Counts, Finding, Requirement

GENERATED_BANNER = (
    "> **File generato — non modificare a mano.**\n"
    "> La fonte di verita' e' il canonical store in `../state/`. Ogni modifica qui viene\n"
    "> sovrascritta al prossimo refresh. Per registrare una decisione usa i comandi\n"
    "> `burnup link confirm`, `burnup requirement remove`, `burnup test define`,\n"
    "> `burnup test confirm-manual`, `burnup finding waive`, `burnup finding close`.\n"
)


def _frontmatter(**fields) -> str:
    lines = ["---"]
    for k, v in fields.items():
        if isinstance(v, bool):
            v = "true" if v else "false"
        lines.append(f'{k}: "{v}"')
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _dash(value: str) -> str:
    return value if value else "—"


def render_matrix(
    requirements: list[Requirement],
    relations: list,
    findings: list[Finding],
    manifest: dict,
) -> str:
    by_key: dict[str, dict[str, list[str]]] = {}
    for rel in relations:
        if not rel.is_current:
            continue
        slot = by_key.setdefault(rel.from_key, {"implemented-by": [], "evidenced-by": [], "verified-by": []})
        if rel.rel_type in slot:
            slot[rel.rel_type].append(rel.to_ref)

    headers = [
        "Requirement Key", "Feature", "ID", "Requirement", "Fingerprint", "Source",
        "User Story", "Scope", "Lifecycle", "Tasks", "Code Evidence", "Tests", "Notes",
    ]
    rows = []
    for r in requirements:
        links = by_key.get(r.key, {})
        rows.append({
            "Requirement Key": r.key,
            "Feature": r.feature_id,
            "ID": r.requirement_id,
            "Requirement": r.text,
            "Fingerprint": short(r.fingerprint),
            "Source": f"{r.source}:{r.source_line}",
            # L'origine e' esplicita: dopo P0-04 il lettore deve poter
            # distinguere un'appartenenza strutturale da un tag inline, e
            # soprattutto vedere quando non ce n'e' nessuna.
            "User Story": f"{r.user_story} ({r.user_story_origin})" if r.user_story else "—",
            "Scope": r.scope_state,
            "Lifecycle": r.lifecycle_state,
            "Tasks": _dash(", ".join(sorted(set(links.get("implemented-by", []))))),
            "Code Evidence": _dash(", ".join(sorted(set(links.get("evidenced-by", []))))),
            "Tests": _dash(", ".join(sorted(set(links.get("verified-by", []))))),
            "Notes": r.notes,
        })

    open_findings = [f for f in findings if f.status in ("open", "accepted")]
    f_headers = ["Finding ID", "Severity", "Status", "Type", "Subject", "Feature", "Description", "Recommended Action", "First Seen"]
    f_rows = [{
        "Finding ID": f.finding_id,
        "Severity": f.severity,
        "Status": f.status,
        "Type": f.finding_type,
        "Subject": f.subject,
        "Feature": _dash(f.feature_id),
        "Description": f.description,
        "Recommended Action": f.recommended_action,
        "First Seen": f.first_seen,
    } for f in open_findings]

    return (
        _frontmatter(
            artifact="traceability-matrix",
            generated_at=manifest.get("scanned_at", ""),
            source_revision=manifest.get("source_revision") or "UNKNOWN",
            worktree_dirty=manifest.get("worktree_dirty", False),
        )
        + "# Traceability Matrix\n\n"
        + GENERATED_BANNER
        + "\n## Matrix\n\n"
        + render_table(headers, rows)
        + "\n## Findings\n\n"
        + (render_table(f_headers, f_rows) if f_rows else "_Nessun finding aperto._\n")
    )


def render_test_register(test_defs: list, runs: list, manifest: dict) -> str:
    from .ingest import latest_run_by_test

    latest = latest_run_by_test(runs)

    headers = [
        "Test ID", "Requirement Keys", "Kind", "Mandatory", "Definition / Expected Result",
        "Location or Command", "Owner", "Last Run", "Last Result", "Source Revision", "Evidence", "Evidence Hash",
    ]
    rows = []
    for t in sorted(test_defs, key=lambda t: t.test_id):
        run = latest.get(t.test_id)
        rows.append({
            "Test ID": t.test_id,
            "Requirement Keys": _dash(", ".join(t.requirement_keys)),
            "Kind": t.kind,
            "Mandatory": "yes" if t.mandatory else "no",
            "Definition / Expected Result": t.definition,
            "Location or Command": t.location_or_command,
            "Owner": _dash(t.owner),
            "Last Run": _dash(run.executed_at if run else ""),
            "Last Result": run.result if run else "not-run",
            # L'origine della revisione e' mostrata perche' dopo P0-08 il
            # lettore deve sapere se quel valore viene dal report o e' stato
            # dedotto: nella v3 era sempre l'HEAD del refresh, e nulla lo diceva.
            "Source Revision": _dash(f"{run.source_revision} ({run.revision_origin})" if run and run.source_revision else ""),
            "Evidence": _dash(run.evidence_path if run else ""),
            "Evidence Hash": _dash(short(run.evidence_hash) if run else ""),
        })

    h_headers = ["Run ID", "Executed At", "Test ID", "Result", "Source Revision", "Duration", "Evidence", "Evidence Hash", "Imported At", "Adapter"]
    h_rows = [{
        "Run ID": r.run_id,
        "Executed At": r.executed_at,
        "Test ID": r.test_id,
        "Result": r.result,
        "Source Revision": _dash(r.source_revision),
        "Duration": _dash(r.duration),
        "Evidence": _dash(r.evidence_path),
        "Evidence Hash": short(r.evidence_hash),
        "Imported At": r.imported_at,
        "Adapter": f"{r.adapter} {r.adapter_version}".strip(),
    } for r in sorted(runs, key=lambda r: (r.executed_at, r.run_id))]

    return (
        _frontmatter(
            artifact="test-register",
            generated_at=manifest.get("scanned_at", ""),
            source_revision=manifest.get("source_revision") or "UNKNOWN",
        )
        + "# Test Register\n\n"
        + GENERATED_BANNER
        + "\n## Test Catalogue and Latest State\n\n"
        + (render_table(headers, rows) if rows else "_Nessun test definito. Usa `burnup test define`._\n")
        + "\n## Execution History\n\n"
        + (render_table(h_headers, h_rows) if h_rows else "_Nessuna esecuzione registrata._\n")
    )


def _burnup_chart(snapshots: list[dict]) -> str:
    if not snapshots:
        return "```\nNessuno snapshot registrato.\n```\n"
    recent = snapshots[-20:]
    labels = ", ".join(f'"{s.get("snapshot_id", "")}"' for s in recent)

    def series(key: str) -> str:
        return ", ".join(str(s.get(key, 0)) for s in recent)

    return (
        "```mermaid\nxychart-beta\n"
        f'    title "Requirement Burn-up"\n'
        f"    x-axis [{labels}]\n"
        '    y-axis "Requisiti"\n'
        f"    line [{series('scope')}]\n"
        f"    line [{series('defined')}]\n"
        f"    line [{series('implemented')}]\n"
        f"    line [{series('tested')}]\n"
        "```\n\n_Serie, dall'alto: Scope, Defined, Implemented, Tested._\n"
    )


def render_dashboard(
    requirements: list[Requirement],
    findings: list[Finding],
    counts: Counts,
    snapshots: list[dict],
    open_risks_by_feature: dict,
    manifest: dict,
) -> str:
    pct = f"{100 * counts.tested / counts.scope:.1f}%" if counts.scope else "N/A"
    summary = [
        {"Metric": "Active scope", "Value": str(counts.scope)},
        {"Metric": "Defined", "Value": str(counts.defined)},
        {"Metric": "Implemented", "Value": str(counts.implemented)},
        {"Metric": "Tested / Done", "Value": str(counts.tested)},
        {"Metric": "Done %", "Value": pct},
        {"Metric": "Removed (cumulative)", "Value": str(counts.removed_total)},
        {"Metric": "Scope fingerprint", "Value": short(counts.scope_fingerprint)},
    ]

    open_findings = [f for f in findings if f.status in ("open", "accepted")]
    blocking = [f for f in open_findings if f.is_blocking]

    feature_ids = sorted({r.feature_id for r in requirements})
    f_headers = ["Feature", "Active", "Defined", "Implemented", "Tested", "Done %", "Open Risks", "Blocking Findings"]
    f_rows = []
    for fid in feature_ids:
        active = [r for r in requirements if r.feature_id == fid and r.scope_state == "active"]
        tested = sum(1 for r in active if r.lifecycle_state == "tested")
        f_rows.append({
            "Feature": fid,
            "Active": str(len(active)),
            "Defined": str(sum(1 for r in active if r.lifecycle_state in ("defined", "implemented", "tested"))),
            "Implemented": str(sum(1 for r in active if r.lifecycle_state in ("implemented", "tested"))),
            "Tested": str(tested),
            "Done %": f"{100 * tested / len(active):.1f}%" if active else "N/A",
            "Open Risks": str(len(open_risks_by_feature.get(fid, []))),
            # feature_id esplicito sul Finding: chiude P1-21, dove la feature
            # veniva dedotta da uno split del subject e i finding su un Test ID
            # non venivano attribuiti a nessuna feature.
            "Blocking Findings": str(sum(1 for f in blocking if f.feature_id == fid)),
        })

    b_headers = ["Finding ID", "Severity", "Type", "Subject", "Feature", "Description", "First Seen"]
    b_rows = [{
        "Finding ID": f.finding_id, "Severity": f.severity, "Type": f.finding_type,
        "Subject": f.subject, "Feature": _dash(f.feature_id),
        "Description": f.description, "First Seen": f.first_seen,
    } for f in blocking]

    dirty_note = ""
    if manifest.get("worktree_dirty"):
        dirty_note = (
            "\n> ⚠️ Il working tree ha modifiche non committate al momento di questo refresh: "
            "la revisione indicata non descrive esattamente il codice misurato.\n"
        )

    return (
        _frontmatter(
            artifact="governance-dashboard",
            generated_at=manifest.get("scanned_at", ""),
            source_revision=manifest.get("source_revision") or "UNKNOWN",
            worktree_dirty=manifest.get("worktree_dirty", False),
        )
        + "# Governance Dashboard\n\n"
        + GENERATED_BANNER
        + dirty_note
        + "\n## Current Summary\n\n"
        + render_table(["Metric", "Value"], summary, align_right={"Value"})
        + "\n## Burn-up Chart\n\n"
        + _burnup_chart(snapshots)
        + "\n## Snapshot History\n\n"
        + render_table(
            ["Snapshot ID", "Timestamp", "Source Revision", "Reason", "Scope", "Defined", "Implemented", "Tested", "Removed Total"],
            [{
                "Snapshot ID": s.get("snapshot_id", ""), "Timestamp": s.get("timestamp", ""),
                "Source Revision": s.get("source_revision", ""), "Reason": s.get("reason", ""),
                "Scope": str(s.get("scope", 0)), "Defined": str(s.get("defined", 0)),
                "Implemented": str(s.get("implemented", 0)), "Tested": str(s.get("tested", 0)),
                "Removed Total": str(s.get("removed_total", 0)),
            } for s in snapshots],
            align_right={"Scope", "Defined", "Implemented", "Tested", "Removed Total"},
        )
        + "\n## Feature Summary\n\n"
        + (render_table(f_headers, f_rows, align_right={"Active", "Defined", "Implemented", "Tested", "Done %", "Open Risks", "Blocking Findings"}) if f_rows else "_Nessuna feature._\n")
        + "\n## Blocking Findings\n\n"
        + (render_table(b_headers, b_rows) if b_rows else "_Nessun finding bloccante._\n")
    )
