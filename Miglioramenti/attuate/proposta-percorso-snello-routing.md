# Proposta: Percorso Snello vs Percorso Completo — Routing per complessità del task

> ## ✅ ATTUATA — `docs/SCALE-ADAPTIVE-FLOW.md`
>
> Implementata in forma più forte di quanto proposto: tre classi invece di due percorsi, sette criteri invece di tre, promozione in corsa con retrocessione vietata dall'engine.
>
> Il pezzo da recuperare che il banner precedente segnalava — il **criterio di coerenza multi-punto** — è stato innestato nella domanda 7 in **4.0.0**, insieme alla guardia contro il criterio basato sull'importanza del file.
>
> **Nulla resta da fare.** Il documento è conservato come storia del ragionamento.

---


**Stato originario dichiarato (superato): PROPOSTA — non ancora implementata.** Attuata in 4.0.0. In stand-by su decisione esplicita dell'utente.**

**Destinatario di questo documento:** un'istanza AI (Claude Code o altro agente) incaricata in futuro di valutare e/o implementare questa modifica al framework di governance SDD a 6 agenti già esistente. Questo documento è autosufficiente: contiene contesto, razionale, criteri esatti ed esempi già validati, così da poter essere letto senza dover recuperare la cronologia delle conversazioni che lo hanno prodotto.

---

## 1. Contesto e problema che questa proposta risolve

Il framework attuale applica lo **stesso ciclo completo a 6 agenti** (Product Manager → Solutions Architect → Business Analyst/QA → Tech Lead → Software Engineer → Technical Auditor, con relativi Gate 1-4) a **qualunque task**, indipendentemente dalla sua dimensione o rischio reale.

Questo è stato un compromesso consapevole per la qualità (vedi principio guida del progetto: qualità sopra velocità), ma ha un costo in token ed hop tra agenti che non è sempre giustificato: un piccolo fix locale o un refactoring cosmetico attraversa lo stesso numero di passaggi di una feature nuova che tocca più componenti.

**Obiettivo della proposta:** introdurre un secondo percorso, più leggero, per i task a basso rischio, **senza eliminare nessun agente e senza rompere il principio Maker-Checker**. Non è un'alternativa alla struttura a 6 agenti (già valutata e confermata più volte in sessioni precedenti come da mantenere), è un routing condizionale sopra la struttura esistente.

---

## 2. Decisione architetturale collegata (per contesto, non riaprire)

Nella stessa sessione di lavoro sono state valutate e **scartate** le seguenti alternative, per completezza di contesto:

- Eliminare `@tech-lead` e riassegnarne le funzioni a `@solutions-architect` o `@software-engineer` — scartato, rischio diretto sulla qualità di `tasks.md`, fonte di evidenza per il Burn-up.
- Accorpare `@business-analyst-qa` e `@technical-auditor` — scartato, i due Checker verificano con lenti diverse (qualità/coerenza requisiti vs coerenza tecnica spec-piano-codice) in momenti diversi del ciclo.
- Accorpare `@product-manager` e `@business-analyst-qa` — scartato, romperebbe il Maker-Checker sui requisiti stessi.

**Questi accorpamenti restano fuori scope.** La proposta di questo documento è indipendente e compatibile con la struttura a 6 agenti invariata.

---

## 3. Il meccanismo: tre criteri di instradamento

L'orchestratore (`CLAUDE.md`), all'apertura di un nuovo task, valuta tre domande. **Basta una sola risposta "sì" per attivare il Percorso Completo.** Solo se tutte e tre le risposte sono "no" si attiva il Percorso Snello.

### Criterio 1 — Tracciabilità
> Il task modifica un requisito già presente nella traceability matrix del Burn-up, oppure ne introduce uno nuovo?

Se sì → Percorso Completo. Un requisito nuovo o modificato deve passare dal controllo pieno del Business Analyst/QA, non è negoziabile.

### Criterio 2 — Visibilità utente
> Il cambiamento è percepibile da chi usa il software (comportamento, output, interazione), oppure è puramente interno (es. performance, leggibilità del codice) senza alcun effetto osservabile dall'esterno?

Se il cambiamento è visibile all'utente → Percorso Completo.

### Criterio 3 — Impatto strutturale (versione raffinata, non la prima bozza)
> La modifica richiede che più file/componenti restino coerenti tra loro dopo il cambiamento (es. cambi una struttura dati e devi aggiornare chi la consuma altrove)?

**Attenzione — punto critico già identificato e corretto:** questo criterio **non va letto come "il file toccato è importante/centrale"**, ma come **"quante cose devono restare coerenti tra loro dopo la modifica"**. Un cambiamento isolato, autocontenuto, dentro un file anche centrale/importante del progetto, **non** fa scattare questo criterio, perché non c'è coerenza multi-punto da preservare. Solo un cambiamento che si propaga e richiede aggiornamenti coordinati in più punti fa scattare "sì" qui.

