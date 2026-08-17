## Regola: Escalation spot di modello/effort per Software Engineer

> ## ⚠️ DA RIFORMULARE — la premessa tecnica non regge sulla v4
>
> **Baseline del documento:** v3 · **Baseline reale del repository:** v4.0.0-beta.1
> **Verificato il:** 2026-08-06 sul frontmatter reale dei sei file in `repo-bundle-v4/.claude/agents/`.
>
> Due correzioni ai fatti su cui la regola poggia:
>
> 1. **Il campo `effort` non esiste.** Il frontmatter degli agenti espone `name`, `description`, `tools` e `model`. Non c'è alcun campo di effort da alzare o abbassare. Ogni riferimento a "effort basso sull'orchestratore, alto su Maker e Checker" descrive un'intenzione, non una configurazione applicabile.
> 2. **La calibrazione dei modelli esiste già**, contrariamente a quanto riportato altrove nella cartella: `opus` per `@solutions-architect` e `@technical-auditor`, `sonnet` per gli altri quattro — incluso `@software-engineer`.
>
> **Cosa resta valido:** il meccanismo. Il trigger (due rigetti consecutivi dello stesso Checker sulla stessa causa di fondo), l'azzeramento del contatore al cambio di causa, la natura spot e non permanente del cambio, e soprattutto il principio che la decisione di spesa resti dell'utente e non dell'orchestratore.
>
> **Cosa va deciso prima di implementare:** se e come sia realmente possibile cambiare modello per una singola invocazione di un subagent senza modificare il suo file. Se non lo è, la regola va riscritta come *prompt di segnalazione* — l'orchestratore avvisa che il ciclo non converge e propone all'utente di intervenire — senza promettere un'escalation automatica che il sistema non sa eseguire.
>
> Dettaglio in `ANALISI-CROSS-CHECK-MIGLIORAMENTI.md`.

---

**Contesto:** questa regola va inserita in `CLAUDE.md`, nella sezione delle regole di orchestrazione, e riguarda il solo agente `@software-engineer` (nella v3 descritto come configurato su Sonnet, effort alto — vedi banner sopra).

**Trigger**

Quando un task assegnato a `@software-engineer` viene rimandato indietro da un Checker (`@business-analyst-qa` o `@technical-auditor`) per la **seconda volta consecutiva sulla stessa causa di fondo**, l'orchestratore deve:

1. **Non ritentare in autonomia** con la stessa configurazione.
2. **Segnalare esplicitamente** all'utente umano che il ciclo Software Engineer → Checker non sta convergendo.
3. **Proporre** — non decidere da solo — di rilanciare quel task con modello ed effort aumentati (es. Opus, effort alto/max), **solo per quella singola invocazione**.

**Regola di azzeramento del contatore**

Se tra un tentativo e l'altro la causa del rigetto cambia (non è più lo stesso bug/problema), il contatore dei tentativi falliti si azzera. Questo evita falsi allarmi su bug diversi che capitano per caso in sequenza consecutiva.

**Natura del cambio: spot, non permanente**

Il cambio di modello/effort si applica **esclusivamente a quella chiamata specifica** di `@software-engineer`. Non modifica il file dell'agente (`.claude/agents/software-engineer.md`), che resta configurato sulla base di default. Il task successivo, anche se collegato, riparte automaticamente dalla configurazione standard.

**Testo suggerito per il prompt di segnalazione all'utente**

> "Il task [ID task] è stato rimandato indietro dal Checker per la seconda volta sulla stessa causa ([breve descrizione]). Vuoi che lo rilanci con un modello più potente ed effort più alto, solo per questo tentativo?"

**Razionale**

- Evita di pagare il costo di un modello più potente in modo preventivo su ogni task MQL5.
- Usa l'evidenza reale (tentativi falliti) invece di stime a priori sulla difficoltà del task.
- Mantiene la decisione di spesa nelle mani dell'utente umano, non dell'orchestratore.
- Coerente con il principio del progetto: qualità sopra velocità, ma senza sprechi non giustificati.
