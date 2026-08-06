---
schema_version: "2.0"
artifact: "risk-register"
feature: "NNN-nome-feature"
generated_at: "YYYY-MM-DDTHH:MM:SSZ"
---

# Risk Register — NNN-nome-feature

> Prodotto dal Business Analyst/QA nello step 2.2-risk (Gate 2), tramite intervista con l'utente.
> Vive nella cartella della feature, accanto a spec.md/plan.md/tasks.md.
> L'estensione Requirement Burn-up lo legge in **sola lettura** e non lo modifica mai.

## Rischi

| Risk ID | Descrizione | Probabilità | Impatto | Esposizione | Risposta | Owner | Trigger / Early Warning | Azione e scadenza | Contingency | Rischio residuo | Stato | Requisiti collegati | Note |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `R-001` | Esempio: dipendenza esterna fragile | media | alto | alta | mitiga | nome.cognome | latenza p95 oltre 800ms per 3 giorni | introdurre cache — 2026-08-15 | fallback a dati locali | basso | aperto | `FR-001` | — |

## Legenda

- **Probabilità / Impatto:** `basso`, `medio`, `alto`
- **Esposizione:** combinazione di probabilità e impatto, usata per l'ordinamento e per le soglie di escalation
- **Risposta (minacce):** `evita`, `mitiga`, `trasferisci`, `accetta`, `escala`
- **Risposta (opportunità):** `sfrutta`, `migliora`, `condividi`, `accetta`, `escala`
- **Owner:** chi è responsabile della risposta. Un rischio senza owner non ha una risposta, ha un'intenzione.
- **Trigger:** il segnale osservabile che indica che il rischio si sta materializzando
- **Contingency:** cosa si fa **se** il rischio si verifica comunque, distinto dall'azione di mitigazione preventiva
- **Rischio residuo:** esposizione stimata **dopo** la risposta
- **Stato:** `aperto`, `mitigato`, `accettato`, `chiuso`
- **Requisiti collegati:** campo **opzionale**. Compilalo con gli ID (es. `FR-003`) solo quando il rischio riguarda requisiti specifici. Se vuoto, il rischio conta a livello di feature — nessun collegamento inventato.

## Note d'uso

- Un rischio non si cancella mai: si aggiorna lo Stato, mantenendo la storia della decisione.
- Se la mitigazione richiede una modifica a `plan.md` (il COME), la gestisce il Solutions Architect in 2.1-loop. Se richiede una modifica a `spec.md` (il COSA), la feature torna al Gate 1.
- Gli ID nei "Requisiti collegati" possono essere separati da virgola e racchiusi in backtick: `` `FR-001`, `FR-002` ``.
