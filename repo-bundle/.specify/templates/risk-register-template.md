---
schema_version: "1.0"
artifact: "risk-register"
feature: "NNN-nome-feature"
generated_at: "YYYY-MM-DDTHH:MM:SSZ"
---

# Risk Register — NNN-nome-feature

> Prodotto dalla Business Analyst/QA nello step 2.2-risk (Gate 2), tramite intervista con l'utente. Vive nella cartella della feature, accanto a spec.md/plan.md/tasks.md.

## Rischi

| Risk ID | Descrizione | Probabilità | Impatto | Risposta | Stato | Requisiti collegati | Note |
|---|---|---|---|---|---|---|---|
| `R-001` | Esempio: dipendenza esterna fragile | media | alto | mitiga | aperto | `FR-001` | — |

## Legenda

- **Probabilità / Impatto:** `basso`, `medio`, `alto`
- **Risposta:** `accetta`, `mitiga`, `evita` (mai risposte lato opportunità)
- **Stato:** `aperto` (mitigazione non ancora applicata/verificata), `mitigato` (applicata), `accettato` (nessuna azione prevista, rischio riconosciuto), `chiuso` (non più rilevante)
- **Requisiti collegati:** campo **opzionale**. Compilalo con l'ID del/i requisito/i (es. `FR-003`) quando il rischio riguarda esplicitamente uno o più requisiti specifici e non l'intera feature in generale. Se lasciato vuoto, il rischio viene considerato a livello di feature nel Governance Dashboard dell'estensione requirement-burnup (nessun collegamento inventato a un requisito specifico).

## Note d'uso

- Un rischio non si cancella mai quando viene mitigato o chiuso — si aggiorna lo Stato, mantenendo la storia della decisione.
- Se la mitigazione di un rischio richiede una modifica a `plan.md` (il COME), lo gestisce il Solutions Architect in step 2.1-loop. Se richiede una modifica a `spec.md` (il COSA), la feature torna a Gate 1 / Product Manager — vedi CLAUDE.md.
