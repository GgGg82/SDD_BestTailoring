"""Scoperta delle feature ed estrazione dell'evidenza dagli artefatti Spec Kit.

Chiude P0-04, P1-13, P1-14, P1-29 e N-07 dell'audit.

Tutte le funzioni qui sono **pure rispetto al filesystem in lettura**: non
scrivono nulla e non hanno stato tra chiamate. Lo stato vive nel canonical
store.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import BurnupConfig
from .errors import SpecsLayoutError
from .fingerprint import artifact_fingerprint, requirement_fingerprint
from .mdparse import Section, parse_document, read_text
from .models import Requirement
from .paths import expand_globs, relative_label

CANDIDATE_SPECS_SUBPATHS = ("specs", ".specify/specs")

_US_HEADING_RE = re.compile(r"^\s*(?:User Story|US)\s*[-#]?\s*(\d+)\b", re.IGNORECASE)
_INLINE_US_RE = re.compile(r"\(\s*US-?\s*(\d+)\s*\)", re.IGNORECASE)
_TASK_LINE_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(T\d+)\b(.*)$")
_NONREQ_RE = re.compile(r"\[NON-REQ(?::\s*([^\]]*))?\]", re.IGNORECASE)


@dataclass
class Feature:
    feature_id: str
    directory: Path
    spec_path: Path
    plan_path: Path | None
    tasks_path: Path | None

    def fingerprints(self, project_root: Path) -> dict[str, str]:
        """Fingerprint degli artefatti della feature, per l'invalidazione dei gate (P1-27)."""
        out: dict[str, str] = {}
        for name, path in (("spec", self.spec_path), ("plan", self.plan_path), ("tasks", self.tasks_path)):
            if path and path.exists():
                out[name] = artifact_fingerprint(read_text(path))
        return out


def detect_specs_root(project_root: Path) -> Path:
    """Individua la radice delle spec, fallendo se il layout e' ambiguo.

    Chiude P1-13: la v3 restituiva il primo layout candidato che conteneva
    spec.md, senza nemmeno un avviso. Con `specs/` e `.specify/specs/`
    entrambe popolate — situazione tipica di una migrazione a meta' — meta'
    delle feature spariva silenziosamente dal burn-up, e il numero risultante
    sembrava comunque plausibile.
    """
    found = [
        project_root / candidate
        for candidate in CANDIDATE_SPECS_SUBPATHS
        if list((project_root / candidate).glob("*/spec.md"))
    ]

    if not found:
        raise SpecsLayoutError(
            "Nessuna cartella feature con spec.md trovata nelle convenzioni note:\n"
            + "\n".join(f"  - {project_root / c}/<feature>/spec.md" for c in CANDIDATE_SPECS_SUBPATHS),
            hint="Verifica di essere nella radice di un progetto Spec Kit inizializzato.",
        )

    if len(found) > 1:
        raise SpecsLayoutError(
            "Trovate DUE radici di spec popolate contemporaneamente:\n"
            + "\n".join(f"  - {p}" for p in found),
            hint=(
                "Consolida le feature in un'unica radice. Un layout ambiguo farebbe sparire "
                "silenziosamente meta' dei requisiti dal burn-up, con un totale comunque plausibile."
            ),
        )

    return found[0]


def discover_features(specs_root: Path) -> list[Feature]:
    features: list[Feature] = []
    for spec_file in sorted(specs_root.glob("*/spec.md")):
        d = spec_file.parent
        plan = d / "plan.md"
        tasks = d / "tasks.md"
        features.append(
            Feature(
                feature_id=d.name,
                directory=d,
                spec_path=spec_file,
                plan_path=plan if plan.exists() else None,
                tasks_path=tasks if tasks.exists() else None,
            )
        )
    return features


# --------------------------------------------------------------------------
# Estrazione dei requisiti
# --------------------------------------------------------------------------

def _user_story_from_section(section: Section, user_story_sections: list[str]) -> tuple[str, str]:
    """Ricava la user story dall'APPARTENENZA STRUTTURALE della sezione.

    Il cuore della correzione di P0-04. La v3 teneva una variabile
    `current_user_story` che veniva impostata da un heading "User Story N" e
    non azzerata mai: attraversando `## Requirements`, ogni requisito globale
    ereditava l'ultima user story incontrata. Verificato: FR-001 e NFR-001
    sotto `## Requirements` risultavano entrambi appartenere a US2.

    Qui si guarda il percorso gerarchico della sezione. Se il requisito non
    e' *dentro* una user story, non appartiene a nessuna: nessun valore viene
    ereditato da cio' che precede nel file.
    """
    for title in reversed(section.path):
        m = _US_HEADING_RE.match(title.strip())
        if m:
            return f"US{m.group(1)}", "structural"
    return "", ""


