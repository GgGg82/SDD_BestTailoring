"""
CLI dello strumento Requirement Burn-up.

Uso tipico (invocato dal Technical Auditor via Bash):

    python requirement-burnup-tool/engine/cli.py init    --project-root .
    python requirement-burnup-tool/engine/cli.py refresh  --project-root .
    python requirement-burnup-tool/engine/cli.py refresh  --project-root . --force-snapshot
    python requirement-burnup-tool/engine/cli.py status   --project-root .

Confine non negoziabile: questo script scrive SOLO dentro la cartella di
output configurata (default requirement-burnup/). Rifiuta di procedere se
quella cartella coincide con o contiene specs/ o .specify/templates/.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import BurnupConfig, ConfigError, load_config
from engine.dashboard import (
    build_blocking_findings,
    build_coverage_integrity,
    build_current_summary,
    build_feature_summary,
    render_burnup_mermaid,
)
from engine.discovery import SpecsLayoutError, detect_specs_root, discover_features
from engine.md_tables import (
    load_document,
    parse_table,
    render_frontmatter,
    replace_fenced_block,
    replace_table,
)
from engine.requirements import Finding, RequirementRow, extract_requirements, link_code_evidence, link_tasks, reconcile
from engine.risk_link import annotate_matrix_with_risks, read_open_risks
from engine.snapshots import Counts, compute_counts, next_run_id, next_snapshot_id, should_append_snapshot
from engine.status_rules import StatusContext, compute_status
from engine.tests_register import ExecutionRun, TestDefinition, parse_generic_json, parse_junit_xml

MATRIX_HEADERS = [
    "Requirement Key", "Feature", "Requirement ID", "Requirement", "Source",
    "User Story", "Scope", "Lifecycle", "Task IDs", "Code Evidence", "Test IDs",
    "Link State", "Notes",
]
FINDINGS_HEADERS = ["Finding ID", "Severity", "Type", "Requirement/Test/Task", "Description", "Recommended Action"]
TEST_CATALOGUE_HEADERS = [
    "Test ID", "Requirement Keys", "Kind", "Mandatory", "Definition / Expected Result",
    "Location or Command", "Last Run", "Last Result", "Source Revision", "Evidence", "Notes",
]
TEST_HISTORY_HEADERS = ["Run ID", "Timestamp", "Test ID", "Result", "Source Revision", "Duration", "Evidence", "Notes"]
SNAPSHOT_HEADERS = [
    "Snapshot ID", "Timestamp", "Source Revision", "Scope", "Defined",
    "Implemented", "Tested", "Removed Total", "Reason",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_current_revision(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def assert_output_dir_safe(output_dir: Path, specs_root: Path, project_root: Path) -> None:
    forbidden = [specs_root, project_root / ".specify" / "templates", project_root / ".specify" / "memory"]
    for f in forbidden:
        try:
            output_dir.resolve().relative_to(f.resolve())
            raise ConfigError(
                f"output_dir ({output_dir}) ricade dentro un percorso nativo protetto ({f}). "
                "Cambia output_dir in requirement-burnup-config.yml."
            )
        except ValueError:
            continue  # non è un sottopercorso: va bene


def _ensure_output_files(output_dir: Path, templates_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    mapping = {
        "traceability-matrix.md": "traceability-matrix-template.md",
        "test-register.md": "test-register-template.md",
        "governance-dashboard.md": "governance-dashboard-template.md",
    }
    for target_name, template_name in mapping.items():
        target = output_dir / target_name
        if not target.exists():
            template_path = templates_dir / template_name
            target.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")


def _last_counts_from_snapshot_rows(snapshot_rows: list[dict]) -> Counts | None:
    if not snapshot_rows:
        return None
    last = snapshot_rows[-1]
    try:
        return Counts(
            scope=int(last.get("Scope", 0) or 0),
            defined=int(last.get("Defined", 0) or 0),
            implemented=int(last.get("Implemented", 0) or 0),
            tested=int(last.get("Tested", 0) or 0),
            removed_total=int(last.get("Removed Total", 0) or 0),
        )
    except ValueError:
        return None


def _ingest_test_reports(
    config: BurnupConfig, project_root: Path, test_defs_by_id: dict[str, TestDefinition], current_revision: str
) -> tuple[list[ExecutionRun], list[Finding]]:
    from engine.discovery import expand_globs

    explicit_mapping: dict[str, str] = config.raw.get("traceability", {}).get("test_id_mapping", {}) or {}
    new_runs: list[ExecutionRun] = []
    findings: list[Finding] = []
    finding_seq = 1

    def next_id() -> str:
        nonlocal finding_seq
        fid = f"FND-INGEST-{finding_seq:03d}"
        finding_seq += 1
        return fid

    report_files = expand_globs(project_root, config.test_report_globs)
    for report_path in report_files:
        try:
            if report_path.suffix.lower() == ".xml":
                imported = parse_junit_xml(report_path, source_revision=current_revision)
            elif report_path.suffix.lower() == ".json":
                imported = parse_generic_json(report_path, source_revision=current_revision)
            else:
                continue
        except Exception as exc:  # parsing robusto: un report malformato è un Finding, non un crash
            findings.append(
                Finding(
                    finding_id=next_id(), severity="medium", finding_type="unreadable-report",
                    subject=str(report_path), description=f"Impossibile leggere il report: {exc}",
                    recommended_action="Verifica il formato del file o escludilo da test_report_globs.",
                )
            )
            continue

        rel_report_path = report_path.relative_to(project_root) if _is_relative(report_path, project_root) else report_path
        for item in imported:
            item.evidence = str(rel_report_path) + (item.evidence[len(str(report_path)):] if item.evidence.startswith(str(report_path)) else "")
            test_id = explicit_mapping.get(item.test_name_in_report)
            if not test_id:
                for tid in test_defs_by_id:
                    if tid in item.test_name_in_report:
                        test_id = tid
                        break
            if not test_id:
                findings.append(
                    Finding(
                        finding_id=next_id(), severity="low", finding_type="unmatched-test-report",
                        subject=item.test_name_in_report,
                        description=f"Risultato importato da {report_path.name} senza corrispondenza a un Test ID catalogato.",
                        recommended_action="Aggiungi il test al catalogo, o mappalo esplicitamente in traceability.test_id_mapping.",
                    )
                )
                continue

            run = ExecutionRun(
                run_id="",  # assegnato dal chiamante con next_run_id per garantire unicità cronologica
                timestamp=item.timestamp or _now_iso(),
                test_id=test_id,
                result=item.result,
                source_revision=item.source_revision,
                duration=item.duration,
                evidence=item.evidence,
            )
            new_runs.append(run)

            if test_id in test_defs_by_id:
                td = test_defs_by_id[test_id]
                td.last_run = run.timestamp
                td.last_result = run.result
                td.source_revision = run.source_revision
                td.evidence = run.evidence

    return new_runs, findings


def _sync_test_links(rows: list[RequirementRow], test_defs_by_id: dict[str, TestDefinition]) -> None:
    """Popola row.test_ids leggendo la colonna 'Requirement Keys' del Test Register.

    Questo NON è matching semantico: la colonna 'Requirement Keys' del Test
    Register è già di per sé un collegamento esplicito (compilato da un
    umano o da un agente durante la definizione del test), quindi rispecchiarlo
    nella Matrix è una semplice sincronizzazione, non un'inferenza.
    """
    by_req_key: dict[str, list[str]] = {}
    for test_id, td in test_defs_by_id.items():
        for key in [k.strip() for k in td.requirement_keys.split(",") if k.strip()]:
            by_req_key.setdefault(key, []).append(test_id)

    for row in rows:
        linked = by_req_key.get(row.requirement_key, [])
        if not linked:
            continue
        existing_ids = {t.strip().strip("`") for t in row.test_ids.split(",") if t.strip()}
        all_ids = sorted(existing_ids.union(linked))
        row.test_ids = ", ".join(f"`{t}`" for t in all_ids)


def _find_orphan_tests(rows: list[RequirementRow], test_defs: list[TestDefinition]) -> list[Finding]:
    known_keys = {r.requirement_key for r in rows}
    findings = []
    seq = 1
    for t in test_defs:
        linked = [k.strip() for k in t.requirement_keys.split(",") if k.strip()]
        if linked and not any(k in known_keys for k in linked):
            findings.append(
                Finding(
                    finding_id=f"FND-ORPHAN-{seq:03d}", severity="low", finding_type="test-orphan",
                    subject=t.test_id,
                    description="Nessuno dei requisiti collegati a questo test esiste nella Matrix corrente.",
                    recommended_action="Correggi i Requirement Keys del test o verifica se il requisito è stato rinominato.",
                )
            )
            seq += 1
    return findings


def _run_scan(config: BurnupConfig, project_root: Path, templates_dir: Path, force_snapshot: bool) -> dict:
    specs_root = detect_specs_root(project_root)
    assert_output_dir_safe(config.output_dir, specs_root, project_root)
    features = discover_features(specs_root)
    _ensure_output_files(config.output_dir, templates_dir)

    current_revision = get_current_revision(project_root)
    specs_root_label = str(specs_root.relative_to(project_root)) if _is_relative(specs_root, project_root) else str(specs_root)

    # --- 1. carica artefatti esistenti ---
    matrix_path = config.output_dir / "traceability-matrix.md"
    register_path = config.output_dir / "test-register.md"
    dashboard_path = config.output_dir / "governance-dashboard.md"

    matrix_doc = load_document(matrix_path)
    matrix_parsed = parse_table(matrix_doc.body, "Matrix")
    existing_rows = [RequirementRow.from_row_dict(d) for d in (matrix_parsed[1] if matrix_parsed else [])]

    register_doc = load_document(register_path)
    cat_parsed = parse_table(register_doc.body, "Test Catalogue and Latest State")
    test_defs = [TestDefinition.from_row_dict(d) for d in (cat_parsed[1] if cat_parsed else [])]
    test_defs_by_id = {t.test_id: t for t in test_defs if t.test_id}
    hist_parsed = parse_table(register_doc.body, "Execution History")
    existing_history_rows = hist_parsed[1] if hist_parsed else []

    dashboard_doc = load_document(dashboard_path)
    snap_parsed = parse_table(dashboard_doc.body, "Snapshot History")
    existing_snapshot_rows = snap_parsed[1] if snap_parsed else []

    # --- 2. scoperta requisiti, task, evidenza codice ---
    discovered_rows: list[RequirementRow] = []
    task_links_by_feature: dict[str, dict] = {}
    for feat in features:
        discovered_rows.extend(extract_requirements(feat, config.accepted_id_patterns, specs_root_label))
        task_links_by_feature[feat.feature_id] = link_tasks(feat, config.accepted_id_patterns)

    code_evidence = link_code_evidence(project_root, config.source_globs, config.code_evidence_marker_pattern)

    merged_rows, reconcile_findings = reconcile(existing_rows, discovered_rows, task_links_by_feature, code_evidence)

    # --- 3. collegamento a senso unico con risk-register.md ---
    open_risks_by_feature = {feat.feature_id: read_open_risks(feat.directory) for feat in features}
    annotate_matrix_with_risks(merged_rows, open_risks_by_feature)

    # --- 4. ingestione report di test ---
    new_runs, ingestion_findings = _ingest_test_reports(config, project_root, test_defs_by_id, current_revision)
    for run in new_runs:
        run.run_id = next_run_id(existing_history_rows, run.timestamp)
        existing_history_rows = existing_history_rows + [run.to_row_dict()]

    # aggiorna il catalogo test con eventuali nuove definizioni non ancora presenti
    # (referenziate dalla Matrix ma assenti dal Test Register: diventano un Finding, non una riga inventata)
    referenced_test_ids = set()
    for row in merged_rows:
        referenced_test_ids.update(t.strip().strip("`") for t in row.test_ids.split(",") if t.strip())
    unresolved_test_refs = [tid for tid in referenced_test_ids if tid not in test_defs_by_id]
    unresolved_findings = [
        Finding(
            finding_id=f"FND-TESTREF-{i+1:03d}", severity="high", finding_type="unresolved-test-reference",
            subject=tid, description="La Matrix referenzia questo Test ID ma non esiste nel Test Register.",
            recommended_action="Aggiungi la definizione del test al Test Register, o correggi il riferimento in Matrix.",
        )
        for i, tid in enumerate(unresolved_test_refs)
    ]

    # --- 5. calcolo stato ---
    _sync_test_links(merged_rows, test_defs_by_id)
    ctx = StatusContext(freshness_policy=config.freshness_policy, current_source_revision=current_revision)
    merged_rows, status_findings = compute_status(merged_rows, task_links_by_feature, test_defs_by_id, ctx)

    orphan_findings = _find_orphan_tests(merged_rows, list(test_defs_by_id.values()))

    all_findings = reconcile_findings + ingestion_findings + unresolved_findings + status_findings + orphan_findings

    # --- 6. conteggi e snapshot ---
    counts = compute_counts(merged_rows)
    last_counts = _last_counts_from_snapshot_rows(existing_snapshot_rows)
    do_append, reason = should_append_snapshot(
        last_counts, counts, config.append_when_counts_change, config.append_when_scope_changes, force_snapshot
    )
    new_snapshot_rows = existing_snapshot_rows
    if do_append:
        snap_id = next_snapshot_id(existing_snapshot_rows)
        new_snapshot_rows = existing_snapshot_rows + [
            {
                "Snapshot ID": f"`{snap_id}`",
                "Timestamp": _now_iso(),
                "Source Revision": f"`{current_revision or 'UNKNOWN'}`",
                "Scope": str(counts.scope),
                "Defined": str(counts.defined),
                "Implemented": str(counts.implemented),
                "Tested": str(counts.tested),
                "Removed Total": str(counts.removed_total),
                "Reason": reason,
            }
        ]

    # --- 7. scrittura artefatti ---
    _write_matrix(matrix_path, matrix_doc, merged_rows, all_findings, current_revision)
    _write_register(register_path, register_doc, list(test_defs_by_id.values()), existing_history_rows, current_revision)
    _write_dashboard(
        dashboard_path, dashboard_doc, merged_rows, all_findings, counts, new_snapshot_rows,
        open_risks_by_feature, current_revision,
    )

    return {
        "counts": counts, "findings": all_findings, "snapshot_appended": do_append,
        "snapshot_reason": reason, "specs_root": specs_root, "n_features": len(features),
        "output_dir": config.output_dir,
    }


def _is_relative(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _write_matrix(path: Path, doc, rows: list[RequirementRow], findings: list[Finding], revision: str) -> None:
    body = doc.body
    body = replace_table(body, "Matrix", render_table_safe(MATRIX_HEADERS, [r.to_row_dict() for r in rows]))
    body = replace_table(body, "Findings", render_table_safe(FINDINGS_HEADERS, [f.to_row_dict() for f in findings]))
    fm = dict(doc.frontmatter)
    fm["generated_at"] = _now_iso()
    fm["source_revision"] = revision or "UNKNOWN"
    path.write_text(render_frontmatter(fm) + body, encoding="utf-8")


def _write_register(path: Path, doc, test_defs: list[TestDefinition], history_rows: list[dict], revision: str) -> None:
    body = doc.body
    body = replace_table(body, "Test Catalogue and Latest State", render_table_safe(TEST_CATALOGUE_HEADERS, [t.to_row_dict() for t in test_defs]))
    body = replace_table(body, "Execution History", render_table_safe(TEST_HISTORY_HEADERS, history_rows))
    fm = dict(doc.frontmatter)
    fm["generated_at"] = _now_iso()
    fm["source_revision"] = revision or "UNKNOWN"
    path.write_text(render_frontmatter(fm) + body, encoding="utf-8")


def _write_dashboard(
    path: Path, doc, rows: list[RequirementRow], findings: list[Finding], counts: Counts,
    snapshot_rows: list[dict], open_risks_by_feature: dict, revision: str,
) -> None:
    body = doc.body
    cs_headers, cs_rows = build_current_summary(counts)
    body = replace_table(body, "Current Summary", render_table_safe(cs_headers, cs_rows, align_right={"Value"}))

    ci_headers, ci_rows = build_coverage_integrity(rows, findings)
    body = replace_table(body, "Coverage and Integrity", render_table_safe(ci_headers, ci_rows, align_right={"Value"}))

    body = replace_fenced_block(body, "Burn-up Chart", render_burnup_mermaid(snapshot_rows), lang="mermaid")

    body = replace_table(body, "Snapshot History", render_table_safe(SNAPSHOT_HEADERS, snapshot_rows, align_right={"Scope", "Defined", "Implemented", "Tested", "Removed Total"}))

    fs_headers, fs_rows = build_feature_summary(rows, findings, open_risks_by_feature)
    body = replace_table(body, "Feature Summary", render_table_safe(fs_headers, fs_rows, align_right={"Active Requirements", "Defined", "Implemented", "Tested / Done", "Done %", "Open Risks", "Findings"}))

    bf_headers, bf_rows = build_blocking_findings(findings)
    body = replace_table(body, "Blocking Findings", render_table_safe(bf_headers, bf_rows))

    fm = dict(doc.frontmatter)
    fm["generated_at"] = _now_iso()
    fm["source_revision"] = revision or "UNKNOWN"
    path.write_text(render_frontmatter(fm) + body, encoding="utf-8")


def render_table_safe(headers: list[str], rows: list[dict], align_right: set[str] | None = None) -> str:
    from engine.md_tables import render_table
    return render_table(headers, rows, align_right_cols=align_right)


def cmd_init(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config) if args.config else project_root / "requirement-burnup-config.yml"
    templates_dir = Path(__file__).resolve().parent.parent / "templates"

    try:
        config = load_config(config_path, project_root)
        result = _run_scan(config, project_root, templates_dir, force_snapshot=False)
    except (ConfigError, SpecsLayoutError) as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1

    c = result["counts"]
    print("Inizializzazione completata.")
    print(f"Layout Spec Kit rilevato: {result['specs_root']}")
    print(f"Feature scoperte: {result['n_features']}")
    print(f"Scope attivo: {c.scope} | Defined: {c.defined} | Implemented: {c.implemented} | Tested/Done: {c.tested}")
    print(f"Snapshot iniziale creato: {result['snapshot_appended']} (motivo: {result['snapshot_reason']})")
    print(f"Findings totali: {len(result['findings'])}")
    print(f"File scritti in: {result['output_dir']}")
    print("Nessun file nativo di Spec Kit è stato modificato.")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config) if args.config else project_root / "requirement-burnup-config.yml"
    templates_dir = Path(__file__).resolve().parent.parent / "templates"

    try:
        config = load_config(config_path, project_root)
        result = _run_scan(config, project_root, templates_dir, force_snapshot=args.force_snapshot)
    except (ConfigError, SpecsLayoutError) as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1

    c = result["counts"]
    print("Refresh completato.")
    print(f"Scope attivo: {c.scope} | Defined: {c.defined} | Implemented: {c.implemented} | Tested/Done: {c.tested}")
    print(f"Snapshot aggiunto: {result['snapshot_appended']} (motivo: {result['snapshot_reason']})")
    high = [f for f in result["findings"] if f.severity == "high"]
    print(f"Findings totali: {len(result['findings'])} (di cui {len(high)} 'high')")
    for f in high:
        print(f"  [{f.finding_id}] {f.finding_type} — {f.subject}: {f.description}")
    print("Nessun file nativo di Spec Kit è stato modificato.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config) if args.config else project_root / "requirement-burnup-config.yml"

    try:
        config = load_config(config_path, project_root)
    except ConfigError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1

    matrix_path = config.output_dir / "traceability-matrix.md"
    register_path = config.output_dir / "test-register.md"
    dashboard_path = config.output_dir / "governance-dashboard.md"

    if not (matrix_path.exists() and register_path.exists() and dashboard_path.exists()):
        print(
            "Artefatti mancanti o incompleti in " + str(config.output_dir) + ". "
            "Esegui prima 'init'.",
            file=sys.stderr,
        )
        return 1

    matrix_doc = load_document(matrix_path)
    matrix_parsed = parse_table(matrix_doc.body, "Matrix")
    rows = [RequirementRow.from_row_dict(d) for d in (matrix_parsed[1] if matrix_parsed else [])]
    findings_parsed = parse_table(matrix_doc.body, "Findings")
    findings_rows = findings_parsed[1] if findings_parsed else []

    dashboard_doc = load_document(dashboard_path)
    snap_parsed = parse_table(dashboard_doc.body, "Snapshot History")
    snapshot_rows = snap_parsed[1] if snap_parsed else []

    counts = compute_counts(rows)
    from engine.snapshots import tested_percent
    print(f"Active scope: {counts.scope}")
    print(f"Defined: {counts.defined}")
    print(f"Implemented: {counts.implemented}")
    print(f"Tested/Done: {counts.tested} ({tested_percent(counts)})")
    proposed = sum(1 for r in rows if r.scope_state == "active" and r.link_state == "proposed")
    incomplete = sum(1 for r in rows if r.scope_state == "active" and r.link_state == "incomplete")
    print(f"Link proposed: {proposed} | Link incomplete: {incomplete}")
    print(f"Findings registrati in Matrix: {len(findings_rows)}")
    if snapshot_rows:
        last = snapshot_rows[-1]
        print(f"Ultimo snapshot: {last.get('Timestamp')} (revisione {last.get('Source Revision')})")
    else:
        print("Nessuno snapshot ancora registrato.")
    print("(Nessun file è stato modificato: 'status' è sola lettura.)")
    return 0


def main() -> int:
    # Parser "genitore" con le opzioni comuni, condiviso da ogni sottocomando:
    # così --project-root/--config funzionano sia prima che dopo init/refresh/status.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--project-root", default=".", help="Radice del progetto Spec Kit (default: directory corrente)")
    common.add_argument("--config", default=None, help="Percorso di requirement-burnup-config.yml (default: <project-root>/requirement-burnup-config.yml)")

    parser = argparse.ArgumentParser(prog="requirement-burnup", description="Strumento Requirement Burn-up per Spec Kit", parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Inizializza gli artefatti e fai la prima scansione", parents=[common])

    p_refresh = sub.add_parser("refresh", help="Aggiorna tracciabilità, test e stato", parents=[common])
    p_refresh.add_argument("--force-snapshot", action="store_true", help="Forza uno snapshot anche a conteggi invariati")

    sub.add_parser("status", help="Mostra lo stato corrente (sola lettura)", parents=[common])

    args = parser.parse_args()
    if args.command == "init":
        return cmd_init(args)
    if args.command == "refresh":
        return cmd_refresh(args)
    if args.command == "status":
        return cmd_status(args)
    parser.error("comando sconosciuto")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
