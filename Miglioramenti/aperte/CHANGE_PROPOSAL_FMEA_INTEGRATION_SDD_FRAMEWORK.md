# Change Proposal — Integrazione FMEA nel Framework SDD Multi-Agente

> ## ⛔ NON IMPLEMENTARE COSÌ COM'È — baseline obsoleta, cinque conflitti con la v4
>
> **Baseline dichiarata dal documento:** v3 (`sdd-agenti-orchestratore-v3.zip`)
> **Baseline reale del repository:** v4.0.0-beta.1 (`repo-bundle-v4/`, 2026-07-31)
> **Verificato il:** 2026-08-06 sui file reali di `repo-bundle-v4/` e su `REMEDIATION-PLAN-v4.md`.
>
> Il documento è il più rigoroso della cartella per metodo — la distinzione fra Risk Register, FMEA e `clarify`, i due passaggi Pass A/Pass B, il divieto di false traceability, il severity override e i non-obiettivi espliciti sono tutti solidi e vanno conservati. Ma è calibrato sulla v3 e collide con la v4 in cinque punti, due dei quali sostanziali.
>
> 1. **Settimo agente.** `REMEDIATION-PLAN-v4.md` §1.1 registra una decisione esplicita dell'utente — *"Nessun settimo agente"* — con il finding P0-11 risolto allargando l'allowlist Bash del Technical Auditor. La proposta di `@risk-quality-analyst` riapre una decisione già presa: va fatto consapevolmente, non per omissione.
> 2. **`fmea.md` come database Markdown.** La sezione 13 prevede che lo script Burn-up faccia il parsing di `fmea.md`, scritto da un agente. La v4 ha appena stabilito il principio opposto per chiudere P0-05, P0-06 e P0-07: canonical store come fonte di verità, Markdown generato e mai riletto. Implementarlo come proposto reintrodurrebbe i difetti appena chiusi.
> 3. **Criteri Gate in prosa.** I criteri di Gate 1–4 sono scritti in linguaggio naturale. In v4 i gate sono una state machine (`burnup gate status|approve|reject`) con Gate Decision Record, exit code e invalidazione automatica per fingerprint. Un criterio che vive solo in prosa non è enforceable — è il difetto P0-10, già chiuso.
> 4. **Numerazione step obsoleta.** Ogni riferimento agli step 2.3, 4.2 e 4.4 e a `/speckit.analyze` segue la v3. In v4: `analyze` esiste solo a 3.2, lo step 2.3 non esiste più, 4.2 è verifica indipendente via lint/test, il collaudo è 4.5.
> 5. **Tailoring duplicato.** L'AC-17 (FMEA mandatory / lite / waived) è un secondo meccanismo di classificazione parallelo alle classi di change già esistenti in `docs/SCALE-ADAPTIVE-FLOW.md`. Vanno unificati in una sola decisione presa una volta sola: Fast Track → nessuna FMEA; Standard → FMEA lite; High-Risk → FMEA completa.
>
> **Due osservazioni di merito, indipendenti dalla versione:**
> - **RPN è deprecato.** AIAG-VDA 2019 lo ha sostituito con la tabella Action Priority, proprio perché il prodotto S×O×D è aritmeticamente instabile e induce ad ancorarsi al numero. La sezione 11 tiene entrambi e definisce solo RPN, lasciando le soglie AP fra le decisioni aperte (§21.3). Meglio eliminare RPN e definire la tabella AP.
> - **Occurrence e Detection senza dati sono il punto fragile.** Il marcatore `ASSUMPTION` è la mitigazione corretta, ma il valore reale della FMEA qui viene dalla *scoperta* dei failure mode, non dai numeri. Valutare un Pass A puramente qualitativo (solo Severity + Action Priority), rinviando O e D a quando esiste evidenza.
>
> **Da estrarre subito, separatamente.** Il **corner-case sweep obbligatorio in `/speckit.clarify`** (§4.3 e §9 step 1.2) è l'elemento a più alto rapporto valore/impegno dell'intera cartella: nessun agente nuovo, nessun artefatto nuovo, nessuna modifica all'engine, e si aggancia a ciò che la classe High-Risk già richiede ("scenari negativi espliciti"). Oggi è sepolto dentro un change proposal da 1.100 righe che ne blocca l'adozione.
>
> Dettaglio in `ANALISI-CROSS-CHECK-MIGLIORAMENTI.md`.

---

**Documento destinato a:** AI/developer responsabile dell'evoluzione del framework  
**Baseline analizzata:** `sdd-agenti-orchestratore-v3.zip` — **obsoleta, vedi banner sopra**  
**Stato originario dichiarato:** proposta funzionale e architetturale pronta per implementazione  
**Data:** 2026-08-06  
**Impatto atteso:** modifica sostanziale del workflow; raccomandato incremento di major version  

---

## 1. Executive Summary

Il framework deve essere esteso con una gestione preventiva e strutturata dei failure mode, applicabile a software, servizi e deliverable non esclusivamente software.

La modifica introduce:

1. un nuovo artefatto per-feature: `fmea.md`;
2. un nuovo agente specialistico proposto: `@risk-quality-analyst`;
3. una nuova fase preventiva dopo la definizione della `spec.md` e prima della finalizzazione della `plan.md`;
4. un'integrazione formale, senza duplicazioni, tra `risk-register.md` e `fmea.md`;
5. una ricerca obbligatoria e tracciata di corner case, edge case e failure scenario;
6. la trasformazione delle azioni FMEA in requisiti, controlli di progetto, task e test verificabili;
7. nuovi entry/exit criteria per Gate 1, Gate 2, Gate 3 e Gate 4.

La FMEA non sostituisce il Risk Register e non sostituisce `/speckit.clarify`. I tre meccanismi hanno finalità diverse e devono lavorare in modo coordinato:

