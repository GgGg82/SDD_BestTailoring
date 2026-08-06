"""
Rilevamento del layout Spec Kit e scoperta delle feature.

Decisione di design (vedi DESIGN-DECISIONS.md del pacchetto originale e la
discussione con l'utente): la documentazione ufficiale di Spec Kit è
discordante tra versioni su dove viva la cartella specs/ — a volte alla
radice del repo, a volte annidata in .specify/specs/. Questo modulo NON
assume nessuna delle due: rileva quale esiste davvero nel repo del progetto
al momento dell'esecuzione.
"""
from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path


class SpecsLayoutError(Exception):
    """Nessun layout Spec Kit riconoscibile trovato nel repo."""


CANDIDATE_SPECS_SUBPATHS = ("specs", ".specify/specs")


@dataclass
class Feature:
    feature_id: str          # nome della cartella, es. "001-book-visit"
    spec_path: Path
    plan_path: Path | None
    tasks_path: Path | None
    directory: Path


def detect_specs_root(project_root: Path) -> Path:
    """Prova le convenzioni candidate in ordine e usa la prima che trova spec.md reali.

    Restituisce il percorso assoluto della cartella specs/ effettivamente in uso.
    Solleva SpecsLayoutError se nessuna delle due contiene almeno una spec.md.
    """
    for candidate in CANDIDATE_SPECS_SUBPATHS:
        candidate_path = project_root / candidate
        matches = list(candidate_path.glob("*/spec.md"))
        if matches:
            return candidate_path

    raise SpecsLayoutError(
        "Nessuna cartella feature con spec.md trovata in nessuna delle convenzioni note:\n"
        + "\n".join(f"  - {project_root / c}/<feature>/spec.md" for c in CANDIDATE_SPECS_SUBPATHS)
        + "\nVerifica di essere nella radice di un progetto Spec Kit inizializzato."
    )


def discover_features(specs_root: Path) -> list[Feature]:
    """Elenca tutte le feature (una per sottocartella con uno spec.md)."""
    features: list[Feature] = []
    for spec_file in sorted(specs_root.glob("*/spec.md")):
        feature_dir = spec_file.parent
        feature_id = feature_dir.name
        plan_path = feature_dir / "plan.md"
        tasks_path = feature_dir / "tasks.md"
        features.append(
            Feature(
                feature_id=feature_id,
                spec_path=spec_file,
                plan_path=plan_path if plan_path.exists() else None,
                tasks_path=tasks_path if tasks_path.exists() else None,
                directory=feature_dir,
            )
        )
    return features


def expand_globs(project_root: Path, patterns: list[str]) -> list[Path]:
    """Espande una lista di pattern glob (relativi alla radice progetto) in path assoluti esistenti."""
    results: list[Path] = []
    for pattern in patterns:
        for match in glob.glob(str(project_root / pattern), recursive=True):
            p = Path(match)
            if p.is_file():
                results.append(p)
    return results
