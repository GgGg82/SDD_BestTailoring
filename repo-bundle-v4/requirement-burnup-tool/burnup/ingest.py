"""Ingestione idempotente dei report di test.

Chiude P0-07, P0-08, P1-12 e P1-17 dell'audit.

Difetti della v3 riprodotti in fase di analisi, tutti presenti insieme:

1. lo stesso report JUnit veniva reimportato ad ogni refresh — tre refresh
   producevano tre righe identiche nella Execution History;
2. il matching era `if test_id in nome_nel_report`, quindi `TEST-1` catturava
   il risultato di `suite.TEST-10_login`;
3. lo stato "corrente" era l'ultimo record processato nell'ordine di
   iterazione dei file, non quello con timestamp piu' recente: un report
   vecchio elaborato dopo uno nuovo sovrascriveva un pass recente;
4. al report veniva assegnato l'HEAD **del momento del refresh**, quindi un
   test eseguito settimane prima risultava girato sulla revisione corrente.

Il punto 4 e' quello che invalida il concetto stesso di verifica: rende la
policy `current-revision` una tautologia sempre vera.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import BurnupConfig
from .fingerprint import file_fingerprint
from .ids import now_iso, run_id, run_identity
from .models import RESULT_VALUES, TestRun
from .paths import expand_globs, relative_label

ADAPTER_VERSION = "2.0"


@dataclass
class ImportedResult:
    test_name: str
    result: str
    executed_at: str
    source_revision: str
    revision_origin: str
    duration: str


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_timestamp(raw: str) -> str:
    """Normalizza un timestamp a UTC ISO-8601, o stringa vuota se illeggibile.

    Deliberatamente NON ripiega sull'ora corrente: un timestamp inventato e'
    peggio di un timestamp assente, perche' fa sembrare fresca un'esecuzione
    di cui non si sa nulla.
    """
    if not raw:
        return ""
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sidecar_metadata(report_path: Path) -> dict:
    """Legge `<report>.meta.json`, prodotto dalla pipeline che ha eseguito i test.

    E' il canale con cui una revisione *reale* entra nel sistema. Senza
    sidecar e senza campo nel report, la revisione resta sconosciuta e la
    policy `current-revision` non puo' essere soddisfatta — che e' il
    comportamento corretto, non una limitazione.
    """
    for candidate in (
        report_path.with_suffix(report_path.suffix + ".meta.json"),
        report_path.with_suffix(".meta.json"),
    ):
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except (OSError, json.JSONDecodeError):
                return {}
    return {}


def parse_junit(report_path: Path, sidecar: dict) -> list[ImportedResult]:
    tree = ET.parse(report_path)
    root = tree.getroot()

    root_ts = _normalize_timestamp(root.get("timestamp", ""))
    sidecar_ts = _normalize_timestamp(str(sidecar.get("executed_at", "")))
    revision = str(sidecar.get("source_revision", "") or root.get("source_revision", "") or "")
    origin = "sidecar" if sidecar.get("source_revision") else ("report" if root.get("source_revision") else "unknown")

    # C-07: l'ora va cercata anche sul <testsuite> che contiene il testcase, non
    # solo sulla radice.
    #
    # TEST-REGISTER-SPEC prescrive l'ordine "testcase@timestamp ->
    # testsuite@timestamp -> sidecar", ma il codice leggeva `root.get(...)`.
    # Funzionava solo quando la radice era gia' un <testsuite>. Nella forma piu'
    # diffusa — <testsuites> che avvolge uno o piu' <testsuite>, quella che
    # producono pytest e la maggior parte dei CI — il timestamp sta sul figlio e
    # veniva ignorato: nessun risultato aveva un'ora, quindi tutti venivano
    # scartati e nessun report era importabile senza sidecar.
    suites = root.findall(".//testsuite")
    if root.tag == "testsuite":
        suites = [root, *suites]

    scoped: list[tuple[ET.Element, str, str]] = []
    seen: set[int] = set()
    for suite in suites:
        suite_ts = _normalize_timestamp(suite.get("timestamp", "")) or root_ts
        suite_rev = str(suite.get("source_revision", "") or "")
        for tc in suite.findall(".//testcase"):
            if id(tc) in seen:
                continue
            seen.add(id(tc))
            scoped.append((tc, suite_ts, suite_rev))
    for tc in root.findall(".//testcase"):
        if id(tc) not in seen:
            seen.add(id(tc))
            scoped.append((tc, root_ts, ""))

    results: list[ImportedResult] = []
    for tc, suite_ts, suite_rev in scoped:
        name = tc.get("name", "")
        classname = tc.get("classname", "")
        full = f"{classname}.{name}" if classname else name

        if tc.find("error") is not None:
            result = "error"
        elif tc.find("failure") is not None:
            result = "fail"
        elif tc.find("skipped") is not None:
            result = "blocked"
        else:
            result = "pass"

        # Il mtime del file NON e' un fallback accettabile per l'ora di
        # esecuzione: la v3 lo usava, e basta un `touch` o un checkout per
        # ringiovanire un report vecchio.
        executed_at = _normalize_timestamp(tc.get("timestamp", "")) or suite_ts or sidecar_ts
        case_revision = revision or suite_rev

        results.append(
            ImportedResult(
                test_name=full,
                result=result,
                executed_at=executed_at,
                source_revision=case_revision,
                revision_origin=(origin if revision else ("report" if suite_rev else "unknown")),
                duration=f"{tc.get('time')}s" if tc.get("time") else "",
            )
        )
    return results


def parse_generic_json(report_path: Path, sidecar: dict) -> list[ImportedResult]:
    with open(report_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("atteso un array JSON al livello radice")

    sidecar_rev = str(sidecar.get("source_revision", "") or "")
    sidecar_ts = _normalize_timestamp(str(sidecar.get("executed_at", "")))

    results: list[ImportedResult] = []
    for entry in data:
        if not isinstance(entry, dict):
            raise ValueError("ogni elemento dell'array deve essere un oggetto")
        result = entry.get("result", "error")
        if result not in RESULT_VALUES:
            result = "error"
        revision = str(entry.get("source_revision", "") or sidecar_rev)
        results.append(
            ImportedResult(
                test_name=str(entry.get("id") or entry.get("name") or ""),
                result=result,
                executed_at=_normalize_timestamp(str(entry.get("timestamp", ""))) or sidecar_ts,
                source_revision=revision,
                revision_origin=("report" if entry.get("source_revision") else ("sidecar" if sidecar_rev else "unknown")),
                duration=str(entry.get("duration", "")),
            )
        )
    return results


def resolve_test_id(report_name: str, known_ids: set[str], mapping: dict[str, str]) -> str | None:
    """Risolve il nome nel report verso un Test ID catalogato.

    Chiude il difetto di matching di P0-07. Ordine:
      1. mappatura esplicita in configurazione — sempre prioritaria;
      2. corrispondenza esatta;
      3. corrispondenza su token delimitati.

    Il passo 3 e' il sostituto sicuro del `in` della v3: `TEST-1` non combacia
    con `TEST-10` perche' `0` e' un carattere di token, quindi il confine non
    e' rispettato. Se piu' Test ID combaciano, si rifiuta invece di scegliere
    il primo: un'attribuzione ambigua e' peggio di nessuna attribuzione.
    """
    if report_name in mapping:
        return mapping[report_name]
    if report_name in known_ids:
        return report_name

    def token_chars(s: str, i: int) -> bool:
        # Solo gli alfanumerici continuano il token. `_`, `.`, `-`, `::` sono
        # separatori nei nomi dei test (`suite.TEST-10_login`), quindi non
        # devono impedire il riconoscimento. Il caso che conta e' TEST-1
        # seguito da `0`: li' il confine e' violato e la corrispondenza va
        # respinta, ed e' esattamente il difetto P0-07 della v3.
        return 0 <= i < len(s) and s[i].isalnum()

    matches: list[str] = []
    for tid in known_ids:
        start = 0
        while True:
            pos = report_name.find(tid, start)
            if pos < 0:
                break
            if not token_chars(report_name, pos - 1) and not token_chars(report_name, pos + len(tid)):
                matches.append(tid)
                break
            start = pos + 1

    if len(matches) == 1:
        return matches[0]
    return None


@dataclass
class IngestOutcome:
    new_runs: list[TestRun]
    skipped_duplicates: int
    anomalies: list[tuple[str, str]]


def ingest_reports(
    config: BurnupConfig,
    project_root: Path,
    known_test_ids: set[str],
    existing_identities: set[str],
    worktree_dirty: bool,
) -> IngestOutcome:
    """Importa i report producendo SOLO le run non gia' presenti.

    L'idempotenza e' garantita da `run_identity`, che dipende dall'hash dei
    byte del report e non dal suo percorso: rinominare o spostare un report
    non lo fa reimportare, e sovrascriverlo con contenuto diverso lo fa
    correttamente entrare come esecuzione nuova.
    """
    new_runs: list[TestRun] = []
    anomalies: list[tuple[str, str]] = []
    duplicates = 0
    imported_at = now_iso()

    reports = expand_globs(
        project_root,
        config.test_report_globs,
        field="inputs.test_report_globs",
        extra_excludes=config.extra_excludes,
    )

    for report_path in reports:
        rel = relative_label(report_path, project_root)
        suffix = report_path.suffix.lower()
        if suffix not in (".xml", ".json"):
            continue
        if rel.endswith(".meta.json"):
            continue  # e' il sidecar di un altro report, non un report

        sidecar = _sidecar_metadata(report_path)
        adapter = "junit-xml" if suffix == ".xml" else "generic-json"

        try:
            report_hash = file_fingerprint(report_path)
            imported = parse_junit(report_path, sidecar) if suffix == ".xml" else parse_generic_json(report_path, sidecar)
        except Exception as exc:  # un report malformato e' un rilievo, non un crash
            anomalies.append(("unreadable-report", f"{rel}: {exc}"))
            continue

        for item in imported:
            if not item.test_name:
                anomalies.append(("unnamed-test-result", f"{rel}: risultato senza nome, ignorato."))
                continue

            test_id = resolve_test_id(item.test_name, known_test_ids, config.test_id_mapping)
            if test_id is None:
                anomalies.append((
                    "unmatched-test-report",
                    f"{rel}: '{item.test_name}' non corrisponde a nessun Test ID catalogato in modo univoco.",
                ))
                continue

            if not item.executed_at:
                anomalies.append((
                    "missing-execution-timestamp",
                    f"{rel}: '{item.test_name}' non riporta un'ora di esecuzione: "
                    "impossibile stabilire quale sia il risultato piu' recente.",
                ))
                continue

            identity = run_identity(
                report_hash=report_hash,
                adapter=adapter,
                test_id=test_id,
                executed_at=item.executed_at,
                result=item.result,
            )
            if identity in existing_identities:
                duplicates += 1
                continue
            existing_identities.add(identity)

            new_runs.append(
                TestRun(
                    run_id=run_id(),
                    run_identity=identity,
                    test_id=test_id,
                    result=item.result,
                    executed_at=item.executed_at,
                    source_revision=item.source_revision,
                    revision_origin=item.revision_origin,
                    duration=item.duration,
                    evidence_path=rel,
                    evidence_hash=report_hash,
                    adapter=adapter,
                    adapter_version=ADAPTER_VERSION,
                    imported_at=imported_at,
                    worktree_dirty=worktree_dirty,
                )
            )

    return IngestOutcome(new_runs=new_runs, skipped_duplicates=duplicates, anomalies=anomalies)


def latest_run_by_test(runs: list[TestRun]) -> dict[str, TestRun]:
    """Ultima esecuzione per ogni test, per ORA DI ESECUZIONE.

    Chiude il punto 3 di P0-07: nella v3 vinceva l'ultimo record processato,
    quindi l'ordine dei file sul filesystem determinava lo stato. Qui il
    criterio e' il timestamp, con `run_id` (ULID, monotono) come tie-breaker
    deterministico: mescolare l'ordine di ingresso non cambia il risultato.
    """
    latest: dict[str, TestRun] = {}
    for run in runs:
        current = latest.get(run.test_id)
        if current is None or (run.executed_at, run.run_id) > (current.executed_at, current.run_id):
            latest[run.test_id] = run
    return latest