- `/speckit.clarify` completa e rende non ambigua la definizione del **COSA**;
- `risk-register.md` governa le incertezze e le decisioni di risposta al rischio;
- `fmea.md` analizza preventivamente come una funzione, un servizio, un processo o una soluzione potrebbe fallire e quali controlli servono per prevenirlo o rilevarlo.

---

## 2. Verifica della baseline corrente

### 2.1 Agenti realmente presenti nella versione 3

La baseline contiene sei agenti specialistici, oltre all'Orchestratore:

| Agente | Tipo | Responsabilità primaria attuale |
|---|---|---|
| `@product-manager` | Maker | Project Brief, User Journeys, `spec.md`, risposte ai chiarimenti |
| `@solutions-architect` | Maker | setup, constitution, `plan.md`, revisioni tecniche del piano |
| `@tech-lead` | Maker | `tasks.md` |
| `@software-engineer` | Maker | implementazione e relativi test |
| `@business-analyst-qa` | Checker | clarify, checklist requisiti/piano, `risk-register.md`, collaudo funzionale |
| `@technical-auditor` | Checker | audit cross-artifact, converge, Requirement Burn-up |

L'Orchestratore non è uno dei sei agenti: è la sessione principale che governa sequenza, handoff, `progress.md` e Gate.

### 2.2 Artefatti di rischio presenti

La baseline contiene già:

- una sezione “rischi e assunzioni” nel `pre-speckit/project-brief.md`, a livello di prodotto/progetto;
- un `risk-register.md` per ogni feature;
- un template `.specify/templates/risk-register-template.md`;
- una relazione del Risk Register con il Requirement Burn-up;
- uno step `2.2-risk`, gestito da `@business-analyst-qa` mediante intervista con l'utente;
- un loop di modifica della `plan.md` quando una mitigazione riguarda il COME;
- un ritorno a Gate 1 quando una mitigazione modifica il COSA.

### 2.3 Gap della baseline

Nella versione 3 non esistono:

- `fmea.md`;
- un template FMEA;
- un agente owner della FMEA;
- uno step FMEA nel `progress.md`;
- criteri Gate specifici per failure mode e residual risk;
- regole di sincronizzazione Risk Register ↔ FMEA;
- tracciabilità FMEA → plan → tasks → test;
- un processo obbligatorio e verificabile per corner case ed edge case.

### 2.4 Incompatibilità da risolvere prima dell'implementazione

Nella baseline il `risk-register.md` viene creato allo step `2.2-risk`, cioè **dopo** che il Solutions Architect ha già prodotto `plan.md` nello step 2.1.

La decisione di usare il Risk Register come input della FMEA, e la FMEA come input della `plan.md`, non è quindi implementabile senza cambiare il workflow.

La soluzione raccomandata è rendere il Risk Register un **living artifact per-feature**, inizializzato prima del piano e aggiornato nuovamente dopo il piano quando emergono rischi tecnici o architetturali.

---

## 3. Decisioni funzionali concordate

Le seguenti decisioni costituiscono il nucleo della change request:

1. Deve esistere un nuovo artefatto per-feature denominato `fmea.md`.
2. L'artefatto deve vivere nella stessa cartella di `spec.md`, `plan.md`, `tasks.md`, `risk-register.md` e `progress.md`.
3. Deve esistere una fase FMEA esplicita tra la maturazione della specifica funzionale e la finalizzazione del piano tecnico.
4. La FMEA deve avere un owner univoco, diverso dagli autori di `spec.md`, `plan.md`, `tasks.md` e codice.
5. L'agente proposto è `@risk-quality-analyst`.
6. Il Risk Register deve alimentare la FMEA.
7. Tutti i rischi con risposta `mitiga` o `evita` devono essere presi in carico dalla FMEA oppure avere un waiver esplicito e approvato dall'utente.
8. La FMEA deve esplorare failure mode, cause, effetti, controlli preventivi, controlli di rilevazione, corner case ed edge case.
9. La FMEA completata deve essere input obbligatorio del Solutions Architect per la `plan.md`.
10. L'Orchestratore deve garantire sequenza, coinvolgimento umano, handoff e rispetto dei Gate.
11. L'utente non deve scrivere manualmente gli artefatti: risponde alle domande e approva le decisioni; gli agenti aggiornano i documenti di propria competenza.
12. Le azioni FMEA devono diventare elementi eseguibili e verificabili in `plan.md`, `tasks.md` e nei test.

---

## 4. Correzioni metodologiche necessarie

Le decisioni precedenti devono essere raffinate per evitare una implementazione formalmente ordinata ma metodologicamente debole.

### 4.1 I rischi accettati non devono essere cancellati dalla FMEA per regola assoluta

Regola minima obbligatoria:

- i rischi `mitiga` e `evita` **devono** essere valutati nella FMEA;
- i rischi `accetta` possono non generare azioni aggiuntive, ma non devono essere automaticamente esclusi quando rappresentano un failure mode rilevante, soprattutto in presenza di severity elevata;
- ogni rischio accettato rilevante deve avere motivazione, decision authority e residual risk espliciti.

L'accettazione è una risposta al rischio, non la prova che il failure mode sia irrilevante.

### 4.2 La FMEA non deve limitarsi ai rischi già presenti nel Risk Register

La FMEA è anche un processo di discovery. Può identificare failure mode, cause o impatti non ancora presenti nel Risk Register.

Pertanto la relazione deve essere bidirezionale:

- Risk Register → FMEA: fornisce rischi, priorità, risposta scelta e contesto;
- FMEA → Risk Register: restituisce nuovi rischi, residual risk, trigger, owner e necessità di risposta.

Gli owner degli artefatti restano separati; la sincronizzazione viene coordinata dall'Orchestratore.

