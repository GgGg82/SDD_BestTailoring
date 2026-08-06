"""Parser Markdown strutturale: heading stack, tabelle con escape corretto, BOM.

Chiude P0-05, N-03 e la parte strutturale di P0-04.

Nella v3 il writer faceva `cell.replace("|", "\\|")` mentre il parser faceva
`line.split("|")`: il round-trip perdeva dati. Verificato:

    render(["A","B"], [{"A": "alpha | beta", "B": "x"}])
    -> parse(...) == {'A': 'alpha \\', 'B': 'beta'}      # dato perso, colonne sfasate

Nella v4 il Markdown non e' piu' il database — e' una proiezione. Ma questo
modulo resta necessario per *leggere* gli artefatti nativi di Spec Kit
(spec.md, tasks.md, risk-register.md), che sono e restano Markdown scritto da
umani. Deve quindi essere corretto in lettura anche su input che non abbiamo
generato noi.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

BOM = "﻿"

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
_SEPARATOR_CELL_RE = re.compile(r"^:?-{1,}:?$")


def read_text(path) -> str:
    """Legge un file di testo normalizzando newline e BOM.

    `Path.read_text()` gia' traduce i newline (motivo per cui il finding
    P1-08 dell'audit sul CRLF non si riproduceva nel percorso reale), ma NON
    rimuove il BOM: un file UTF-8 con BOM faceva fallire il match del
    frontmatter, che iniziava con `\\ufeff---` invece che con `---`.
    Verificato sulla v3: `frontmatter: {}`.
    """
    with open(path, "r", encoding="utf-8-sig", newline=None) as f:
        text = f.read()
    return text.lstrip(BOM)


def split_frontmatter(text: str) -> tuple[str, str]:
    """Ritorna (frontmatter grezzo, body). Frontmatter vuoto se assente."""
    text = text.lstrip(BOM)
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


# --------------------------------------------------------------------------
# Celle di tabella: escape e unescape simmetrici
# --------------------------------------------------------------------------

def escape_cell(value: str) -> str:
    """Prepara un valore per una cella di tabella Markdown.

    L'ordine conta: prima il backslash, poi il pipe. Invertendolo, `a\\|b`
    diventerebbe `a\\\\|b` e il parser lo rileggerebbe come due celle.
    I newline interni diventano `<br>`: una cella Markdown non puo' contenerli.

    **Contratto esplicito:** il valore viene normalizzato con `strip()`. Il
    formato tabella non puo' conservare la spaziatura ai bordi di una cella,
    perche' il parser deve poter ignorare il padding di allineamento. Senza
    questa normalizzazione il round-trip sarebbe asimmetrico — uno spazio
    finale andrebbe perso, ma un a-capo finale sopravviverebbe convertito in
    `<br>`. Un property test ha reso evidente l'incoerenza.
    """
    if value is None:
        return ""
    s = str(value).strip()
    s = s.replace("\\", "\\\\")
    s = s.replace("|", "\\|")
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return s


def unescape_cell(value: str) -> str:
    """Inverso esatto di `escape_cell`.

    Scansione carattere per carattere invece di due `replace` in sequenza:
    con i replace, `\\\\|` (backslash letterale seguito da separatore) non
    sarebbe distinguibile da `\\|` (pipe escapato).
    """
    if not value:
        return ""
    out: list[str] = []
    i = 0
    n = len(value)
    while i < n:
        ch = value[i]
        if ch == "\\" and i + 1 < n:
            nxt = value[i + 1]
            if nxt in ("\\", "|"):
                out.append(nxt)
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out).replace("<br>", "\n")


def split_row(line: str) -> list[str]:
    """Divide una riga di tabella sui soli pipe NON escapati.

    I backtick vengono deliberatamente ignorati. E' una decisione, non una
    semplificazione: GFM impone che un pipe destinato al contenuto di una
    cella sia escapato con backslash **anche dentro un code span**, quindi un
    pipe non escapato e' sempre e solo un separatore.

    Un primo tentativo di implementazione trattava i backtick come delimitatori
    di code span, e un property test su 2000 casi generati lo ha demolito: con
    un numero dispari di backtick nella riga lo stato "dentro il code span"
    non si chiudeva piu' e i separatori successivi venivano inghiottiti,
    collassando due celle in una (593 fallimenti su 2000). La regola semplice
    e conforme alla specifica e' anche l'unica corretta.
    """
    s = line.strip()
    cells: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(s)

    # Un pipe iniziale/finale delimita la tabella e non introduce celle vuote.
    if s.startswith("|"):
        i = 1
    end = n
    if s.endswith("|") and not s.endswith("\\|") and end > i:
        end = n - 1

    while i < end:
        ch = s[i]
        if ch == "\\" and i + 1 < end:
            buf.append(ch)
            buf.append(s[i + 1])
            i += 2
            continue
        if ch == "|":
            cells.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1

    cells.append("".join(buf).strip())
    return cells


def is_separator_row(cells: list[str]) -> bool:
    non_empty = [c.strip() for c in cells if c.strip()]
    return bool(non_empty) and all(_SEPARATOR_CELL_RE.match(c) for c in non_empty)


def render_table(
    headers: list[str],
    rows: list[dict],
    align_right: set[str] | None = None,
) -> str:
    """Rende una tabella Markdown con escaping corretto e larghezza stabile."""
    align_right = align_right or set()
    sep = ["---:" if h in align_right else "---" for h in headers]
    lines = [
        "| " + " | ".join(escape_cell(h) for h in headers) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(escape_cell(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines) + "\n"


def parse_table_lines(lines: list[str]) -> tuple[list[str], list[dict]] | None:
    """Parsifica un blocco di righe che compongono una tabella."""
    table = [ln for ln in lines if ln.strip().startswith("|")]
    if len(table) < 2:
        return None
    headers = [unescape_cell(c) for c in split_row(table[0])]
    rows: list[dict] = []

    # Il separatore e' POSIZIONALE: in una tabella Markdown ce n'e' esattamente
    # uno, subito dopo l'header. Riconoscerlo dal contenuto — come faceva la
    # prima stesura — significa scartare una riga di dati legittima che
    # contenga solo trattini. Trovato da un property test: la riga di dati
    # ("-", "") veniva silenziosamente eliminata.
    data_lines = table[1:]
    if data_lines and is_separator_row(split_row(data_lines[0])):
        data_lines = data_lines[1:]

    for line in data_lines:
        cells = split_row(line)
        values = [unescape_cell(c) for c in cells]
        if len(values) < len(headers):
            values += [""] * (len(headers) - len(values))
        rows.append({headers[k]: values[k] for k in range(len(headers))})
    return headers, rows


# --------------------------------------------------------------------------
# Struttura del documento: heading stack
# --------------------------------------------------------------------------

@dataclass
class Section:
    """Una sezione del documento, con il suo percorso gerarchico completo."""

    level: int
    title: str
    path: tuple[str, ...]          # es. ("Requirements", "Functional Requirements")
    start_line: int                # 0-based, riga dell'heading
    lines: list[tuple[int, str]] = field(default_factory=list)  # (numero riga, testo)

    def text(self) -> str:
        return "\n".join(t for _, t in self.lines)

    def matches(self, *names: str) -> bool:
        """True se una qualunque componente del percorso combacia (case-insensitive)."""
        wanted = {n.strip().lower() for n in names}
        return any(p.strip().lower() in wanted for p in self.path)


@dataclass
class Document:
    frontmatter_raw: str
    body: str
    sections: list[Section]

    def sections_matching(self, *names: str) -> list[Section]:
        return [s for s in self.sections if s.matches(*names)]

    def find_table(self, heading: str) -> tuple[list[str], list[dict]] | None:
        """Prima tabella sotto un heading il cui titolo combacia esattamente."""
        for section in self.sections:
            if section.title.strip().lower() != heading.strip().lower():
                continue
            block: list[str] = []
            started = False
            for _, line in section.lines:
                if line.strip().startswith("|"):
                    started = True
                    block.append(line)
                elif started:
                    break
            parsed = parse_table_lines(block)
            if parsed:
                return parsed
        return None


def parse_document(text: str) -> Document:
    """Costruisce l'albero delle sezioni mantenendo lo heading stack.

    E' il cuore della correzione di P0-04. La v3 scorreva le righe con un solo
    `current_user_story` che veniva impostato da un heading "User Story N" e
    non veniva mai azzerato: passando a `## Requirements`, i requisiti globali
    continuavano a ereditare l'ultima user story vista. Verificato: FR-001 e
    NFR-001 sotto `## Requirements` risultavano entrambi US2.

    Qui ogni sezione conosce il proprio percorso completo, quindi
    l'appartenenza a una user story e' una proprieta' strutturale e non uno
    stato che sopravvive alla sezione in cui e' nato.
    """
    frontmatter_raw, body = split_frontmatter(text)
    lines = body.splitlines()

    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    preamble = Section(level=0, title="", path=(), start_line=0)
    current = preamble
    sections.append(preamble)

    in_fence = False
    fence_marker = ""

    for idx, line in enumerate(lines):
        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence, fence_marker = True, marker[:3]
            elif marker[:3] == fence_marker:
                in_fence, fence_marker = False, ""
            current.lines.append((idx, line))
            continue

        # Un heading dentro un blocco di codice non e' un heading: e' codice.
        if in_fence:
            current.lines.append((idx, line))
            continue

        m = _HEADING_RE.match(line)
        if not m:
            current.lines.append((idx, line))
            continue

        level = len(m.group(1))
        title = m.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        current = Section(
            level=level,
            title=title,
            path=tuple(t for _, t in stack),
            start_line=idx,
        )
        sections.append(current)

    return Document(frontmatter_raw=frontmatter_raw, body=body, sections=sections)
