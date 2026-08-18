"""PROJECT-STATE.md — lo stato del progetto, generato dal canonical store.

Perche' generato e non scritto a mano
-------------------------------------
La proposta originale prevedeva un file di stato mantenuto dall'orchestratore
ai Gate, e ne riconosceva onestamente il rischio principale: un file di stato
non aggiornato e' *peggio* di non averlo, perche' da' falsa sicurezza a chi lo
legge.

Quel rischio non e' una fatalita': e' la conseguenza di collocare uno **stato**
dentro una **vista**. Il framework ha gia' preso la decisione opposta per i
gate — `D-010`, "lo stato dei gate e' calcolato, non memorizzato" — proprio
perche' un valore che qualcuno deve ricordarsi di aggiornare finisce per
mentire. Qui si applica lo stesso principio: il Markdown e' una proiezione
rigenerabile, mai un database.

Cosa cambia in pratica: nessuno deve *ricordarsi* di aggiornare qualcosa. Il
file si rigenera, e se non lo si rigenera l'intestazione dichiara da quando e'
fermo — che e' un'informazione, non un silenzio.

Il contatore di non-convergenza
-------------------------------
La regola di non-convergenza (`CLAUDE.md`) scatta al secondo rigetto
consecutivo dello stesso Checker sulla stessa causa. Tenere quel conteggio a
mano lo esporrebbe allo stesso difetto: un contatore dimenticato non fa mai
scattare la regola, e nessuno se ne accorge.

Non serve tenerlo. Il canonical store contiene gia' tutto:

* i rigetti sono Gate Decision Record con `outcome == "rejected"`, ordinabili
  per `approved_at`;
* ogni record porta `open_findings`, cioe' quali finding erano aperti in quel
  momento;
* l'identita' di un finding e' stabile per costruzione (`D-008`: l'ID deriva da
  tipo, feature e subject, e **non** dalla descrizione, perche' riformulare un
  messaggio non deve cambiare l'identita' del problema).

Il conteggio e' quindi **derivabile**, e qui viene derivato.

Limite dichiarato: copre i rigetti che passano da `burnup gate reject`. I cicli
interni a una fase — il Business Analyst che rimanda `spec.md` al Product
Manager durante l'1.2 — non producono alcun record, e per quelli il conteggio
resta un'osservazione umana. Dirlo e' meglio che lasciar credere che la
copertura sia totale.
"""

from __future__ import annotations

from collections import defaultdict

#: Numero di rigetti consecutivi sulla stessa causa oltre il quale la regola
#: di non-convergenza e' considerata scattata.
SOGLIA_NON_CONVERGENZA = 2


def streak_non_convergenza(gate_decisions: list, soglia: int = SOGLIA_NON_CONVERGENZA) -> list[dict]:
    """Rigetti consecutivi che insistono sulla stessa causa.

    Per ogni coppia (feature, gate) considera la coda di decisioni consecutive
    con esito ``rejected`` e, per ciascun finding, conta da quanti rigetti
    consecutivi compare **senza interruzione**.

    L'intersezione su tutta la coda non basterebbe: con rigetti che portano
    ``{A}``, ``{A, B}``, ``{B}`` l'intersezione e' vuota, ma gli ultimi due
    insistono su ``B`` e la regola deve scattare. Si conta quindi per singola
    causa, non per serie.

    Restituisce una lista ordinata di dizionari, uno per causa, con il conteggio
    e gli estremi utili a chi deve decidere.
    """
    per_gate: dict[tuple[str, int], list] = defaultdict(list)
    for d in gate_decisions:
        per_gate[(d.feature_id, d.gate)].append(d)

    risultati: list[dict] = []

    for (feature_id, gate), decisioni in per_gate.items():
        decisioni = sorted(decisioni, key=lambda d: (d.approved_at, d.decision_id))

        coda: list = []
        for d in reversed(decisioni):
            if d.outcome != "rejected":
                break
            coda.append(d)
        if len(coda) < soglia:
            continue
        coda.reverse()  # ordine cronologico

        cause: set[str] = set()
        for d in coda:
            cause.update(d.open_findings or [])

        for finding_id in sorted(cause):
            n = 0
            for d in reversed(coda):
                if finding_id in (d.open_findings or []):
                    n += 1
                else:
                    break
            if n < soglia:
                continue
            ultimo = coda[-1]
            risultati.append(
                {
                    "feature_id": feature_id,
                    "gate": gate,
                    "finding_id": finding_id,
                    "rigetti_consecutivi": n,
                    "ultimo_rigetto": ultimo.approved_at,
                    "ultimo_attore": ultimo.approver,
                    "ultima_motivazione": ultimo.rationale,
                }
            )

    risultati.sort(key=lambda r: (-r["rigetti_consecutivi"], r["feature_id"], r["gate"], r["finding_id"]))
    return risultati


