"""
Estrazione dei requisiti da spec.md, collegamento deterministico a task/codice,
e riconciliazione con la Traceability Matrix già esistente.

Principio fondamentale (da TRACEABILITY-RULES.md e DESIGN-DECISIONS D-010):
questo modulo NON fa mai matching semantico. Un link diventa 'confirmed' solo
se c'è un riferimento esplicito e letterale (ID del requisito nel testo del
task, marcatore esplicito nel codice, o link già confermato in precedenza e
qui semplicemente preservato). Qualunque cosa richieda giudizio — inclusa la
proposta di un collegamento plausibile ma non esplicito — resta fuori da
questo script: la fa il Technical Auditor (agente) durante il refresh,
mai lo script da solo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .discovery import Feature, expand_globs

LIFECYCLE_STATES = ("defined", "implemented", "tested")
SCOPE_STATES = ("active", "removed")
LINK_STATES = ("confirmed", "proposed", "incomplete")


@dataclass
class RequirementRow:
    requirement_key: str
    feature: str
    requirement_id: str
    requirement_text: str
    source: str
    user_story: str = ""
    scope_state: str = "active"
    lifecycle_state: str = "defined"
    task_ids: str = ""       # stringa "T010, T014" per compatibilità con la tabella Markdown
    code_evidence: str = ""
    test_ids: str = ""
    link_state: str = "incomplete"
    notes: str = ""

    def to_row_dict(self) -> dict:
        return {
            "Requirement Key": f"`{self.requirement_key}`",
            "Feature": f"`{self.feature}`",
            "Requirement ID": f"`{self.requirement_id}`",
            "Requirement": self.requirement_text,
            "Source": f"`{self.source}`",
            "User Story": f"`{self.user_story}`" if self.user_story else "—",
            "Scope": f"`{self.scope_state}`",
            "Lifecycle": f"`{self.lifecycle_state}`",
            "Task IDs": self.task_ids or "—",
            "Code Evidence": self.code_evidence or "—",
            "Test IDs": self.test_ids or "—",
            "Link State": f"`{self.link_state}`",
            "Notes": self.notes or "",
        }

    @staticmethod
    def from_row_dict(d: dict) -> "RequirementRow":
        def unbacktick(v: str) -> str:
            v = (v or "").strip()
            if v.startswith("`") and v.endswith("`") and len(v) >= 2:
                return v[1:-1]
            return "" if v == "—" else v

        return RequirementRow(
            requirement_key=unbacktick(d.get("Requirement Key", "")),
            feature=unbacktick(d.get("Feature", "")),
            requirement_id=unbacktick(d.get("Requirement ID", "")),
            requirement_text=d.get("Requirement", "") or "",
            source=unbacktick(d.get("Source", "")),
            user_story=unbacktick(d.get("User Story", "")),
            scope_state=unbacktick(d.get("Scope", "")) or "active",
            lifecycle_state=unbacktick(d.get("Lifecycle", "")) or "defined",
            task_ids="" if d.get("Task IDs", "—") == "—" else d.get("Task IDs", ""),
            code_evidence="" if d.get("Code Evidence", "—") == "—" else d.get("Code Evidence", ""),
            test_ids="" if d.get("Test IDs", "—") == "—" else d.get("Test IDs", ""),
            link_state=unbacktick(d.get("Link State", "")) or "incomplete",
            notes=d.get("Notes", "") or "",
        )


@dataclass
class Finding:
    finding_id: str
    severity: str  # low | medium | high
    finding_type: str
    subject: str
    description: str
    recommended_action: str

    def to_row_dict(self) -> dict:
        return {
            "Finding ID": f"`{self.finding_id}`",
            "Severity": self.severity,
            "Type": self.finding_type,
            "Requirement/Test/Task": f"`{self.subject}`",
            "Description": self.description,
            "Recommended Action": self.recommended_action,
        }


def _build_id_regex(accepted_id_patterns: list[str]) -> re.Pattern:
    alt = "|".join(f"(?:{p})" for p in accepted_id_patterns)
    return re.compile(alt)


def extract_requirements(feature: Feature, accepted_id_patterns: list[str], specs_root_label: str) -> list[RequirementRow]:
    """Estrae i requisiti da spec.md di una feature.

    Riconosce righe del tipo:
        - **FR-001**: testo del requisito
        - FR-001: testo del requisito
        - **FR-001** (US1): testo del requisito
    L'associazione a una user story è 'strutturale' (confirmed) solo se il
    requisito appare nel corpo testuale sotto un'intestazione tipo
    '### User Story 1' / '## US1' che lo precede senza un'altra intestazione
    di pari o superiore livello nel mezzo, oppure se il tag (USx) è esplicito
    sulla stessa riga.
    """
    id_regex = _build_id_regex(accepted_id_patterns)
    text = feature.spec_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    current_user_story = ""
    us_heading_re = re.compile(r"^#{1,6}\s*(User Story\s*(\d+)|US-?(\d+))", re.IGNORECASE)
    inline_us_re = re.compile(r"\(US-?(\d+)\)", re.IGNORECASE)
    req_line_re = re.compile(r"^\s*[-*]?\s*\**\(?(" + id_regex.pattern + r")\)?\**\s*[:.\-]?\s*(.*)$")

    rows: list[RequirementRow] = []

    for line in lines:
        us_match = us_heading_re.match(line.strip())
        if us_match:
            num = us_match.group(2) or us_match.group(3)
            current_user_story = f"US{num}"
            continue

        m = req_line_re.match(line)
        if not m:
            continue
        req_id = m.group(1)
        rest = m.group(2).strip()
        if not rest:
            continue  # riga che menziona l'ID ma non è la definizione (es. riferimento incrociato)

        inline_us = inline_us_re.search(line)
        user_story = f"US{inline_us.group(1)}" if inline_us else current_user_story

        rows.append(
            RequirementRow(
                requirement_key=f"{feature.feature_id}/{req_id}",
                feature=feature.feature_id,
                requirement_id=req_id,
                requirement_text=rest,
                source=f"{specs_root_label}/{feature.feature_id}/spec.md",
                user_story=user_story,
                scope_state="active",
                lifecycle_state="defined",
            )
        )

    return rows


TASK_LINE_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(T\d+)\b(.*)$")


def link_tasks(feature: Feature, accepted_id_patterns: list[str]) -> dict[str, dict]:
    """Legge tasks.md e ritorna, per ogni requirement_id trovato ESPLICITAMENTE nel testo
    di un task, la lista di task collegati con il loro stato di completamento.

    Ritorna: { requirement_id: {"task_ids": [...], "all_complete": bool} }
    Nessun matching semantico: un task è collegato SOLO se l'ID del requisito
    compare letteralmente nella riga del task.
    """
    if feature.tasks_path is None:
        return {}

    id_regex = _build_id_regex(accepted_id_patterns)
    text = feature.tasks_path.read_text(encoding="utf-8")

    links: dict[str, list[tuple[str, bool]]] = {}
    for line in text.splitlines():
        m = TASK_LINE_RE.match(line)
        if not m:
            continue
        complete = m.group(1).lower() == "x"
        task_id = m.group(2)
        rest = m.group(3)
        for req_id_match in re.finditer(id_regex, rest):
            req_id = req_id_match.group(0)
            links.setdefault(req_id, []).append((task_id, complete))

    result: dict[str, dict] = {}
    for req_id, task_list in links.items():
        result[req_id] = {
            "task_ids": [t for t, _ in task_list],
            "all_complete": all(c for _, c in task_list),
        }
    return result


def link_code_evidence(project_root: Path, source_globs: list[str], marker_pattern: str) -> dict[str, list[str]]:
    """Scansiona i file sorgente configurati cercando il marcatore esplicito
    (default: 'REQ: <requirement_key>' in un commento). Ritorna
    { requirement_key: ["path/to/file.py:42", ...] }.

    Nessuna euristica: solo corrispondenza letterale del marcatore.
    """
    marker_re = re.compile(marker_pattern)
    evidence: dict[str, list[str]] = {}
    for file_path in expand_globs(project_root, source_globs):
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in marker_re.finditer(line):
                req_key = m.group(1) if m.groups() else m.group(0)
                rel = file_path.relative_to(project_root)
                evidence.setdefault(req_key, []).append(f"{rel}:{lineno}")
    return evidence


def reconcile(
    existing_rows: list[RequirementRow],
    discovered_rows: list[RequirementRow],
    task_links_by_feature: dict[str, dict[str, dict]],
    code_evidence: dict[str, list[str]],
) -> tuple[list[RequirementRow], list[Finding]]:
    """Riconcilia le righe scoperte in questo giro con quelle già presenti nella Matrix.

    Regole (da TRACEABILITY-RULES.md e OPERATING-PROCEDURE.md):
    - match per chiave composita (feature/requirement_id);
    - i link già 'confirmed' in precedenza e le note umane si preservano SEMPRE,
      anche se questo giro non trova evidenza fresca per confermarli di nuovo;
    - un requisito presente prima ma non ritrovato ora viene mantenuto e
      segnalato (source-missing), MAI rimosso automaticamente;
    - ID duplicati nella stessa feature generano un Finding high.
    """
    findings: list[Finding] = []
    existing_by_key = {r.requirement_key: r for r in existing_rows}

    # Conta le occorrenze per chiave PRIMA di deduplicare: un duplicato nello
    # stesso giro di scoperta non deve mai dipendere da un marcatore infilato
    # nel campo Notes (che la preservazione delle note umane potrebbe
    # sovrascrivere) — si rileva qui, in modo indipendente.
    key_occurrences: dict[str, int] = {}
    for r in discovered_rows:
        key_occurrences[r.requirement_key] = key_occurrences.get(r.requirement_key, 0) + 1
    duplicate_keys = {k for k, count in key_occurrences.items() if count > 1}

    discovered_by_key = {r.requirement_key: r for r in discovered_rows}

    merged: dict[str, RequirementRow] = {}
    finding_seq = 1

    def next_finding_id() -> str:
        nonlocal finding_seq
        fid = f"FND-{finding_seq:03d}"
        finding_seq += 1
        return fid

    # 1. requisiti trovati in questo giro
    for key, discovered in discovered_by_key.items():
        existing = existing_by_key.get(key)
        task_info = task_links_by_feature.get(discovered.feature, {}).get(discovered.requirement_id)
        code_ev = code_evidence.get(key, [])

        row = discovered
        if existing is not None:
            # preserva le note umane esistenti; le note scoperte in questo giro
            # (di norma vuote, l'estrazione non le popola) non le sovrascrivono mai.
            if existing.notes:
                row.notes = existing.notes
            if existing.scope_state == "removed":
                row.scope_state = "removed"
            if existing.link_state == "confirmed" and not task_info and not code_ev:
                # nessuna nuova evidenza in questo giro: preserva il link confermato in precedenza
                row.task_ids = existing.task_ids
                row.code_evidence = existing.code_evidence
                row.test_ids = existing.test_ids
                row.link_state = existing.link_state
            # preserva sempre eventuali test_ids già collegati manualmente
            if not row.test_ids:
                row.test_ids = existing.test_ids

        if task_info:
            row.task_ids = ", ".join(f"`{t}`" for t in task_info["task_ids"])
        if code_ev:
            row.code_evidence = ", ".join(f"`{c}`" for c in code_ev)

        if task_info or code_ev:
            row.link_state = "confirmed"
        elif row.link_state != "confirmed":
            row.link_state = "incomplete"

        merged[key] = row

    # 2. requisiti presenti prima ma non ritrovati ora: mai rimuovere, sempre flaggare
    for key, existing in existing_by_key.items():
        if key in merged:
            continue
        merged[key] = existing
        findings.append(
            Finding(
                finding_id=next_finding_id(),
                severity="high",
                finding_type="source-missing",
                subject=key,
                description=(
                    "Il requisito era presente nella Matrix ma non è più stato trovato "
                    "in spec.md in questo refresh."
                ),
                recommended_action=(
                    "Verifica se è stato rimosso intenzionalmente (imposta scope_state=removed "
                    "con motivo in Notes) o se è un rinominazione dell'ID (conferma l'alias)."
                ),
            )
        )

    # 3. duplicati ID nella stessa feature (rilevati sulla lista grezza, non sulle Notes)
    for key in sorted(duplicate_keys):
        row = merged.get(key)
        if row is None:
            continue
        findings.append(
            Finding(
                finding_id=next_finding_id(),
                severity="high",
                finding_type="duplicate-id",
                subject=key,
                description=f"L'ID {row.requirement_id} compare più volte in {row.feature}/spec.md.",
                recommended_action="Rendi univoci gli ID dei requisiti dentro la stessa feature.",
            )
        )

    # 4. requisiti attivi senza alcun link (orfani)
    for row in merged.values():
        if row.scope_state == "active" and not row.task_ids and not row.code_evidence:
            findings.append(
                Finding(
                    finding_id=next_finding_id(),
                    severity="medium",
                    finding_type="requirement-orphan",
                    subject=row.requirement_key,
                    description="Nessun task o evidenza di codice collegata a questo requisito.",
                    recommended_action="Collega un task/commit, oppure conferma manualmente il collegamento.",
                )
            )

    ordered = sorted(merged.values(), key=lambda r: (r.feature, r.requirement_id))
    return ordered, findings