### 4.3 Corner case ed edge case devono nascere prima di tutto in `clarify`

La FMEA non sostituisce l'analisi dei casi limite nella fase requisiti.

Regola raccomandata:

1. `/speckit.clarify` deve contenere un **mandatory corner-case sweep**;
2. i casi limite che definiscono comportamento atteso, scope o acceptance criteria devono essere scritti in `spec.md`;
3. la FMEA usa tali casi come input e può scoprirne di ulteriori;
4. ogni nuovo caso che modifica il COSA torna al Product Manager e riapre Gate 1;
5. ogni caso esclusivamente tecnico alimenta `plan.md`, `tasks.md` e test.

### 4.4 Una sola analisi pre-plan non è sufficiente per tutti i rischi tecnici

Alcuni failure mode sono individuabili dalla funzione o dal servizio prima del piano. Altri diventano visibili solo dopo aver scelto architettura, dipendenze, database, protocolli, algoritmi o deployment model.

Si raccomanda quindi una FMEA vivente con due passaggi:

- **Pass A — Functional/Service FMEA:** dopo la spec e prima del piano;
- **Pass B — Technical/Design FMEA Update:** dopo la prima bozza di `plan.md` e prima dell'approvazione di Gate 2.

Non sono due file diversi: sono due revisioni dello stesso `fmea.md`.

---

## 5. Scopo della FMEA nel framework

La FMEA deve essere domain-neutral e applicabile a:

- applicazioni software;
- API e servizi cloud;
- automazioni e agenti AI;
- processi operativi;
- servizi erogati a clienti o utenti interni;
- prodotti digitali;
- deliverable documentali o configurazioni critiche;
- soluzioni miste software/hardware, quando presenti.

### 5.1 Oggetto dell'analisi

L'unità di analisi non è necessariamente un componente fisico. Può essere:

- una funzione;
- un requisito;
- una user story;
- uno step di user journey;
- un processo;
- un'interfaccia;
- un'integrazione;
- una decisione o trasformazione dati;
- una funzione AI;
- un controllo;
- un'operazione manuale;
- un handoff tra sistemi o persone.

### 5.2 Domande guida

Per ogni funzione o step rilevante l'agente deve esplorare almeno:

- In che modo può non funzionare?
- In che modo può produrre un risultato errato, incompleto, ritardato o non rilevato?
- Quale effetto avrebbe sull'utente, sul business, sui dati, sulla sicurezza o sulla compliance?
- Quali cause possono generare il failure mode?
- Quali corner case o condizioni limite lo possono attivare?
- Quali controlli esistono già per prevenirlo?
- Quali controlli esistono già per rilevarlo prima dell'effetto finale?
- Quale azione riduce il rischio?
- Come sarà verificato che l'azione sia stata implementata ed efficace?

---

## 6. Nuovo agente proposto

### 6.1 Nome

`@risk-quality-analyst`

Nome visualizzato consigliato: **Risk & Quality Analyst**.

### 6.2 Classificazione

Agente **[CHECKER / ANALYST]** con funzione preventiva.

Non è Maker di prodotto e non deve scrivere:

- `spec.md`;
- `plan.md`;
- `tasks.md`;
- codice applicativo.

### 6.3 Artefatto di proprietà

L'agente è owner esclusivo di:

- `fmea.md`;
- eventuali report di FMEA review o delta review.

Non è owner di `risk-register.md`, che rimane di `@business-analyst-qa`.

### 6.4 Responsabilità

1. Leggere Project Brief, User Journeys, `spec.md`, checklist requisiti e Risk Register.
2. Condurre l'intervista FMEA mediata dall'Orchestratore.
3. Identificare failure mode, effetti, cause e controlli.
4. Verificare che i corner/edge case rilevanti siano coperti.
5. Valutare Severity, Occurrence e Detection con motivazione e livello di confidenza.
6. Definire la priorità di azione.
7. Proporre prevention controls, detection controls e recommended actions.
8. Collegare ogni riga a requirement ID, risk ID, acceptance criterion e, quando disponibili, test ID.
9. Segnalare all'Orchestratore ogni modifica necessaria al COSA o al COME.
10. Aggiornare la FMEA dopo la prima `plan.md` per includere failure mode tecnici o architetturali.
11. Verificare residual risk e chiusura delle azioni prima dei Gate applicabili.
12. Non approvare mai un residual risk al posto dell'utente.

### 6.5 Potere di blocco

L'agente deve emettere FAIL/NOT READY quando:

- esiste un failure mode ad alta severity senza risposta o motivazione;
- un rischio `mitiga`/`evita` non è collegato a una riga FMEA e non ha waiver;
- una recommended action non ha owner o verification method;
- la FMEA scopre una lacuna del COSA non recepita in `spec.md`;
- la FMEA scopre una lacuna del COME non recepita in `plan.md`;
- il residual risk supera la soglia definita e non è stato esplicitamente accettato dall'utente;
- i valori S/O/D sono inventati senza evidenza o dichiarazione di assunzione.

---

## 7. Modello di interazione umano–agenti

### 7.1 Single front door

L'Orchestratore rimane l'unico punto di contatto e il process owner.

Il nuovo agente non deve instaurare flussi autonomi con gli altri agenti. Il modello resta:

1. l'Orchestratore invoca `@risk-quality-analyst`;
2. l'agente legge gli artefatti disponibili;
3. l'agente prepara domande mirate;
4. l'Orchestratore presenta le domande all'utente;
5. l'utente risponde a voce o in chat, senza modificare file;
6. l'Orchestratore inoltra le risposte all'agente;
7. l'agente aggiorna `fmea.md`;
8. l'agente restituisce esito, gap, richieste di modifica e readiness;
9. l'Orchestratore instrada ogni modifica all'owner corretto.