def _section_is_requirements(section: Section, requirement_sections: list[str]) -> bool:
    wanted = {s.strip().lower() for s in requirement_sections}
    return any(part.strip().lower() in wanted for part in section.path)


def extract_requirements(
    feature: Feature,
    config: BurnupConfig,
    specs_root_label: str,
) -> tuple[list[Requirement], list[tuple[str, str]]]:
    """Estrae i requisiti dalle SOLE sezioni configurate.

    Ritorna (requisiti, anomalie) dove ogni anomalia e' (tipo, dettaglio).

    Chiude la seconda meta' di P0-04: la v3 estraeva qualunque riga che
    somigliasse a un requisito, in qualunque punto del documento. Verificato:
    `- FR-999: vedi documento esterno` scritto sotto `# Notes` come semplice
    rimando entrava nel burn-up come requisito reale, gonfiando lo scope.
    """
    text = read_text(feature.spec_path)
    doc = parse_document(text)
    source_label = f"{specs_root_label}/{feature.feature_id}/spec.md"

    id_alt = "|".join(f"(?:{p})" for p in config.accepted_id_patterns)
    req_line_re = re.compile(
        r"^\s*(?:[-*+]\s*)?\**\s*(?P<id>" + id_alt + r")\**\s*(?:\((?P<us>US-?\d+)\))?\s*[:.—-]\s*(?P<text>.+?)\s*$",
        re.IGNORECASE,
    )

    requirements: list[Requirement] = []
    anomalies: list[tuple[str, str]] = []
    seen: dict[str, int] = {}

    for section in doc.sections:
        in_requirements = _section_is_requirements(section, config.requirement_sections)
        us_structural, us_origin = _user_story_from_section(section, config.user_story_sections)

        for lineno, line in section.lines:
            m = req_line_re.match(line)
            if not m:
                continue

            req_id = m.group("id")
            body = (m.group("text") or "").strip()
            if not body:
                continue

            if not in_requirements:
                # Non e' un requisito: e' un rimando. Si segnala perche' un
                # riferimento a un ID inesistente resta un problema di qualita'
                # della spec — ma non entra nello scope.
                anomalies.append((
                    "reference-outside-requirements",
                    f"{source_label}:{lineno + 1}: '{req_id}' citato in '{' > '.join(section.path) or '(preambolo)'}', "
                    "fuori dalle sezioni dei requisiti: non conteggiato nello scope.",
                ))
                continue

            inline = _INLINE_US_RE.search(line)
            if inline:
                user_story, origin = f"US{inline.group(1)}", "inline"
            else:
                user_story, origin = us_structural, us_origin

            key = f"{feature.feature_id}/{req_id}"
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 1:
                anomalies.append((
                    "duplicate-requirement-id",
                    f"{source_label}:{lineno + 1}: l'ID '{req_id}' compare {seen[key]} volte nella stessa feature.",
                ))
                continue

            requirements.append(
                Requirement(
                    key=key,
                    feature_id=feature.feature_id,
                    requirement_id=req_id,
                    text=body,
                    fingerprint=requirement_fingerprint(requirement_id=req_id, text=body),
                    source=source_label,
                    source_line=lineno + 1,
                    section_path=section.path,
                    user_story=user_story,
                    user_story_origin=origin,
                )
            )

    return requirements, anomalies


# --------------------------------------------------------------------------
# Collegamento ai task
# --------------------------------------------------------------------------

@dataclass
class TaskLink:
    task_id: str
    complete: bool
    line: int


@dataclass
class TaskScan:
    by_requirement: dict[str, list[TaskLink]] = field(default_factory=dict)
    anomalies: list[tuple[str, str]] = field(default_factory=list)
    total_tasks: int = 0
    unlinked_tasks: list[str] = field(default_factory=list)


