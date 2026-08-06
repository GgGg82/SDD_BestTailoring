"""
Test Register: catalogo dei test, ultimo stato, storico esecuzioni append-only.

Adapter di importazione (da TEST-REGISTER-SPEC.md): JUnit XML e un formato
JSON generico. Un'esecuzione viene collegata a un Test ID SOLO se il nome/ID
del test nel report combacia esplicitamente con un Test ID già catalogato
(o con una mappatura esplicita in configurazione) — mai per somiglianza.
Se un risultato importato non trova corrispondenza, diventa un Finding,
non un collegamento indovinato.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

RESULT_VALUES = ("not-run", "pass", "fail", "blocked", "error")


@dataclass
class TestDefinition:
    test_id: str
    requirement_keys: str  # "001-example/FR-001, 001-example/FR-002"
    kind: str
    mandatory: str  # "yes" | "no"
    definition: str
    location_or_command: str
    last_run: str = ""
    last_result: str = "not-run"
    source_revision: str = ""
    evidence: str = ""
    notes: str = ""

    def to_row_dict(self) -> dict:
        return {
            "Test ID": f"`{self.test_id}`",
            "Requirement Keys": ", ".join(f"`{k.strip()}`" for k in self.requirement_keys.split(",") if k.strip()),
            "Kind": f"`{self.kind}`",
            "Mandatory": f"`{self.mandatory}`",
            "Definition / Expected Result": self.definition,
            "Location or Command": f"`{self.location_or_command}`",
            "Last Run": self.last_run or "—",
            "Last Result": f"`{self.last_result}`",
            "Source Revision": f"`{self.source_revision}`" if self.source_revision else "—",
            "Evidence": f"`{self.evidence}`" if self.evidence else "—",
            "Notes": self.notes or "",
        }

    @staticmethod
    def from_row_dict(d: dict) -> "TestDefinition":
        def unbacktick(v: str) -> str:
            v = (v or "").strip()
            if v.startswith("`") and v.endswith("`"):
                return v[1:-1]
            return "" if v == "—" else v

        req_keys_raw = d.get("Requirement Keys", "")
        req_keys = ", ".join(unbacktick(x) for x in req_keys_raw.split(",") if x.strip())

        return TestDefinition(
            test_id=unbacktick(d.get("Test ID", "")),
            requirement_keys=req_keys,
            kind=unbacktick(d.get("Kind", "")),
            mandatory=unbacktick(d.get("Mandatory", "no")) or "no",
            definition=d.get("Definition / Expected Result", "") or "",
            location_or_command=unbacktick(d.get("Location or Command", "")),
            last_run=unbacktick(d.get("Last Run", "")),
            last_result=unbacktick(d.get("Last Result", "")) or "not-run",
            source_revision=unbacktick(d.get("Source Revision", "")),
            evidence=unbacktick(d.get("Evidence", "")),
            notes=d.get("Notes", "") or "",
        )


@dataclass
class ExecutionRun:
    run_id: str
    timestamp: str
    test_id: str
    result: str
    source_revision: str = ""
    duration: str = ""
    evidence: str = ""
    notes: str = ""

    def to_row_dict(self) -> dict:
        return {
            "Run ID": f"`{self.run_id}`",
            "Timestamp": self.timestamp,
            "Test ID": f"`{self.test_id}`",
            "Result": f"`{self.result}`",
            "Source Revision": f"`{self.source_revision}`" if self.source_revision else "—",
            "Duration": self.duration or "—",
            "Evidence": f"`{self.evidence}`" if self.evidence else "—",
            "Notes": self.notes or "",
        }

    @staticmethod
    def from_row_dict(d: dict) -> "ExecutionRun":
        def unbacktick(v: str) -> str:
            v = (v or "").strip()
            if v.startswith("`") and v.endswith("`"):
                return v[1:-1]
            return "" if v == "—" else v

        return ExecutionRun(
            run_id=unbacktick(d.get("Run ID", "")),
            timestamp=d.get("Timestamp", "") or "",
            test_id=unbacktick(d.get("Test ID", "")),
            result=unbacktick(d.get("Result", "")),
            source_revision=unbacktick(d.get("Source Revision", "")),
            duration=unbacktick(d.get("Duration", "")),
            evidence=unbacktick(d.get("Evidence", "")),
            notes=d.get("Notes", "") or "",
        )


@dataclass
class ImportedResult:
    test_name_in_report: str
    result: str
    timestamp: str
    source_revision: str
    duration: str
    evidence: str


def parse_junit_xml(report_path: Path, source_revision: str = "") -> list[ImportedResult]:
    """Adapter JUnit XML. Assume lo schema standard <testsuite><testcase .../></testsuite>
    (o <testsuites> con più <testsuite>). Il nome usato per il matching è
    'classname.name' se classname è presente, altrimenti solo 'name' —
    il matching col Test ID catalogato avviene altrove (vedi cli.py),
    tramite mappatura esplicita in configurazione o corrispondenza letterale
    del Test ID dentro il nome stesso.
    """
    tree = ET.parse(report_path)
    root = tree.getroot()
    testcases = root.findall(".//testcase")
    results: list[ImportedResult] = []
    mtime = report_path.stat().st_mtime
    from datetime import datetime, timezone
    default_ts = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for tc in testcases:
        name = tc.get("name", "")
        classname = tc.get("classname", "")
        full_name = f"{classname}.{name}" if classname else name
        duration = tc.get("time", "")

        failure = tc.find("failure")
        error = tc.find("error")
        skipped = tc.find("skipped")
        if error is not None:
            result = "error"
        elif failure is not None:
            result = "fail"
        elif skipped is not None:
            result = "blocked"
        else:
            result = "pass"

        results.append(
            ImportedResult(
                test_name_in_report=full_name,
                result=result,
                timestamp=default_ts,
                source_revision=source_revision,
                duration=f"{duration}s" if duration else "",
                evidence=str(report_path),
            )
        )
    return results


def parse_generic_json(report_path: Path, source_revision: str = "") -> list[ImportedResult]:
    """Adapter JSON generico. Formato atteso (documentato in TEST-REGISTER-SPEC.md):

    [
      {"id": "TEST-001", "result": "pass", "timestamp": "...", "duration": "1.2s"},
      ...
    ]

    'result' deve essere uno tra: not-run, pass, fail, blocked, error.
    Righe con un valore di 'result' non riconosciuto diventano 'error' più
    una nota esplicita, non vengono scartate silenziosamente.
    """
    data = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{report_path}: atteso un array JSON al livello radice.")

    results: list[ImportedResult] = []
    for entry in data:
        result = entry.get("result", "error")
        note = ""
        if result not in RESULT_VALUES:
            note = f" [risultato non riconosciuto nel report originale: '{result}']"
            result = "error"
        results.append(
            ImportedResult(
                test_name_in_report=str(entry.get("id") or entry.get("name") or ""),
                result=result,
                timestamp=entry.get("timestamp", ""),
                source_revision=entry.get("source_revision", source_revision),
                duration=str(entry.get("duration", "")),
                evidence=str(report_path) + note,
            )
        )
    return results