È quindi un dialogo logicamente a tre — utente, Orchestratore e Risk & Quality Analyst — ma operativamente mediato dall'Orchestratore.

### 7.2 Decision authority

L'utente umano mantiene la decision authority su:

- risposta al rischio;
- accettazione del residual risk;
- eventuali waiver;
- modifica di scope o acceptance criteria;
- approvazione dei Gate.

L'agente propone e documenta; non approva al posto dell'utente.

---

## 8. Relazione tra Project Brief, Risk Register e FMEA

### 8.1 Project Brief

Contiene rischi e assunzioni preliminari a livello di progetto/prodotto.

Caratteristiche:

- una tantum;
- livello alto;
- non specifico di ogni failure mode;
- input per le feature future;
- owner: `@product-manager`.

### 8.2 Risk Register per-feature

Contiene eventi incerti e decisioni di gestione.

Deve includere almeno:

- Risk ID;
- cause/event/effect statement;
- probabilità;
- impatto;
- risposta (`accetta`, `mitiga`, `evita`);
- stato;
- owner;
- trigger;
- requisiti collegati;
- residual risk;
- collegamenti a FMEA ID;
- decisione/approvazione umana.

Owner: `@business-analyst-qa`.

### 8.3 FMEA per-feature

Contiene analisi preventiva dei possibili modi di fallimento.

Caratteristiche:

- orientata a funzione/processo/servizio/design;
- più granulare del Risk Register;
- identifica cause, effetti e controlli;
- genera azioni verificabili;
- vive e viene revisionata durante il ciclo della feature;
- owner: `@risk-quality-analyst`.

### 8.4 Regole di mapping

- Un Risk ID può collegarsi a più FMEA ID.
- Un FMEA ID può contribuire a più Risk ID.
- Non duplicare descrizioni complete tra i due file: usare ID e link relativi.
- Ogni rischio `mitiga` o `evita` deve avere almeno un FMEA ID oppure un waiver.
- Ogni nuova esposizione significativa scoperta dalla FMEA deve essere aggiunta al Risk Register.
- La chiusura di un rischio richiede evidenza dell'azione e rivalutazione del residual risk.

---

## 9. Target Workflow raccomandato

## Fase Meno Uno — Pre-Spec Kit

### Step -1.1 — Project Brief

- **Owner:** `@product-manager`
- **Output:** `pre-speckit/project-brief.md`
- **Contenuto risk-related:** rischi e assunzioni a livello progetto/prodotto.

### Step -1.2 — User Journeys

- **Owner:** `@product-manager`
- **Output:** `pre-speckit/user-journeys.md`
- **Contenuto risk-related:** percorsi, handoff, condizioni alternative e failure journey rilevanti.

---

## Fase 1 — Requisiti e Functional Risk Baseline

### Step 1.1 — Specify

- **Owner:** `@product-manager`
- **Comando:** `/speckit.specify`
- **Output:** `spec.md`.

### Step 1.2 — Clarify + Mandatory Corner-Case Sweep

- **Checker:** `@business-analyst-qa`
- **Maker delle correzioni:** `@product-manager`
- **Comando:** `/speckit.clarify`
- **Output:** `spec.md` aggiornata.

Il corner-case sweep deve coprire almeno:

- input nulli, vuoti, estremi, duplicati o malformati;
- concorrenza e race condition, se applicabili;
- timeout, retry, partial failure e dipendenze indisponibili;
- permessi, ruoli e accessi non autorizzati;
- dati incoerenti, obsoleti o incompleti;
- perdita di connettività o ripresa dopo interruzione;
- limiti di volume, performance e capacità;
- localizzazione, timezone, date e precisione numerica;
- errori umani o sequenze operative fuori ordine;
- stato iniziale, stato finale e recovery;
- comportamento degradato e fallback;
- casi rari ma ad alta severity.

### Step 1.3 — Requirements Checklist

- **Owner:** `@business-analyst-qa`
- **Output:** `checklists/requirements.md`.

### Step 1.4 — Preliminary Feature Risk Register

- **Owner:** `@business-analyst-qa`
- **Metodo:** intervista guidata con l'utente, mediata dall'Orchestratore.
- **Output:** prima baseline di `risk-register.md`.

Questa è una modifica rispetto alla v3: il Risk Register viene inizializzato prima del piano.

### Step 1.5 — Functional/Service FMEA

- **Owner:** `@risk-quality-analyst`
- **Input:** Project Brief, User Journeys, `spec.md`, requirements checklist, preliminary Risk Register.
- **Output:** prima baseline di `fmea.md`.

### Step 1.5-loop — Requisiti corretti in base alla FMEA

Quando la FMEA identifica una lacuna del COSA:

1. Risk & Quality Analyst emette Change Request;
2. Orchestratore invoca `@product-manager`;
3. Product Manager aggiorna `spec.md`;
4. Business Analyst/QA riesegue clarify/checklist sul delta;
5. Risk & Quality Analyst aggiorna e rivalida `fmea.md`.

### Gate 1 — Requirements & Functional Risk Baseline

Gate 1 può essere approvato soltanto quando:

- `spec.md` è completa e non ambigua;
- corner-case sweep completato;
- requirements checklist PASS;
- preliminary Risk Register disponibile;
- Functional/Service FMEA disponibile;
- nessuna lacuna critica del COSA è aperta;
- eventuali residual risk pre-plan sono approvati dall'utente.

---

## Fase 2 — Piano tecnico e Technical Risk Baseline

### Step 2.1 — Plan

- **Owner:** `@solutions-architect`
- **Comando:** `/speckit.plan`
- **Input obbligatori aggiuntivi:** `risk-register.md` e `fmea.md`.
- **Output:** `plan.md`.