def _riga(celle: list[str]) -> str:
    return "| " + " | ".join(celle) + " |"


def render(
    *,
    generato_il: str,
    versione_engine: str,
    features: list[dict],
    findings_aperti: list,
    streaks: list[dict],
    freschezza: str,
) -> str:
    """Compone PROJECT-STATE.md.

    ``features`` e' una lista di dizionari gia' assemblati dal chiamante, che
    possiede gli helper per fingerprint e classe di change. Tenere questo
    modulo privo di accesso al filesystem lo rende verificabile senza costruire
    un progetto finto.
    """
    out: list[str] = []
    out.append("# Stato del progetto")
    out.append("")
    out.append(
        "> **File generato. Non modificarlo a mano:** si rigenera con "
        "`burnup project-state` e ogni modifica manuale va persa al primo rigenero."
    )
    out.append(">")
    out.append(
        "> Lo stato non e' memorizzato, e' **calcolato** dal canonical store — lo stesso "
        "principio per cui lo stato dei gate non vive in `progress.md`. Un valore che "
        "qualcuno deve ricordarsi di aggiornare, prima o poi, mente."
    )
    out.append("")
    out.append(f"**Generato il:** {generato_il} · **Engine:** {versione_engine} · **Misurazione:** {freschezza}")
    out.append("")

    # ---------------- feature ----------------
    out.append("## Feature")
    out.append("")
    if not features:
        out.append("Nessuna feature nel canonical store.")
        out.append("")
    else:
        out.append(_riga(["Feature", "Classe", "Gate", "Requisiti", "Tested", "Dettaglio"]))
        out.append(_riga(["---", "---", "---", "---:", "---:", "---"]))
        for f in features:
            gate_txt = " · ".join(f"{g}:{s}" for g, s in f["gates"].items()) or "—"
            out.append(
                _riga([
                    f"`{f['feature_id']}`",
                    f["change_class"],
                    gate_txt,
                    str(f["scope"]),
                    str(f["tested"]),
                    f"`{f['progress_path']}`",
                ])
            )
        out.append("")
        out.append(
            "Legenda dei gate: `valid` approvato e ancora valido · `invalidated` decaduto "
            "perche' un artefatto a monte e' cambiato · `rejected` rifiutato · `not-approved` "
            "mai approvato."
        )
        out.append("")

    # ---------------- non-convergenza ----------------
    out.append("## Cicli che non convergono")
    out.append("")
    if not streaks:
        out.append(
            "Nessuna causa con rigetti consecutivi oltre la soglia. "
            "La regola di non-convergenza non e' scattata."
        )
        out.append("")
    else:
        out.append(
            "**La regola di non-convergenza e' scattata.** Vedi `CLAUDE.md`, sezione "
            "*Quando un ciclo non converge*: fermati, presenta all'utente le due ipotesi — "
            "puo' non farcela il Maker, oppure puo' avere torto il Checker — e non rilanciare "
            "con la stessa configurazione."
        )
        out.append("")
        out.append(_riga(["Feature", "Gate", "Causa", "Rigetti consecutivi", "Ultimo rigetto", "Attore"]))
        out.append(_riga(["---", "---:", "---", "---:", "---", "---"]))
        for s in streaks:
            out.append(
                _riga([
                    f"`{s['feature_id']}`",
                    str(s["gate"]),
                    f"`{s['finding_id']}`",
                    f"**{s['rigetti_consecutivi']}**",
                    s["ultimo_rigetto"],
                    s["ultimo_attore"],
                ])
            )
        out.append("")

    out.append(
        "> Questo conteggio e' **derivato** dai Gate Decision Record: nessuno deve tenerlo. "
        "Copre pero' i soli rigetti registrati con `burnup gate reject`. I cicli interni a una "
        "fase, che non producono un record, restano un'osservazione umana — e su quelli il "
        "rischio di non accorgersene resta intero."
    )
    out.append("")

    # ---------------- findings ----------------
    out.append("## Finding aperti")
    out.append("")
    if not findings_aperti:
        out.append("Nessun finding aperto.")
        out.append("")
    else:
        out.append(_riga(["ID", "Severita'", "Tipo", "Feature", "Aperto dal"]))
        out.append(_riga(["---", "---", "---", "---", "---"]))
        for f in findings_aperti:
            out.append(
                _riga([
                    f"`{f.finding_id}`",
                    f.severity,
                    f.finding_type,
                    f"`{f.feature_id}`" if f.feature_id else "—",
                    f.first_seen or "—",
                ])
            )
        out.append("")

    out.append("---")
    out.append("")
    out.append(
        "Il **perche'** delle decisioni non sta qui: sta in `progress.md` di ciascuna feature "
        "e nei Gate Decision Record del canonical store, che ne conservano attore, motivo e "
        "fingerprint degli artefatti approvati."
    )
    out.append("")
    return "\n".join(out)
