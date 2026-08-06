"""
Parser/writer generico per i tre artefatti Markdown (frontmatter YAML + tabelle a pipe).

Principio guida: mai perdere dati durante un refresh. Il parser è tollerante
in lettura (spazi, celle vuote) ma lo writer è rigoroso nel produrre un
formato stabile, cella per cella, così i diff Git restano leggibili nel tempo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


@dataclass
class MarkdownDocument:
    frontmatter: dict
    body: str  # tutto il testo dopo il frontmatter, incluso


def parse_document(text: str) -> MarkdownDocument:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return MarkdownDocument(frontmatter={}, body=text)
    fm_raw = m.group(1)
    fm = yaml.safe_load(fm_raw) or {}
    body = text[m.end():]
    return MarkdownDocument(frontmatter=fm, body=body)


def render_frontmatter(fm: dict) -> str:
    dumped = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return f"---\n{dumped}---\n"


def load_document(path: Path) -> MarkdownDocument:
    return parse_document(path.read_text(encoding="utf-8"))


def _split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    # riga tipo | --- | ---: | :--- |
    return all(re.fullmatch(r":?-{2,}:?", c.strip()) is not None for c in cells if c.strip() != "")


def find_table_under_heading(body: str, heading: str) -> tuple[int, int] | None:
    """Trova (start, end) come indici di riga [inclusi] della tabella subito sotto
    un'intestazione '## heading' (o '### heading'). None se non trovata.
    Ritorna indici di RIGA (non di carattere), riferiti a body.splitlines().
    """
    lines = body.splitlines()
    heading_pattern = re.compile(r"^#{1,6}\s+" + re.escape(heading) + r"\s*$")
    start_heading = None
    for i, line in enumerate(lines):
        if heading_pattern.match(line.strip()):
            start_heading = i
            break
    if start_heading is None:
        return None

    # cerca la prima riga che comincia con '|' dopo l'intestazione
    i = start_heading + 1
    while i < len(lines) and not lines[i].strip().startswith("|"):
        if lines[i].strip().startswith("#"):
            # un'altra intestazione prima di trovare una tabella: nessuna tabella qui
            return None
        i += 1
    if i >= len(lines):
        return None
    table_start = i
    # avanza finché le righe iniziano con '|'
    j = i
    while j < len(lines) and lines[j].strip().startswith("|"):
        j += 1
    table_end = j - 1
    return table_start, table_end


def parse_table(body: str, heading: str) -> tuple[list[str], list[dict[str, str]]] | None:
    """Ritorna (headers, righe come dict) per la tabella sotto `heading`, o None se assente/vuota."""
    span = find_table_under_heading(body, heading)
    if span is None:
        return None
    start, end = span
    lines = body.splitlines()[start:end + 1]
    if len(lines) < 2:
        return None
    headers = _split_row(lines[0])
    rows: list[dict[str, str]] = []
    for line in lines[2:]:  # salta header e riga separatore
        cells = _split_row(line)
        if _is_separator_row(cells):
            continue
        if len(cells) < len(headers):
            cells = cells + [""] * (len(headers) - len(cells))
        row = {headers[k]: cells[k] for k in range(len(headers))}
        rows.append(row)
    return headers, rows


def render_table(headers: list[str], rows: list[dict[str, str]], align_right_cols: set[str] | None = None) -> str:
    align_right_cols = align_right_cols or set()
    sep_cells = []
    for h in headers:
        sep_cells.append("---:" if h in align_right_cols else "---")
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(sep_cells) + "|",
    ]
    for row in rows:
        cells = [str(row.get(h, "") or "").replace("|", r"\|") for h in headers]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def find_fenced_block_under_heading(body: str, heading: str, lang: str = "mermaid") -> tuple[int, int] | None:
    """Trova (start, end) come indici di riga [inclusi] di un blocco fenced ```lang ... ```
    che compare da qualche parte sotto un'intestazione, prima della prossima intestazione."""
    lines = body.splitlines()
    heading_pattern = re.compile(r"^#{1,6}\s+" + re.escape(heading) + r"\s*$")
    start_heading = None
    for i, line in enumerate(lines):
        if heading_pattern.match(line.strip()):
            start_heading = i
            break
    if start_heading is None:
        return None

    fence_open = re.compile(r"^```" + re.escape(lang) + r"\s*$")
    i = start_heading + 1
    fence_start = None
    while i < len(lines):
        if lines[i].strip().startswith("#") and re.match(r"^#{1,6}\s", lines[i].strip()):
            return None  # prossima intestazione raggiunta senza trovare il blocco
        if fence_open.match(lines[i].strip()):
            fence_start = i
            break
        i += 1
    if fence_start is None:
        return None

    j = fence_start + 1
    while j < len(lines) and lines[j].strip() != "```":
        j += 1
    if j >= len(lines):
        return None
    return fence_start, j


def replace_fenced_block(body: str, heading: str, new_block_text: str, lang: str = "mermaid") -> str:
    """Sostituisce l'intero blocco ```lang ... ``` (fence incluso) con new_block_text,
    che deve già includere i delimitatori ``` propri."""
    span = find_fenced_block_under_heading(body, heading, lang=lang)
    lines = body.splitlines()
    if span is None:
        raise ValueError(f"Blocco ```{lang} sotto '## {heading}' non trovato.")
    start, end = span
    new_lines = lines[:start] + new_block_text.rstrip("\n").split("\n") + lines[end + 1:]
    return "\n".join(new_lines) + ("\n" if body.endswith("\n") else "")


def replace_table(body: str, heading: str, new_table_md: str) -> str:
    """Sostituisce la tabella esistente sotto `heading` con new_table_md, preservando tutto
    il resto del documento (testo umano, altre sezioni, note)."""
    span = find_table_under_heading(body, heading)
    lines = body.splitlines()
    if span is None:
        raise ValueError(
            f"Sezione '## {heading}' con tabella non trovata: il file potrebbe essere "
            "malformato o non generato da questo strumento. Vedi procedura di recovery."
        )
    start, end = span
    new_lines = lines[:start] + new_table_md.rstrip("\n").split("\n") + lines[end + 1:]
    return "\n".join(new_lines) + ("\n" if body.endswith("\n") else "")