Il Solutions Architect deve indicare nel piano come vengono implementati:

- prevention controls;
- detection controls;
- fallback e recovery;
- mitigazioni tecniche;
- monitoring/observability;
- testability provisions;
- security e data-integrity controls;
- azioni FMEA applicabili.

### Step 2.2 — Plan Checklist

- **Owner:** `@business-analyst-qa`
- **Output:** `checklists/plan.md`.

### Step 2.2-risk — Technical Risk Register Update

- **Owner:** `@business-analyst-qa`
- **Output:** aggiornamento dello stesso `risk-register.md`.

Questo step non crea più il registro da zero. Lo arricchisce con rischi emersi dalle scelte del piano.

### Step 2.2-fmea — Technical/Design FMEA Update

- **Owner:** `@risk-quality-analyst`
- **Input:** prima `plan.md`, Plan Checklist, Risk Register aggiornato.
- **Output:** revisione dello stesso `fmea.md`.

### Step 2.1-loop — Plan Remediation

- **Owner:** `@solutions-architect`
- **Input:** finding della Plan Checklist e della Technical/Design FMEA.
- **Output:** `plan.md` aggiornata.

Se la modifica riguarda il COSA, la feature torna a Fase 1/Gate 1.

### Step 2.3 — Independent Consistency Review

- **Owner:** `@technical-auditor`
- **Scope minimo:** spec ↔ risk ↔ FMEA ↔ plan ↔ constitution.

Nota: l'implementazione deve essere allineata alla sequenza supportata dalla versione Spec Kit adottata e ai blocker già identificati nell'audit generale della v3. Non usare questo change proposal per legittimare command sequence non supportate.

### Gate 2 — Technical Plan & Risk Controls

Gate 2 può essere approvato soltanto quando:

- il piano copre tutti i requisiti;
- ogni azione FMEA applicabile ha una risposta nel piano;
- i rischi tecnici sono aggiornati;
- i failure mode tecnici sono analizzati;
- nessuna action ad alta priorità è senza owner, deliverable o verification method;
- eventuali residual risk sono esplicitamente approvati dall'utente;
- Technical Auditor emette PASS.

---

## Fase 3 — Task e Verification Planning

### Step 3.1 — Tasks

- **Owner:** `@tech-lead`
- **Comando:** `/speckit.tasks`
- **Input obbligatori:** `plan.md`, `fmea.md`, `risk-register.md`.

Ogni azione FMEA deve essere tradotta in uno o più elementi tra:

- implementation task;
- test task;
- observability task;
- fault-injection/negative-test task;
- manual verification task;
- documentation/runbook task;
- acceptance/waiver task.

I task devono riportare gli FMEA ID e Risk ID collegati.

### Step 3.2 — Independent Coverage Review

- **Owner:** `@technical-auditor`
- **Scope:** plan/FMEA/risk actions ↔ tasks/test tasks.

### Gate 3 — Implementation Readiness

Gate 3 può essere approvato soltanto quando:

- tutte le azioni obbligatorie hanno task;
- tutti i critical/high failure mode hanno verification task;
- non esistono mitigazioni “solo narrative” senza esecuzione prevista;
- ownership e dipendenze sono definite;
- la copertura è stata verificata indipendentemente.

---

## Fase 4 — Implementazione, test e validazione

### Step 4.1 — Implement

- **Owner:** `@software-engineer`
- **Comando:** `/speckit.implement`
- **Obbligo:** implementare controlli e test collegati agli FMEA ID.

### Step 4.2/4.3 — Technical Audit e Convergence

- **Owner:** `@technical-auditor`
- **Scope aggiuntivo:** verificare che i controlli dichiarati nella FMEA siano realmente implementati e che l'evidenza di test sia tracciabile.

### Step 4.4 — Functional Validation

- **Owner:** `@business-analyst-qa`
- **Parte automatica:** eseguita dall'agente o dagli strumenti previsti.
- **Parte manuale:** l'Orchestratore guida l'utente nell'esecuzione; l'utente comunica il risultato; l'agente aggiorna gli artefatti di test, senza richiedere all'utente di scrivere file.

### Step 4.4-fmea — Residual Risk Review

- **Owner:** `@risk-quality-analyst`
- **Output:** aggiornamento finale di `fmea.md` con:
  - evidenze;
  - valori post-action;
  - residual risk;
  - azioni aperte;
  - proposta di chiusura/accettazione.

### Gate 4 — Feature Acceptance

Gate 4 può essere approvato soltanto quando:

- acceptance criteria superati;
- azioni FMEA implementate e verificate;
- nessuna action critica è aperta;
- residual risk documentato;
- accettazioni/waiver approvati dall'utente;
- Risk Register e FMEA coerenti;
- Requirement Burn-up aggiornato dopo il collaudo, se attivo.

---

## 10. Struttura proposta di `fmea.md`