def link_tasks(feature: Feature, config: BurnupConfig) -> TaskScan:
    """Collega i task ai requisiti citati esplicitamente nella riga del task.

    Chiude la prima meta' di P1-14. La v3 cercava gli ID con una regex priva di
    word boundary: verificato, `- [x] T001 Implement XFR-001Y helper` veniva
    collegato a FR-001. Il boundary e' imposto dall'engine in `config.id_regex`,
    non lasciato alla regex scritta dall'utente.

    Riconosce inoltre il marcatore `[NON-REQ: motivo]`, che permette di
    dichiarare un task deliberatamente non tracciabile invece di lasciarlo
    apparire come dimenticanza.
    """
    scan = TaskScan()
    if feature.tasks_path is None:
        return scan

    text = read_text(feature.tasks_path)
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _TASK_LINE_RE.match(line)
        if not m:
            continue
        scan.total_tasks += 1
        complete = m.group(1).lower() == "x"
        task_id = m.group(2)
        rest = m.group(3)

        if _NONREQ_RE.search(rest):
            continue

        ids = {mm.group(0) for mm in config.id_regex.finditer(rest)}
        if not ids:
            scan.unlinked_tasks.append(task_id)
            continue
        for req_id in sorted(ids):
            scan.by_requirement.setdefault(req_id, []).append(
                TaskLink(task_id=task_id, complete=complete, line=lineno)
            )

    return scan


# --------------------------------------------------------------------------
# Evidenza nel codice
# --------------------------------------------------------------------------

@dataclass
class CodeEvidence:
    requirement_key: str
    path: str
    line: int

    @property
    def ref(self) -> str:
        return f"{self.path}:{self.line}"


def _is_comment_line(stripped: str, prefixes: list[str]) -> bool:
    return any(stripped.startswith(p) for p in prefixes)


def link_code_evidence(
    project_root: Path,
    config: BurnupConfig,
) -> tuple[dict[str, list[CodeEvidence]], list[tuple[str, str]]]:
    """Cerca il marcatore esplicito, accettandolo SOLO dentro un commento.

    Chiude la seconda meta' di P1-14 e P1-29. Verificato sulla v3:

        msg = "REQ: 001-demo/FR-001 not a real link"   <- contava come evidenza

    Una stringa eseguibile non e' una dichiarazione di tracciabilita'. Qui il
    marcatore vale se la riga e' un commento, oppure se il marcatore compare
    dopo un delimitatore di commento a fine riga (commento in coda al codice).

    L'esclusione della directory di output avviene a monte, in `expand_globs`
    (N-07): senza, i marcatori presenti nelle celle Code Evidence della Matrix
    generata verrebbero riletti come evidenza, e il sistema si
    auto-alimenterebbe.
    """
    evidence: dict[str, list[CodeEvidence]] = {}
    anomalies: list[tuple[str, str]] = []
    prefixes = config.comment_prefixes

    for file_path in expand_globs(
        project_root, config.source_globs, field="inputs.source_globs", extra_excludes=config.extra_excludes
    ):
        try:
            content = file_path.read_text(encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            continue  # binario: non e' codice sorgente tracciabile
        except OSError as exc:
            anomalies.append(("unreadable-source", f"{relative_label(file_path, project_root)}: {exc}"))
            continue

        rel = relative_label(file_path, project_root)
        for lineno, line in enumerate(content.splitlines(), start=1):
            for m in config.code_evidence_regex.finditer(line):
                before = line[: m.start()]
                stripped_before = before.strip()
                in_comment = (
                    _is_comment_line(line.lstrip(), prefixes)
                    or any(p in before for p in prefixes)
                )
                if not in_comment:
                    anomalies.append((
                        "marker-outside-comment",
                        f"{rel}:{lineno}: marcatore '{m.group(0)[:60]}' trovato fuori da un commento: ignorato.",
                    ))
                    continue
                # Un marcatore preceduto da un apice aperto sulla stessa riga e'
                # dentro una stringa, non in un commento.
                if stripped_before.count('"') % 2 == 1 or stripped_before.count("'") % 2 == 1:
                    anomalies.append((
                        "marker-inside-string",
                        f"{rel}:{lineno}: marcatore dentro una stringa: ignorato.",
                    ))
                    continue

                key = m.group(1) if config.code_evidence_regex.groups else m.group(0)
                evidence.setdefault(key, []).append(CodeEvidence(requirement_key=key, path=rel, line=lineno))

    return evidence, anomalies