Questa distinzione è stata introdotta proprio perché la prima formulazione ("tocca più di un file") produceva un falso positivo su un caso di test (vedi sezione 4, Caso C).

---

## 4. Casi di validazione (già testati sul dominio RiskGuard, generalizzabili)

| Caso | Descrizione | Crit. 1 | Crit. 2 | Crit. 3 | Esito |
|---|---|---|---|---|---|
| A | Fix su un caso limite di un requisito già tracciato (es. arrotondamento collegato a un REQ esistente) | Sì | — | — | **Percorso Completo** (basta 1 sì) |
| B | Rinominare una variabile interna o estrarre una funzione duplicata in un helper condiviso, zero cambio di comportamento | No | No | No | **Percorso Snello** |
| C | Aggiungere un log diagnostico interno in un file centrale del progetto, nessun cambio di logica, nessuna propagazione ad altri file | No | No | No (con criterio raffinato) | **Percorso Snello** |

Il Caso C è quello che ha portato al raffinamento del Criterio 3: con la formulazione originale ("tocca più file / file non isolato") sarebbe finito erroneamente in Percorso Completo solo perché il file ospitante era "importante", non perché la modifica richiedesse reale coordinamento multi-punto.

---

## 5. Cosa cambia nel Percorso Snello (nessun agente eliminato)

Tutti e sei gli agenti restano attivi anche nel Percorso Snello. Cambia **l'ampiezza** di alcuni passaggi, non la loro esistenza:

- **`@solutions-architect`**: scrive un piano minimo diretto, senza il giro completo di domande di chiarimento formali previsto nel percorso pieno.
- **`@tech-lead` + `@software-engineer`**: la scomposizione in task e l'implementazione possono essere accorpate nello stesso passaggio invece di due passaggi separati.
- **`@business-analyst-qa`**: esegue una checklist minima (poche righe, verifica assenza di effetti collaterali nascosti) invece della checklist tecnica completa dello step 2.2.
- **`@technical-auditor`**: **il suo passaggio di analisi di coerenza (equivalente a `/speckit.analyze`) NON viene mai saltato, in nessun caso.** È l'unica rete di sicurezza che verifica automaticamente se un task ritenuto "piccolo" aveva in realtà un impatto non previsto. Il burnup-refresh a chiusura resta invariato in entrambi i percorsi.

**Principio guida per l'implementazione:** il Percorso Snello riduce il formalismo di alcuni step, non elimina il controllo. Nessun artefatto perde completamente il proprio Checker.

---

## 6. Cosa serve fare per implementare (checklist per l'AI incaricata)

Questa sezione è la parte operativa, per chi dovrà tradurre la proposta in modifiche reali ai file:

1. **`CLAUDE.md`**: aggiungere la logica di routing con i tre criteri della sezione 3, da valutare all'apertura di ogni nuovo task/feature, prima di invocare `@product-manager` o `@solutions-architect`. L'esito (Percorso Completo / Percorso Snello) va comunicato esplicitamente all'utente prima di procedere, non applicato in modo silenzioso.
2. **File agente `.claude/agents/solutions-architect.md`**: aggiungere una modalità "piano minimo" attivabile quando l'orchestratore segnala Percorso Snello.
3. **File agente `.claude/agents/tech-lead.md`** e **`.claude/agents/software-engineer.md`**: definire come si accorpano scomposizione e implementazione nel caso snello — valutare se serve un flag esplicito o una sezione condizionale nel file.
4. **File agente `.claude/agents/business-analyst-qa.md`**: aggiungere il template della checklist minima, distinto da quello della checklist tecnica completa già esistente.
5. **File agente `.claude/agents/technical-auditor.md`**: nessuna modifica di sostanza necessaria — confermare esplicitamente nel file che il suo passaggio si esegue sempre, indipendentemente dal percorso.
6. **Diagramma HTML** (`sdd_workflow_diagramma.html`, attualmente v4): valutare se aggiungere una rappresentazione visiva del bivio Percorso Completo/Snello dopo l'apertura del task.

**Prima di implementare**, l'AI incaricata dovrebbe far confermare esplicitamente all'utente umano (123trading) che la proposta è ancora valida e che non sono nel frattempo cambiate le decisioni architetturali della sezione 2.

---

## 7. Nota di provenienza

Questo documento nasce da una sessione di ragionamento congiunto tra l'utente (123trading) e un'istanza Claude, nell'ambito della messa a punto del framework di governance SDD a 6 agenti già completato e stabile. Non sostituisce, ma si aggiunge a: `regola-escalation-modello-effort.md` (regola separata su model/effort spot per `@software-engineer`) e al framework base (`sdd-agenti-orchestratore-v3.zip`).