```markdown
---
schema_version: "1.0"
artifact: "feature-fmea"
feature: "NNN-nome-feature"
owner: "risk-quality-analyst"
status: "draft | under-review | approved | closed"
revision: 1
generated_at: "YYYY-MM-DDTHH:MM:SSZ"
last_reviewed_at: "YYYY-MM-DDTHH:MM:SSZ"
---

# FMEA — NNN-nome-feature

## 1. Scope e contesto

- Funzioni/processi inclusi:
- Funzioni/processi esclusi:
- Assunzioni:
- Fonti analizzate:
- Soglie di azione:

## 2. Scale di valutazione

### Severity
[definizioni 1–10 contestualizzate]

### Occurrence
[definizioni 1–10 basate su evidenza o assunzione dichiarata]

### Detection
[definizioni 1–10: capacità di rilevare prima dell'effetto finale]

## 3. FMEA Table

| FMEA ID | Function / Step | Requirement IDs | Risk IDs | Failure Mode | Effects | S | Causes | O | Prevention Controls | Detection Controls | D | RPN | Action Priority | Corner/Edge Scenario | Recommended Action | Action Owner | Verification Method | Target S/O/D | Residual Risk | Status |
|---|---|---|---|---|---|---:|---|---:|---|---|---:|---:|---|---|---|---|---|---|---|---|
| FMEA-001 | ... | FR-001 | R-001 | ... | ... | 9 | ... | 4 | ... | ... | 6 | 216 | High | ... | ... | ... | TEST-001 | 9/2/2 | ... | open |

## 4. Action Log

| Action ID | FMEA IDs | Description | Owner | Target Stage | Due Gate | Status | Evidence | Residual Risk Decision |
|---|---|---|---|---|---|---|---|---|

## 5. Findings that require spec changes

| Finding ID | Description | Requirement impacted | Status | Product Manager response |
|---|---|---|---|---|

## 6. Findings that require plan changes

| Finding ID | Description | Plan area | Status | Solutions Architect response |
|---|---|---|---|---|

## 7. Residual Risk Acceptance

| Decision ID | FMEA/Risk IDs | Residual risk | Rationale | Decision authority | Decision | Date |
|---|---|---|---|---|---|---|

## 8. Revision History

| Revision | Date | Stage | Author/Agent | Summary | Trigger |
|---|---|---|---|---|---|
```

---

## 11. Scoring e priorità

### 11.1 Scale

Le scale devono essere definite nel template e contestualizzate per il progetto. Non basta scrivere numeri da 1 a 10 senza criteri.

- **Severity (S):** gravità dell'effetto finale.
- **Occurrence (O):** probabilità/frequenza della causa o del failure mode.
- **Detection (D):** difficoltà di rilevare il problema prima che produca l'effetto finale; valore alto = difficile da rilevare.

### 11.2 RPN

È possibile calcolare:

`RPN = Severity × Occurrence × Detection`

L'RPN è un indicatore di supporto, non l'unica regola decisionale.

### 11.3 Severity override

Una severity elevata non deve diventare “bassa priorità” solo perché occurrence o detection sono basse.

Regola configurabile raccomandata:

- `S >= 9`: mandatory review e decisione umana;
- `Action Priority = High`: action obbligatoria o waiver;
- valori non supportati da dati: marcare `ASSUMPTION` e definire come ottenere evidenza.

### 11.4 Post-action rating

Dopo l'implementazione devono essere registrati:

- controlli realmente applicati;
- evidenze;
- O e D post-action;
- S post-action solo quando l'effetto è realmente cambiato, non automaticamente;
- residual risk;
- decisione finale.

---

## 12. Regole di tracciabilità

### 12.1 Identificatori

Usare ID univoci e stabili:

- `R-###` per Risk Register;
- `FMEA-###` per failure mode;
- `FA-###` per FMEA Action;
- requirement ID già presenti (`FR-###`, `NFR-###`, ecc.);
- `T###` o convenzione task del progetto;
- `TEST-###` per test/evidenze.

### 12.2 Catena minima

La catena minima richiesta è:

`Requirement → Risk/FMEA → Control/Action → Plan section → Task → Test/Evidence → Residual Risk Decision`

### 12.3 No false traceability

- Vietato inferire collegamenti basandosi solo su parole simili.
- I collegamenti devono essere espliciti tramite ID.
- Un ID ambiguo o duplicato deve bloccare il Gate.
- L'assenza di un link deve produrre Finding, non un collegamento inventato.

---

## 13. Aggiornamento del Requirement Burn-up e Dashboard

L'integrazione con il Requirement Burn-up è raccomandata ma deve avvenire solo dopo la correzione dei blocker identificati nell'audit della v3.

### 13.1 Nuovi indicatori proposti

Per ogni requisito:

- numero di FMEA ID collegati;
- Action Priority massima;
- numero di azioni aperte;
- residual risk status;
- test/evidenze mancanti;
- waiver presente/assente.

A livello feature:

- Critical/High FMEA open;
- azioni scadute;
- rischi accettati;
- residual risk non approvati;
- readiness per Gate 3 e Gate 4.

### 13.2 Ownership

- `@risk-quality-analyst` aggiorna `fmea.md`;
- `@business-analyst-qa` aggiorna `risk-register.md`;
- lo script Burn-up legge entrambi senza modificarli;
- `@technical-auditor` gestisce refresh/status e Finding;
- l'Orchestratore presenta lo stato all'utente.

---

## 14. Modifiche richieste ai file del framework

### 14.1 Nuovi file

1. `.claude/agents/risk-quality-analyst.md`
2. `.specify/templates/fmea-template.md`
3. eventuale documentazione `docs/fmea-workflow.md`
4. test fixture/sample feature con `fmea.md`

### 14.2 File da modificare

#### `CLAUDE.md`

- cambiare “6 agenti” in “7 agenti”;
- aggiungere il nuovo agente alla tabella;
- inserire gli step 1.4, 1.5, 1.5-loop, 2.2-fmea e 4.4-fmea;
- definire le nuove condizioni Gate;
- definire l'interazione mediata con l'utente;
- definire il routing delle change request COSA/COME;
- estendere la sezione Requirement Burn-up.

#### `.specify/templates/progress-template.md`

Aggiungere checkbox e Gate criteria per:

- preliminary Risk Register;
- corner-case sweep;
- Functional/Service FMEA;
- FMEA remediation loop;
- Technical/Design FMEA update;
- FMEA-to-task coverage;
- residual risk review.

#### `.claude/agents/business-analyst-qa.md`

