"""Lettura del risk register della feature, a senso unico.

Chiude P1-09 dell'audit.

Due difetti distinti nella v3:

1. il parsing degli ID collegati faceva `unbacktick()` sull'intera cella e poi
   `split(",")`. Verificato: la cella `` `FR-001`, `FR-002` `` produceva
   `['FR-001`', '`FR-002']` — ID corrotti, quindi nessun collegamento
   funzionante e nessun errore visibile;
2. l'annotazione `[rischio aperto: R-001]` veniva aggiunta alle Note del
   requisito e non veniva MAI rimossa alla chiusura del rischio. Le Note sono
   umane e preservate per definizione, quindi l'annotazione restava li' per
   sempre, mescolando metadato macchina e testo umano.

Nella v4 il rischio aperto e' un dato calcolato ad ogni refresh e reso in una
colonna propria della Dashboard: non viene mai scritto nelle Note. Il campo
Note torna a essere esclusivamente umano.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .mdparse import parse_document, read_text

OPEN_STATES = ("aperto", "open")


def strip_backticks(value: str) -> str:
    """Rimuove i backtick di formattazione da un singolo token.

    Opera su un token gia' separato, mai su una lista intera: e' esattamente
    l'inversione dell'ordine sbagliato che causava il difetto della v3.
    """
    v = (value or "").strip()
    while len(v) >= 2 and v.startswith("`") and v.endswith("`"):
        v = v[1:-1].strip()
    return "" if v in ("—", "-", "n/a", "N/A") else v


def parse_id_list(cell: str) -> list[str]:
    """Estrae una lista di ID da una cella, separando PRIMA di ripulire.

        "`FR-001`, `FR-002`"  ->  ["FR-001", "FR-002"]

    La v3 faceva il contrario e otteneva ["FR-001`", "`FR-002"].
    """
    if not cell:
        return []
    out: list[str] = []
    for token in cell.replace(";", ",").split(","):
        cleaned = strip_backticks(token)
        if cleaned:
            out.append(cleaned)
    return out


@dataclass
class OpenRisk:
    risk_id: str
    description: str
    probability: str = ""
    impact: str = ""
    response: str = ""
    owner: str = ""
    linked_requirement_ids: list[str] = field(default_factory=list)


def read_open_risks(feature_dir: Path) -> list[OpenRisk]:
    """Legge `risk-register.md` in sola lettura. Non lo modifica mai."""
    risk_file = feature_dir / "risk-register.md"
    if not risk_file.exists():
        return []

    doc = parse_document(read_text(risk_file))
    parsed = doc.find_table("Rischi") or doc.find_table("Risks")
    if parsed is None:
        return []
    _, rows = parsed

    def get(row: dict, *names: str) -> str:
        for n in names:
            for key in row:
                if key.strip().lower() == n.strip().lower():
                    return strip_backticks(row[key])
        return ""

    risks: list[OpenRisk] = []
    for row in rows:
        state = get(row, "Stato", "Status").lower()
        if state not in OPEN_STATES:
            continue
        risks.append(
            OpenRisk(
                risk_id=get(row, "Risk ID", "ID"),
                description=get(row, "Descrizione", "Description"),
                probability=get(row, "Probabilità", "Probabilita", "Probability"),
                impact=get(row, "Impatto", "Impact"),
                response=get(row, "Risposta", "Response"),
                owner=get(row, "Owner", "Risk Owner"),
                linked_requirement_ids=parse_id_list(
                    get(row, "Requisiti collegati", "Linked Requirements", "Requirements")
                ),
            )
        )
    return risks
