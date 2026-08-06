"""
Calcolo dei conteggi correnti (BURNUP-CALCULATION.md) e gestione degli
snapshot storici, append-only e mai riscritti.

Politica confermata con l'utente: uno snapshot si aggiunge SOLO quando i
conteggi attivi cambiano o lo scope cambia — mai ad ogni refresh per
principio. È sempre possibile forzarne uno manualmente (checkpoint a
calendario) tramite il flag --force-snapshot della CLI.
"""
from __future__ import annotations

from dataclasses import dataclass

from .requirements import RequirementRow


@dataclass
class Counts:
    scope: int
    defined: int
    implemented: int
    tested: int
    removed_total: int

    def as_dict(self) -> dict:
        return {
            "scope": self.scope,
            "defined": self.defined,
            "implemented": self.implemented,
            "tested": self.tested,
            "removed_total": self.removed_total,
        }


def compute_counts(rows: list[RequirementRow]) -> Counts:
    active = [r for r in rows if r.scope_state == "active"]
    removed = [r for r in rows if r.scope_state == "removed"]

    scope = len(active)
    defined = sum(1 for r in active if r.lifecycle_state in ("defined", "implemented", "tested"))
    implemented = sum(1 for r in active if r.lifecycle_state in ("implemented", "tested"))
    tested = sum(1 for r in active if r.lifecycle_state == "tested")

    # Invariante da BURNUP-CALCULATION.md: tested <= implemented <= defined <= scope.
    # Un fallimento qui indica un bug nello status_rules, non un problema legittimo
    # di dati — meglio fallire rumorosamente ora che pubblicare un grafico sbagliato.
    assert tested <= implemented <= defined <= scope, (
        f"Invariante di burn-up violata: tested={tested} implemented={implemented} "
        f"defined={defined} scope={scope}"
    )

    return Counts(scope=scope, defined=defined, implemented=implemented, tested=tested, removed_total=len(removed))


def tested_percent(counts: Counts) -> str:
    if counts.scope == 0:
        return "N/A"
    pct = 100 * counts.tested / counts.scope
    return f"{pct:.1f}%"


def should_append_snapshot(
    last_counts: Counts | None,
    new_counts: Counts,
    append_when_counts_change: bool,
    append_when_scope_changes: bool,
    forced: bool,
) -> tuple[bool, str]:
    if forced:
        return True, "forced"
    if last_counts is None:
        return True, "initial"
    if append_when_scope_changes and new_counts.scope != last_counts.scope:
        return True, "scope-change"
    if append_when_counts_change and (
        new_counts.defined != last_counts.defined
        or new_counts.implemented != last_counts.implemented
        or new_counts.tested != last_counts.tested
    ):
        return True, "status-change"
    return False, "no-change"


def next_snapshot_id(existing_snapshot_rows: list[dict]) -> str:
    existing_nums = []
    for row in existing_snapshot_rows:
        raw = (row.get("Snapshot ID", "") or "").strip("`")
        if raw.startswith("SNP-"):
            try:
                existing_nums.append(int(raw[4:]))
            except ValueError:
                continue
    n = (max(existing_nums) + 1) if existing_nums else 1
    return f"SNP-{n:03d}"


def next_run_id(existing_run_rows: list[dict], timestamp: str) -> str:
    date_part = timestamp.split("T")[0].replace("-", "")
    same_day = [r for r in existing_run_rows if (r.get("Run ID", "") or "").strip("`").startswith(f"RUN-{date_part}")]
    return f"RUN-{date_part}-{len(same_day) + 1:03d}"