- trasformare `risk-register.md` in living artifact;
- inizializzarlo in Fase 1;
- aggiornarlo in Fase 2 e Fase 4;
- sincronizzare Risk ID/FMEA ID;
- mantenere ownership esclusiva del registro;
- includere mandatory corner-case sweep in clarify.

#### `.claude/agents/product-manager.md`

- ricevere e risolvere FMEA findings che modificano il COSA;
- aggiornare `spec.md` senza inserire dettagli tecnici;
- non modificare `fmea.md`.

#### `.claude/agents/solutions-architect.md`

- leggere `fmea.md` prima di `/speckit.plan`;
- incorporare prevention/detection controls;
- gestire il technical FMEA remediation loop;
- non modificare direttamente `fmea.md`.

#### `.claude/agents/tech-lead.md`

- tradurre FMEA Action in task atomici;
- includere ID espliciti;
- creare test/verification tasks;
- segnalare azioni senza implementazione prevista.

#### `.claude/agents/software-engineer.md`

- implementare controlli e test tracciati;
- riportare evidenze e ID;
- fail-fast quando action e piano sono incoerenti.

#### `.claude/agents/technical-auditor.md`

- verificare copertura e coerenza FMEA;
- non modificare `fmea.md`;
- estendere audit e dashboard;
- bloccare false traceability e residual risk non approvati.

#### `.specify/templates/risk-register-template.md`

Aggiungere almeno:

- Risk Owner;
- Trigger;
- FMEA IDs;
- residual risk;
- decision authority;
- last review date;
- action/evidence link.

#### Requirement Burn-up tool

In una fase successiva:

- parser `fmea.md`;
- schema rigoroso;
- exact ID matching;
- Finding per azioni aperte/ambigue;
- indicatori dashboard;
- regression tests.

---

## 15. Acceptance Criteria per l'implementazione del framework

### AC-01 — Artefatto

Data una feature valida, il framework può creare `fmea.md` dal template corretto nella cartella della feature.

### AC-02 — Ownership

Solo `@risk-quality-analyst` può creare o modificare `fmea.md`; gli altri agenti presentano finding o change request.

### AC-03 — Sequenza

L'Orchestratore non può invocare la finalizzazione di `plan.md` senza Functional/Service FMEA completata o waiver esplicito previsto dal profilo di tailoring.

### AC-04 — Risk selection

Ogni rischio `mitiga` o `evita` è collegato ad almeno un FMEA ID oppure a un waiver approvato.

### AC-05 — Accepted risks

I rischi accettati ad alta severity rimangono tracciati con rationale, residual risk e approvazione umana.

### AC-06 — Discovery feedback

Un failure mode nuovo identificato dalla FMEA genera una richiesta di aggiornamento del Risk Register.

### AC-07 — COSA/COME routing

- finding sul COSA → Product Manager + riapertura Gate 1;
- finding sul COME → Solutions Architect + permanenza/riapertura Gate 2;
- finding su task → Tech Lead + riapertura Gate 3;
- finding su implementazione → Software Engineer + rework Fase 4.

### AC-08 — Corner cases

`/speckit.clarify` include un corner-case sweep obbligatorio e le risposte che definiscono comportamento entrano in `spec.md`.

### AC-09 — FMEA pass A/B

Lo stesso `fmea.md` registra una revisione Functional/Service pre-plan e una revisione Technical/Design post-plan.

### AC-10 — Task coverage

Ogni FMEA Action obbligatoria è collegata ad almeno un task e a un verification method.

### AC-11 — Gate enforcement

Gate 3 e Gate 4 falliscono in presenza di azioni High/Critical aperte senza waiver.

### AC-12 — Human authority

Nessun agente può accettare residual risk o approvare un waiver senza conferma esplicita dell'utente.

### AC-13 — No manual file editing by user

Per i test manuali e le decisioni di rischio, l'utente comunica l'esito; l'agente owner aggiorna l'artefatto.

### AC-14 — Idempotency

Rieseguire una FMEA review senza nuovi input non duplica righe, azioni, revisioni o decisioni.

### AC-15 — Traceability

Ogni collegamento usa ID esatti e verificabili; ID duplicati o riferimenti inesistenti producono FAIL.

### AC-16 — Audit trail

Ogni modifica registra revisione, data, trigger, agent/author e decisione collegata.

### AC-17 — Tailoring

Il framework consente di classificare la FMEA come:

- mandatory;
- lite;
- waived con motivazione;

ma non permette waiver silenziosi.

### AC-18 — Domain neutrality

Template e prompt non devono assumere che il deliverable sia sempre codice software.

---

## 16. Definition of Done della change request

La modifica è Done quando:

1. tutti i nuovi file e prompt sono presenti;
2. `CLAUDE.md` e `progress-template.md` rappresentano lo stesso workflow senza divergenze;
3. gli agenti hanno ownership non sovrapposte;
4. è disponibile almeno un end-to-end test su una feature software;
5. è disponibile almeno un end-to-end test su un servizio/processo non software;
6. sono testati i loop COSA, COME, task e implementazione;
7. sono testati risk acceptance e waiver;
8. sono testati FMEA update e residual risk review;
9. non è possibile superare i Gate con failure mode critici aperti;
10. documentazione, template, esempi e installazione sono aggiornati;
11. la versione è incrementata coerentemente con il breaking workflow change;
12. i blocker P0 dell'audit generale della v3 sono stati corretti o esplicitamente separati dalla release.

---

## 17. Backlog di implementazione raccomandato

### Epic F0 — Workflow design

- F0.1 Definire step ID e Gate definitivi.
- F0.2 Aggiornare `CLAUDE.md`.
- F0.3 Aggiornare `progress-template.md`.
- F0.4 Definire tailoring e waiver policy.

### Epic F1 — Agent model

