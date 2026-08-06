"""
Generazione del Governance Dashboard.

Regola da ARCHITECTURE.md del pacchetto originale: la dashboard è una
PROIEZIONE generata da Matrix + Test Register + storico snapshot. Non è mai
una fonte di verità indipendente — ogni sua rigenerazione riscrive
interamente le sezioni "correnti", ma non tocca mai righe storiche esistenti
nello Snapshot History o nell'Execution History.
"""
from __future__ import annotations

from collections import defaultdict

from .md_tables import parse_table, render_table
from .requirements import Finding, RequirementRow
from .risk_link import OpenRisk
from .snapshots import Counts, tested_percent
from .tests_register import TestDefinition


def build_current_summary(counts: Counts) -> tuple[list[str], list[dict]]:
    headers = ["Metric", "Value"]
    rows = [
        {"Metric": "Active scope", "Value": str(counts.scope)},
        {"Metric": "Defined", "Value": str(counts.defined)},
        {"Metric": "Implemented", "Value": str(counts.implemented)},
        {"Metric": "Tested / Done", "Value": str(counts.tested)},
        {"Metric": "Tested / Done %", "Value": tested_percent(counts)},
        {"Metric": "Removed requirements retained", "Value": str(counts.removed_total)},
    ]
    return headers, rows


def build_coverage_integrity(rows: list[RequirementRow], findings: list[Finding]) -> tuple[list[str], list[dict]]:
    active = [r for r in rows if r.scope_state == "active"]
    without_code_evidence = sum(1 for r in active if not r.code_evidence)
    without_mandatory_test = sum(
        1 for f in findings if f.finding_type == "missing-mandatory-test"
    )
    failing_mandatory = sum(1 for f in findings if f.finding_type == "failing-mandatory-test")
    stale_evidence = sum(1 for f in findings if f.finding_type == "stale-evidence")
    proposed_only = sum(1 for r in active if r.link_state == "proposed")
    orphan_tests = sum(1 for f in findings if f.finding_type == "test-orphan")

    headers = ["Metric", "Value"]
    table_rows = [
        {"Metric": "Requirements without confirmed code evidence", "Value": str(without_code_evidence)},
        {"Metric": "Requirements without mandatory tests", "Value": str(without_mandatory_test)},
        {"Metric": "Requirements with failing mandatory tests", "Value": str(failing_mandatory)},
        {"Metric": "Requirements with stale test evidence", "Value": str(stale_evidence)},
        {"Metric": "Proposed-only links", "Value": str(proposed_only)},
        {"Metric": "Orphan tests", "Value": str(orphan_tests)},
    ]
    return headers, table_rows


def build_feature_summary(
    rows: list[RequirementRow],
    findings: list[Finding],
    open_risks_by_feature: dict[str, list[OpenRisk]],
) -> tuple[list[str], list[dict]]:
    by_feature: dict[str, list[RequirementRow]] = defaultdict(list)
    for r in rows:
        if r.scope_state == "active":
            by_feature[r.feature].append(r)

    findings_count_by_feature: dict[str, int] = defaultdict(int)
    for f in findings:
        feature_guess = f.subject.split("/")[0] if "/" in f.subject else f.subject
        findings_count_by_feature[feature_guess] += 1

    headers = ["Feature", "Active Requirements", "Defined", "Implemented", "Tested / Done", "Done %", "Open Risks", "Findings"]
    table_rows = []
    for feature, freqs in sorted(by_feature.items()):
        defined = sum(1 for r in freqs if r.lifecycle_state in ("defined", "implemented", "tested"))
        implemented = sum(1 for r in freqs if r.lifecycle_state in ("implemented", "tested"))
        tested = sum(1 for r in freqs if r.lifecycle_state == "tested")
        done_pct = f"{100 * tested / len(freqs):.1f}%" if freqs else "N/A"
        open_risks = len(open_risks_by_feature.get(feature, []))
        table_rows.append(
            {
                "Feature": f"`{feature}`",
                "Active Requirements": str(len(freqs)),
                "Defined": str(defined),
                "Implemented": str(implemented),
                "Tested / Done": str(tested),
                "Done %": done_pct,
                "Open Risks": str(open_risks),
                "Findings": str(findings_count_by_feature.get(feature, 0)),
            }
        )
    return headers, table_rows


def build_blocking_findings(findings: list[Finding]) -> tuple[list[str], list[dict]]:
    headers = ["Finding ID", "Severity", "Description", "Affected Items", "Recommended Action"]
    table_rows = []
    for f in findings:
        if f.severity != "high":
            continue
        table_rows.append(
            {
                "Finding ID": f"`{f.finding_id}`",
                "Severity": f.severity,
                "Description": f.description,
                "Affected Items": f"`{f.subject}`",
                "Recommended Action": f.recommended_action,
            }
        )
    return headers, table_rows


def render_burnup_mermaid(snapshot_rows: list[dict]) -> str:
    """Genera il blocco mermaid xychart-beta dallo Snapshot History reale.
    L'asse X usa le date vere dei timestamp degli snapshot, non etichette progressive finte."""
    if not snapshot_rows:
        return (
            "```mermaid\n"
            "xychart-beta\n"
            '    title "Requirement Burn-up"\n'
            '    x-axis ["Nessuno snapshot ancora"]\n'
            '    y-axis "Requirements" 0 --> 1\n'
            "    line [0]\n"
            "    line [0]\n"
            "    line [0]\n"
            "    line [0]\n"
            "```\n"
        )

    def unbacktick(v: str) -> str:
        v = (v or "").strip()
        return v[1:-1] if v.startswith("`") and v.endswith("`") else v

    labels = []
    scope_s, defined_s, impl_s, tested_s = [], [], [], []
    max_scope = 1
    for row in snapshot_rows:
        ts = (row.get("Timestamp", "") or "").split("T")[0]
        labels.append(f'"{ts}"')
        scope_v = int(row.get("Scope", 0) or 0)
        defined_v = int(row.get("Defined", 0) or 0)
        impl_v = int(row.get("Implemented", 0) or 0)
        tested_v = int(row.get("Tested", 0) or 0)
        scope_s.append(str(scope_v))
        defined_s.append(str(defined_v))
        impl_s.append(str(impl_v))
        tested_s.append(str(tested_v))
        max_scope = max(max_scope, scope_v)

    return (
        "```mermaid\n"
        "xychart-beta\n"
        '    title "Requirement Burn-up"\n'
        f"    x-axis [{', '.join(labels)}]\n"
        f'    y-axis "Requirements" 0 --> {max_scope}\n'
        f"    line [{', '.join(scope_s)}]\n"
        f"    line [{', '.join(defined_s)}]\n"
        f"    line [{', '.join(impl_s)}]\n"
        f"    line [{', '.join(tested_s)}]\n"
        "```\n"
    )
