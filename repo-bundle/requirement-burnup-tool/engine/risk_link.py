"""
Lettura di risk-register.md (di proprietà della Business Analyst/QA, Gate 2)
e collegamento a SENSO UNICO verso la Traceability Matrix.

Regola concordata con l'utente: questo script legge risk-register.md in
sola lettura e non lo modifica mai. Se un rischio ha il campo "Requisiti
collegati" compilato con un ID che corrisponde esattamente a un requisito
di quella stessa feature, annota il collegamento nelle Note della riga
corrispondente in Matrix. Se il campo è vuoto, il rischio conta solo a
livello di feature nel Governance Dashboard — non si inventa mai una
precisione che il dato non ha.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .md_tables import load_document, parse_table


@dataclass
class OpenRisk:
    risk_id: str
    description: str
    linked_requirement_ids: list[str]  # vuoto se il rischio è solo a livello di feature


def read_open_risks(feature_dir: Path) -> list[OpenRisk]:
    """Legge risk-register.md della feature, se presente, e ritorna i rischi con Stato 'aperto'."""
    risk_file = feature_dir / "risk-register.md"
    if not risk_file.exists():
        return []

    doc = load_document(risk_file)
    parsed = parse_table(doc.body, "Rischi")
    if parsed is None:
        return []
    _, rows = parsed

    def unbacktick(v: str) -> str:
        v = (v or "").strip()
        if v.startswith("`") and v.endswith("`"):
            return v[1:-1]
        return "" if v == "—" else v

    open_risks: list[OpenRisk] = []
    for row in rows:
        stato = unbacktick(row.get("Stato", ""))
        if stato != "aperto":
            continue
        linked_raw = unbacktick(row.get("Requisiti collegati", ""))
        linked_ids = [x.strip() for x in linked_raw.split(",") if x.strip()] if linked_raw else []
        open_risks.append(
            OpenRisk(
                risk_id=unbacktick(row.get("Risk ID", "")),
                description=row.get("Descrizione", "") or "",
                linked_requirement_ids=linked_ids,
            )
        )
    return open_risks


def annotate_matrix_with_risks(rows, open_risks_by_feature: dict[str, list[OpenRisk]]) -> None:
    """Aggiorna row.notes IN PLACE per i requisiti con un rischio esplicitamente collegato.
    Idempotente: non duplica l'annotazione se già presente da un giro precedente."""
    for row in rows:
        risks = open_risks_by_feature.get(row.feature, [])
        for risk in risks:
            if row.requirement_id in risk.linked_requirement_ids:
                marker = f"[rischio aperto: {risk.risk_id}, vedi risk-register.md]"
                if marker not in row.notes:
                    row.notes = (row.notes + " " if row.notes else "") + marker