- F1.1 Creare `@risk-quality-analyst`.
- F1.2 Aggiornare Business Analyst/QA.
- F1.3 Aggiornare Product Manager.
- F1.4 Aggiornare Solutions Architect.
- F1.5 Aggiornare Tech Lead.
- F1.6 Aggiornare Software Engineer.
- F1.7 Aggiornare Technical Auditor.

### Epic F2 — Artifact model

- F2.1 Creare FMEA template.
- F2.2 Estendere Risk Register template.
- F2.3 Definire ID e schema versioning.
- F2.4 Definire revision history e decision log.
- F2.5 Creare esempi software e service.

### Epic F3 — Traceability

- F3.1 Requirement ↔ Risk ↔ FMEA mapping.
- F3.2 FMEA Action ↔ Plan mapping.
- F3.3 FMEA Action ↔ Task/Test mapping.
- F3.4 Residual Risk ↔ Gate decision mapping.

### Epic F4 — Enforcement

- F4.1 Gate 1 validation.
- F4.2 Gate 2 validation.
- F4.3 Gate 3 validation.
- F4.4 Gate 4 validation.
- F4.5 Waiver validation.
- F4.6 Duplicate/missing ID validation.

### Epic F5 — Dashboard and Burn-up

- F5.1 FMEA parser.
- F5.2 Dashboard indicators.
- F5.3 Open action alerts.
- F5.4 Residual risk status.
- F5.5 Snapshot and audit trail.

### Epic F6 — Test and release

- F6.1 Unit tests.
- F6.2 Golden corpus.
- F6.3 End-to-end feature tests.
- F6.4 Cross-platform tests.
- F6.5 Migration from v3.
- F6.6 Version bump, changelog and release notes.

---

## 18. PMI-aligned alternative

In una lettura PMI, il Risk Register rimane il repository gestionale ufficiale dei rischi della feature, mentre la FMEA è una tecnica specialistica di risk identification, qualitative analysis e response planning.

Impostazione raccomandata:

- Risk Owner esplicito per ogni rischio;
- response owner per ogni azione;
- trigger e contingency/fallback;
- residual e secondary risks;
- decision log per acceptance e waiver;
- review ai Gate e durante il ciclo, non una tantum;
- tailoring proporzionato a criticality e complexity;
- escalation dei rischi fuori dall'autorità della feature al livello progetto/prodotto.

Il Risk & Quality Analyst facilita l'analisi; l'Orchestratore mantiene process governance; l'utente/sponsor conserva la risk acceptance authority.

---

## 19. Six Sigma / Operational Excellence interpretation

La FMEA deve essere trattata come controllo preventivo, non come documento amministrativo.

Principi da applicare:

- prevention over inspection;
- evidence-based scoring;
- focus sui Critical-to-Quality characteristics;
- failure-proofing e mistake-proofing dove applicabile;
- reaction plan per failure mode ad alta priorità;
- verifica dell'efficacia delle azioni, non solo del loro completamento;
- aggiornamento con lesson learned e difetti realmente osservati;
- uso dei dati post-release per ricalibrare Occurrence e Detection;
- riduzione del rischio residuo come outcome misurabile.

---

## 20. Non-obiettivi

Questa change request non deve:

- sostituire Spec Kit core;
- modificare direttamente i comandi ufficiali senza extension/preset supportato;
- trasformare la FMEA in un semplice elenco di rischi duplicato;
- fare dell'RPN l'unico criterio decisionale;
- consentire all'agente di inventare probabilità o dati;
- eliminare la responsabilità umana sulle decisioni di rischio;
- imporre lo stesso livello di FMEA a qualunque micro-feature indipendentemente dalla criticità;
- confondere test completion con residual risk acceptance.

---

## 21. Decisioni ancora da congelare durante l'implementazione

L'AI/developer deve proporre una scelta esplicita, senza assumerla silenziosamente, per:

1. nome definitivo dell'agente (`risk-quality-analyst` raccomandato);
2. scala S/O/D e definizioni contestuali;
3. soglie Action Priority;
4. policy di FMEA Lite e waiver;
5. posizione esatta del Gate 1 dopo la nuova fase;
6. nomenclatura definitiva degli step;
7. modalità di packaging: repository customization, Spec Kit extension, preset o bundle;
8. integrazione immediata o differita con Requirement Burn-up;
9. formato strutturato primario: Markdown-only oppure store strutturato con Markdown come view;
10. migration strategy per feature v3 già avviate.

Per ciascuna decisione il developer deve documentare opzioni, trade-off e raccomandazione.

---

## 22. Raccomandazione conclusiva

La FMEA è un miglioramento coerente e ad alto valore, ma non deve essere aggiunta come file isolato dopo `spec.md`.

La soluzione robusta richiede:

- Risk Register living e anticipato;
- FMEA in due passaggi;
- corner-case sweep obbligatorio in clarify;
- nuovo owner specializzato;
- routing formale COSA/COME;
- tracciabilità fino a task, test ed evidenze;
- residual risk review ai Gate;
- enforcement deterministico dove possibile.

La modifica è sufficientemente profonda da giustificare una nuova major release del framework, preferibilmente dopo la chiusura dei blocker P0 già rilevati nell'audit completo della versione 3.

---

## 23. Riferimenti metodologici

- GitHub Spec Kit — documentazione ufficiale del workflow Agentic SDD e dei comandi `specify`, `clarify`, `plan`, `tasks`, `analyze`, `implement` e `converge`.
- American Society for Quality — Failure Mode and Effects Analysis: tecnica preventiva applicabile a design, processi, prodotti e servizi.
- Project Management Institute — Standard for Risk Management in Portfolios, Programs, and Projects.
- Audit completo della baseline v3: `SDD_MULTI_AGENT_FRAMEWORK_V3_FULL_AUDIT.md`.

