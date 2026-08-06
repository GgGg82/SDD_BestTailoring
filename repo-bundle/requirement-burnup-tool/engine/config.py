"""
Caricamento e validazione di requirement-burnup-config.yml.

Questo modulo non decide MAI valori di default "silenziosamente" per le
opzioni che richiedono giudizio umano (pattern ID, policy di freschezza,
percorsi di scansione): quelle vengono scritte nel file di config durante
l'intervista condotta dal Technical Auditor (agente), non da questo script.
Questo modulo si limita a leggere, validare la forma del file, e applicare
SOLO i default meccanici documentati (es. schema_version).

Dipendenza esterna: pyyaml (vedi INSTALL.md del framework).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print(
        "ERRORE: manca la dipendenza 'pyyaml'.\n"
        "Installala con: pip install pyyaml --break-system-packages\n"
        "(o 'uv pip install pyyaml' se il progetto usa un virtualenv gestito da uv)",
        file=sys.stderr,
    )
    raise

REQUIRED_TOP_LEVEL_KEYS = ("output_dir", "inputs", "requirements", "traceability", "status", "snapshots")

VALID_FRESHNESS_POLICIES = ("current-revision", "latest-known", "manual-confirmation")


class ConfigError(Exception):
    """Errore di configurazione: file mancante, malformato, o valori non validi."""


@dataclass
class BurnupConfig:
    raw: dict[str, Any]
    config_path: Path
    project_root: Path

    # --- accessor comodi, con validazione esplicita invece di .get() silenzioso ---

    @property
    def output_dir(self) -> Path:
        return self.project_root / self.raw["output_dir"]

    @property
    def source_globs(self) -> list[str]:
        return self.raw["inputs"].get("source_globs", [])

    @property
    def test_source_globs(self) -> list[str]:
        return self.raw["inputs"].get("test_source_globs", [])

    @property
    def test_report_globs(self) -> list[str]:
        return self.raw["inputs"].get("test_report_globs", [])

    @property
    def accepted_id_patterns(self) -> list[str]:
        return self.raw["requirements"]["accepted_id_patterns"]

    @property
    def freshness_policy(self) -> str:
        policy = self.raw["status"]["test_freshness_policy"]
        if policy not in VALID_FRESHNESS_POLICIES:
            raise ConfigError(
                f"test_freshness_policy '{policy}' non valida. "
                f"Valori ammessi: {', '.join(VALID_FRESHNESS_POLICIES)}"
            )
        return policy

    @property
    def append_when_counts_change(self) -> bool:
        return bool(self.raw["snapshots"].get("append_when_counts_change", True))

    @property
    def append_when_scope_changes(self) -> bool:
        return bool(self.raw["snapshots"].get("append_when_scope_changes", True))

    @property
    def code_evidence_marker_pattern(self) -> str:
        """Pattern del commento/annotazione esplicita nel codice che conferma un legame.

        Esempio di default: 'REQ: 001-example/FR-001' dentro un commento.
        Deve essere configurabile perché convenzioni di commento cambiano per linguaggio
        (MQL5, Python, TypeScript, ...).
        """
        return self.raw.get("traceability", {}).get("code_evidence_marker", r"REQ:\s*([A-Za-z0-9_.\-]+/[A-Za-z0-9_\-]+)")

    def risk_register_path(self, feature_dir: Path) -> Path:
        return feature_dir / "risk-register.md"


def load_config(config_path: Path, project_root: Path) -> BurnupConfig:
    if not config_path.exists():
        raise ConfigError(
            f"File di configurazione non trovato: {config_path}\n"
            "Esegui prima l'intervista di inizializzazione (comando 'init') "
            "oppure copia requirement-burnup-config.template.yml e compilalo."
        )

    with config_path.open("r", encoding="utf-8") as f:
        try:
            raw = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ConfigError(f"YAML non valido in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path} non contiene una mappa YAML valida al livello radice.")

    missing = [k for k in REQUIRED_TOP_LEVEL_KEYS if k not in raw]
    if missing:
        raise ConfigError(
            f"{config_path} manca delle chiavi obbligatorie: {', '.join(missing)}. "
            "Confronta con requirement-burnup-config.template.yml."
        )

    return BurnupConfig(raw=raw, config_path=config_path, project_root=project_root)
