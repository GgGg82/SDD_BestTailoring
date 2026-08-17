"""Caricamento e validazione completa della configurazione.

Chiude P1-06 e P1-07 dell'audit.

La v3 verificava soltanto la presenza delle sei chiavi di primo livello: una
config con `inputs: []` e `requirements: {}` superava `load_config` e
falliva molto piu' tardi con AttributeError o KeyError, a file di output gia'
creati. E cinque campi documentati nel template non erano usati da nessuna
parte del codice (`test_source_globs`, `default_scope_state`,
`allow_forced_snapshot`, `schema_version`, `risk_register_path`), il che e'
peggio di un campo assente: promette un comportamento che non esiste.

Qui la validazione e' completa e avviene PRIMA di qualunque scrittura, e ogni
campo dichiarato o e' implementato o non compare.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit(
        "ERRORE: manca la dipendenza 'pyyaml'.\n"
        "Installa il tool con:  uv tool install ./requirement-burnup-tool\n"
        "oppure in un virtualenv: python -m venv .venv && .venv/bin/pip install ./requirement-burnup-tool"
    )

from .errors import ConfigError
from .paths import resolve_under_root

CONFIG_SCHEMA_VERSION = "2.0"

VALID_FRESHNESS_POLICIES = ("current-revision", "latest-known", "manual-confirmation")
VALID_TEST_KINDS = ("unit", "integration", "e2e", "manual", "performance", "security")
VALID_SCOPE_STATES = ("active", "removed")


def _require(raw: dict, key: str, expected_type, *, where: str = "") -> Any:
    path = f"{where}.{key}" if where else key
    if key not in raw:
        raise ConfigError(
            f"Manca la chiave di configurazione obbligatoria '{path}'.",
            hint="Confronta con requirement-burnup-config.template.yml.",
        )
    value = raw[key]
    if not isinstance(value, expected_type):
        want = getattr(expected_type, "__name__", str(expected_type))
        raise ConfigError(
            f"La chiave '{path}' deve essere di tipo {want}, trovato {type(value).__name__}.",
        )
    return value


def _require_non_empty_list(raw: dict, key: str, *, where: str) -> list:
    value = _require(raw, key, list, where=where)
    if not value:
        raise ConfigError(
            f"La lista '{where}.{key}' e' vuota.",
            hint="Una lista vuota qui rende il risultato del burn-up privo di significato: indica almeno un elemento.",
        )
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ConfigError(f"'{where}.{key}' deve contenere solo stringhe non vuote.")
    return value


def _validate_regex(pattern: str, *, field_name: str) -> re.Pattern:
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ConfigError(
            f"La regex in '{field_name}' non e' valida: {exc}",
            hint=f"Pattern rifiutato: {pattern}",
        ) from exc


@dataclass
class BurnupConfig:
    project_root: Path
    config_path: Path
    output_dir: Path
    source_globs: list[str]
    test_report_globs: list[str]
    accepted_id_patterns: list[str]
    id_regex: re.Pattern
    code_evidence_marker: str
    code_evidence_regex: re.Pattern
    test_id_mapping: dict[str, str]
    freshness_policy: str
    default_scope_state: str
    requirement_sections: list[str]
    user_story_sections: list[str]
    comment_prefixes: list[str]
    extra_excludes: tuple[str, ...]
    allow_forced_snapshot: bool
    strict_blocks_on: tuple[str, ...]
    require_tasks_for_implemented: bool
    raw: dict = field(default_factory=dict)

    def risk_register_path(self, feature_dir: Path) -> Path:
        return feature_dir / "risk-register.md"


def load_config(config_path: Path, project_root: Path) -> BurnupConfig:
    if not config_path.exists():
        raise ConfigError(
            f"File di configurazione non trovato: {config_path}",
            hint="Esegui 'burnup init', oppure copia requirement-burnup-config.template.yml e compilalo.",
        )

    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML non valido in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path} non contiene una mappa YAML al livello radice.")

    # -- schema version: governa davvero la compatibilita' (P1-07) ---------
    schema_version = str(raw.get("schema_version", "")).strip()
    if not schema_version:
        raise ConfigError(
            "Manca 'schema_version' nella configurazione.",
            hint=f"Aggiungi:  schema_version: \"{CONFIG_SCHEMA_VERSION}\"",
        )
    if schema_version != CONFIG_SCHEMA_VERSION:
        raise ConfigError(
            f"schema_version '{schema_version}' non e' compatibile con questo engine (richiesto {CONFIG_SCHEMA_VERSION}).",
            # C-05: `burnup migrate-config` non esiste.
            hint=(
                "Aggiorna il file da requirement-burnup-config.template.yml: parti da "
                "schema_version, ma confronta anche i campi, perche' lo schema e' cambiato."
            ),
        )

    # -- output -----------------------------------------------------------
    output_raw = _require(raw, "output_dir", str)
    output_dir = resolve_under_root(project_root, output_raw, field="output_dir")

    # -- inputs -----------------------------------------------------------
    inputs = _require(raw, "inputs", dict)
    source_globs = _require_non_empty_list(inputs, "source_globs", where="inputs")
    test_report_globs = inputs.get("test_report_globs", []) or []
    if not isinstance(test_report_globs, list):
        raise ConfigError("'inputs.test_report_globs' deve essere una lista.")
    extra_excludes = tuple(inputs.get("exclude_dirs", []) or ())
    if not all(isinstance(x, str) for x in extra_excludes):
        raise ConfigError("'inputs.exclude_dirs' deve contenere solo stringhe.")

    # -- requirements -----------------------------------------------------
    requirements = _require(raw, "requirements", dict)
    accepted = _require_non_empty_list(requirements, "accepted_id_patterns", where="requirements")
    for p in accepted:
        _validate_regex(p, field_name="requirements.accepted_id_patterns")
    # Word boundary imposta dall'engine, non dall'utente: chiude P1-14, dove
    # `XFR-001Y` in un task veniva collegato a FR-001.
    id_regex = re.compile(r"(?<![A-Za-z0-9_-])(?:" + "|".join(f"(?:{p})" for p in accepted) + r")(?![A-Za-z0-9_])")

    default_scope_state = str(requirements.get("default_scope_state", "active"))
    if default_scope_state not in VALID_SCOPE_STATES:
        raise ConfigError(
            f"'requirements.default_scope_state' = '{default_scope_state}' non valido.",
            hint=f"Valori ammessi: {', '.join(VALID_SCOPE_STATES)}",
        )

    requirement_sections = requirements.get("sections", ["Requirements"])
    if not isinstance(requirement_sections, list) or not requirement_sections:
        raise ConfigError(
            "'requirements.sections' deve essere una lista non vuota.",
            hint="E' l'elenco delle sezioni di spec.md da cui estrarre i requisiti, es. ['Requirements'].",
        )
    user_story_sections = requirements.get("user_story_sections", ["User Scenarios", "User Stories"])
    if not isinstance(user_story_sections, list):
        raise ConfigError("'requirements.user_story_sections' deve essere una lista.")

    # -- traceability -----------------------------------------------------
    traceability = _require(raw, "traceability", dict)
    marker = traceability.get("code_evidence_marker") or r"REQ:\s*([A-Za-z0-9_.\-]+/[A-Za-z0-9_\-]+)"
    marker_re = _validate_regex(marker, field_name="traceability.code_evidence_marker")
    if marker_re.groups < 1:
        raise ConfigError(
            "'traceability.code_evidence_marker' deve avere almeno un gruppo di cattura, che catturi la chiave 'feature/requisito'.",
            hint=r"Esempio: REQ:\s*([A-Za-z0-9_.\-]+/[A-Za-z0-9_\-]+)",
        )
    mapping = traceability.get("test_id_mapping", {}) or {}
    if not isinstance(mapping, dict):
        raise ConfigError("'traceability.test_id_mapping' deve essere una mappa.")
    comment_prefixes = traceability.get("comment_prefixes", ["#", "//", "--", "/*", "*", ";", "%", "'"])
    if not isinstance(comment_prefixes, list) or not comment_prefixes:
        raise ConfigError("'traceability.comment_prefixes' deve essere una lista non vuota.")

    # -- status -----------------------------------------------------------
    status = _require(raw, "status", dict)
    policy = _require(status, "test_freshness_policy", str, where="status")
    if policy not in VALID_FRESHNESS_POLICIES:
        raise ConfigError(
            f"'status.test_freshness_policy' = '{policy}' non valida.",
            hint=f"Valori ammessi: {', '.join(VALID_FRESHNESS_POLICIES)}",
        )
    # P1-30: in v3 l'assenza di task rendeva `tasks_ok` vero, quindi il solo
    # marker nel codice bastava per 'implemented'. Ora e' una scelta esplicita
    # e il default e' quello prudente.
    require_tasks = bool(status.get("require_tasks_for_implemented", True))

    # -- snapshots --------------------------------------------------------
    snapshots = _require(raw, "snapshots", dict)
    allow_forced = bool(snapshots.get("allow_forced_snapshot", True))

    # -- gates ------------------------------------------------------------
    gates = raw.get("gates", {}) or {}
    if not isinstance(gates, dict):
        raise ConfigError("'gates' deve essere una mappa.")
    blocks_on = tuple(gates.get("strict_blocks_on", ["high"]))
    for sev in blocks_on:
        if sev not in ("low", "medium", "high"):
            raise ConfigError(
                f"'gates.strict_blocks_on' contiene una severita' sconosciuta: '{sev}'.",
                hint="Valori ammessi: low, medium, high.",
            )

    return BurnupConfig(
        project_root=project_root,
        config_path=config_path,
        output_dir=output_dir,
        source_globs=source_globs,
        test_report_globs=test_report_globs,
        accepted_id_patterns=accepted,
        id_regex=id_regex,
        code_evidence_marker=marker,
        code_evidence_regex=marker_re,
        test_id_mapping={str(k): str(v) for k, v in mapping.items()},
        freshness_policy=policy,
        default_scope_state=default_scope_state,
        requirement_sections=[str(s) for s in requirement_sections],
        user_story_sections=[str(s) for s in user_story_sections],
        comment_prefixes=[str(c) for c in comment_prefixes],
        extra_excludes=extra_excludes,
        allow_forced_snapshot=allow_forced,
        strict_blocks_on=blocks_on,
        require_tasks_for_implemented=require_tasks,
        raw=raw,
    )
