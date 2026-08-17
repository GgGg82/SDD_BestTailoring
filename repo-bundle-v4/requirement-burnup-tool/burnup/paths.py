"""Confinamento di ogni percorso alla radice del progetto.

Chiude P0-09 e N-07 dell'audit.

Nella v3 `output_dir` veniva risolto con `project_root / raw["output_dir"]`:
in Python, se il secondo operando e' assoluto sovrascrive il primo, quindi
`output_dir: /tmp/OUTSIDE` scriveva fuori dal repository. In parallelo
`expand_globs` faceva `glob.glob(str(project_root / pattern))`, con lo stesso
difetto in lettura: un glob assoluto leggeva file arbitrari del filesystem e
poteva riportarne il contenuto negli artefatti generati.

Qui vale una regola sola: **ogni percorso e' relativo alla radice del
progetto, e deve risolversi sotto di essa dopo la risoluzione dei symlink.**
"""
from __future__ import annotations

import glob as _glob
import os
from pathlib import Path, PurePosixPath

from .errors import PathConfinementError

# Directory sempre escluse dalla scansione dei sorgenti, a prescindere dalla
# configurazione. `requirement-burnup` e' nell'elenco per N-07: gli artefatti
# generati contengono marker `REQ:` nelle celle Code Evidence, e senza questa
# esclusione un glob ampio farebbe auto-alimentare l'evidenza di codice.
ALWAYS_EXCLUDED = (
    ".git",
    ".hg",
    ".svn",
    "requirement-burnup",
    "requirement-burnup-tool",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".idea",
    ".vscode",
)


def _is_within(child: Path, parent: Path) -> bool:
    """True se `child` e' `parent` o e' contenuto in `parent`, dopo resolve()."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def resolve_under_root(project_root: Path, raw_path: str, *, field: str) -> Path:
    """Risolve un percorso configurato garantendo che resti sotto la radice.

    Respinge, con un messaggio che dice quale campo di configurazione correggere:
      - percorsi assoluti (`/etc`, `C:\\Windows`);
      - traversal con `..` che esce dalla radice;
      - symlink che puntano fuori dalla radice.
    """
    if raw_path is None or str(raw_path).strip() == "":
        raise PathConfinementError(
            f"Il campo di configurazione '{field}' e' vuoto.",
            hint="Indica un percorso relativo alla radice del progetto, es. 'requirement-burnup'.",
        )

    text = str(raw_path).strip()
    candidate = Path(text)

    if candidate.is_absolute() or (os.name == "nt" and candidate.drive):
        raise PathConfinementError(
            f"Il campo '{field}' contiene un percorso assoluto ({text}).",
            hint="Usa un percorso relativo alla radice del progetto: l'engine non scrive né legge mai fuori dal repository.",
        )

    # Normalizzazione puramente lessicale prima di toccare il filesystem: cosi'
    # un `..` viene intercettato anche se il path non esiste ancora.
    parts = PurePosixPath(text.replace("\\", "/")).parts
    depth = 0
    for part in parts:
        # `PurePosixPath.parts` normalizza gia' via i segmenti neutri: `out/./x`
        # e `out//x` danno entrambi ('out', 'x'). La guardia resta perche' il
        # confinamento non deve dipendere da un dettaglio di pathlib, ma non e'
        # raggiungibile — e dichiararlo e' piu' onesto che costruire un test
        # che finge di arrivarci.
        if part in (".", ""):  # pragma: no cover - normalizzato da PurePosixPath
            continue
        if part == "..":
            depth -= 1
            if depth < 0:
                raise PathConfinementError(
                    f"Il campo '{field}' esce dalla radice del progetto tramite '..' ({text}).",
                    hint="I percorsi devono restare dentro il repository.",
                )
            continue
        depth += 1

    resolved = (project_root / candidate)

    # Il controllo sui symlink si applica al primo antenato che esiste davvero:
    # una directory di output non esiste ancora al primo `init`.
    probe = resolved
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if probe.exists() and not _is_within(probe, project_root):
        raise PathConfinementError(
            f"Il campo '{field}' risolve fuori dalla radice del progetto tramite un symlink ({text}).",
            hint="Rimuovi il symlink o indica un percorso reale interno al repository.",
        )

    return resolved


def is_excluded(path: Path, project_root: Path, extra_excludes: tuple[str, ...] = ()) -> bool:
    """True se il percorso attraversa una directory sempre esclusa."""
    try:
        rel = path.resolve().relative_to(project_root.resolve())
    except (ValueError, OSError):
        return True  # fuori dalla radice: escluso per definizione
    excluded = set(ALWAYS_EXCLUDED) | set(extra_excludes)
    return any(part in excluded for part in rel.parts)


def expand_globs(
    project_root: Path,
    patterns: list[str],
    *,
    field: str = "inputs",
    extra_excludes: tuple[str, ...] = (),
) -> list[Path]:
    """Espande pattern glob confinati alla radice, in ordine deterministico.

    L'ordinamento non e' cosmetico: la v3 dipendeva dall'ordine di
    restituzione del filesystem, che varia tra sistemi e rendeva l'output non
    riproducibile (fallimento Reproducibility nella MSA dell'audit).
    """
    results: list[Path] = []
    seen: set[Path] = set()

    for pattern in patterns:
        text = str(pattern).strip()
        if not text:
            continue
        if Path(text).is_absolute():
            raise PathConfinementError(
                f"Il glob '{text}' in '{field}' e' assoluto.",
                hint="I glob devono essere relativi alla radice del progetto.",
            )
        if ".." in PurePosixPath(text.replace("\\", "/")).parts:
            raise PathConfinementError(
                f"Il glob '{text}' in '{field}' contiene '..'.",
                hint="I glob non possono uscire dalla radice del progetto.",
            )

        for match in _glob.glob(str(project_root / text), recursive=True):
            p = Path(match)
            if not p.is_file():
                continue
            if not _is_within(p, project_root):
                # Un symlink dentro il repo che punta fuori: si scarta in
                # silenzio invece di sollevare, perche' e' una proprieta' del
                # workspace e non un errore di configurazione.
                continue
            if is_excluded(p, project_root, extra_excludes):
                continue
            rp = p.resolve()
            if rp in seen:
                continue
            seen.add(rp)
            results.append(p)

    return sorted(results, key=lambda p: str(p.relative_to(project_root)).replace("\\", "/"))


def relative_label(path: Path, project_root: Path) -> str:
    """Etichetta stabile e portabile di un percorso, per report e store.

    Sempre con separatore POSIX: lo stesso repository su Windows e su Linux
    deve produrre artefatti identici byte per byte.
    """
    try:
        return str(path.resolve().relative_to(project_root.resolve())).replace("\\", "/")
    except (ValueError, OSError):
        return str(path).replace("\\", "/")
