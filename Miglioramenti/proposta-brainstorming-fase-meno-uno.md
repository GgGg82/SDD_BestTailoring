# Change Proposal — Step -1.0 Brainstorming, opzionale e con raccomandazione

**ID proposta:** H
**Framework di riferimento:** 4.0.0-rc.2
**Stato:** formalizzata, non implementata
**Data:** 2026-08-14
**Origine:** emersa durante il test di utilizzo reale del framework sul progetto LLM Wiki
**Riferimento esterno:** BMad Method v6, Fase di Analisi

---

## Il problema

La Fase -1 del framework consiste in due step: **-1.1 Project Brief** e **-1.2 User Journeys**. Entrambi producono un artefatto, entrambi appartengono a `@product-manager`.

L'esplorazione che li precede — la conversazione in cui si capisce che cosa si sta costruendo e perché, si scartano alternative, si scoprono vincoli — **avviene sempre**, occupa tempo reale, e produce le decisioni che i due artefatti si limitano a registrare. Ma nel framework non esiste: nessun identificativo, nessun proprietario, nessun artefatto, nessuna riga in `progress.md`.

Il framework la nomina una volta sola, e come condotta anziché come fase, nel prompt di `@product-manager`:

> «Se la richiesta è vaga, fai tu le domande giuste **prima** di scrivere la prima versione.»

**Questa è un'eccezione al modo in cui il framework tratta il dialogo ovunque altrove.** Quando il confronto conta, riceve uno step, un proprietario e un artefatto:

| Dialogo | Step | Proprietario | Artefatto |
|---|---|---|---|
| Chiarimento dei requisiti | 1.2 | `@business-analyst-qa` | aggiorna `spec.md` |
| Intervista sui rischi | 2.2-risk | `@business-analyst-qa` | `risk-register.md` |
| Intervista di configurazione | burnup-init | `@technical-auditor` | `requirement-burnup-config.yml` |
| **Esplorazione iniziale** | **—** | **—** | **—** |

Tre interviste formalizzate e una no. Non c'è una ragione documentata per l'asimmetria: sembra un'omissione, non una scelta.

**La conseguenza osservata sul campo.** Nel test sul progetto LLM Wiki, l'esplorazione ha prodotto gli otto principi della constitution, il perimetro dell'MVP, le regole di concorrenza, la scelta di non misurare nulla nella prima versione, e almeno tre decisioni poi ritrattate con motivazione. Di tutto questo, in `progress.md` non compare nulla. Le **decisioni** sopravvivono negli artefatti; il **ragionamento** che le ha prodotte — le alternative scartate e il perché — esiste solo nella cronologia di una chat.

---

## Cosa fa BMad, e perché è la referenza giusta

BMad Method v6 colloca l'esplorazione in una **Fase di Analisi** con quattro strumenti: Brainstorming, Research, Product Brief, PRFAQ. La dichiarazione di opzionalità è esplicita e accompagnata dal suo prezzo:

> *«Every tool in this phase is optional, but skipping analysis entirely means your PRD is built on assumptions instead of insight.»*

Tre elementi sono direttamente rilevanti.

**1. Il Project Brief di questo framework è già uno dei quattro strumenti BMad.** L'esito della fase di analisi è stato importato senza l'esplorazione che lo alimenta. Non si tratta quindi di aggiungere un pezzo estraneo, ma di completare un'importazione parziale.

**2. L'agente facilita, non genera.** BMad è categorico:

> *«The AI acts as coach, pulling ideas out of you through structured exercises — not generating ideas for you.»*

È il vincolo che distingue il brainstorming dalla consulenza. Un agente che produce le opzioni e le sottopone alla scelta dell'utente sta facendo una cosa utile, ma diversa: le idee restano sue, e l'utente si limita a selezionare fra alternative che qualcun altro ha delimitato.

**3. La raccomandazione è già un pattern maturo.** BMad espone una tabella situazione → strumento, e un comando di aiuto che consiglia il punto di partenza *«based on what you've already done and what you're trying to accomplish»*. Non serve inventare il meccanismo di suggerimento: serve adattarlo.

**Cosa NON importare.** BMad ha quattro strumenti e oltre sessanta tecniche di ideazione. Portarli tutti significherebbe importare un sottosistema. Questa proposta prende **un solo strumento** — il brainstorming — e lascia fuori Research, PRFAQ e il catalogo delle tecniche. Se serviranno, saranno proposte separate con la loro giustificazione.

---

## Proposta

### H-a — Esiste lo step `-1.0 Brainstorming`

| | |
|---|---|
| **Identificativo** | `-1.0` — precede `-1.1`, coerente con la numerazione esistente |
| **Proprietario** | `@product-manager` — **[MAKER]**. Nessun agente nuovo: la decisione di mantenere sei agenti è chiusa |
| **Artefatto** | `pre-speckit/brainstorming/<AAAA-MM-GG>-<tema>.md` — un documento per sessione |
| **Natura** | **Opzionale**, con raccomandazione dell'Orchestratore |
| **Ripetibilità** | Non è una tantum: si può ripetere quando serve, anche a progetto avviato |

**Il documento di sessione contiene:** tema, obiettivo e vincoli dichiarati all'apertura; le idee emerse raggruppate per tema; **le alternative considerate e scartate, con il motivo** — che è la parte che oggi si perde; le decisioni raggiunte; e ciò che resta aperto.

L'ultimo punto è quello che rende l'artefatto utile a valle e non un verbale: `-1.1` e `-1.2` sanno da dove partire, e le domande irrisolte non vanno riscoperte.

### H-b — L'agente facilita, non genera (regola operativa)

Nel prompt di `@product-manager`, lo step `-1.0` porta il vincolo BMad in forma esplicita:

> Poni domande. Non produrre l'elenco delle opzioni e non chiedere all'utente di sceglierne una. Se l'utente si blocca, offri un angolo da cui guardare il problema, non la risposta. Le idee sono sue: il tuo compito è creare le condizioni perché emergano, e registrarle fedelmente.

**Perché è una regola e non un consiglio.** Un agente che genera le opzioni delimita implicitamente lo spazio delle soluzioni: ciò che non gli è venuto in mente non viene nemmeno considerato, e l'utente non se ne accorge — sta scegliendo, quindi si sente attivo. È l'errore più difficile da rilevare a posteriori, perché il risultato *sembra* frutto di una scelta.

> **Osservazione dal test.** Durante il test sul progetto LLM Wiki l'esplorazione ha violato questa regola per l'intera durata: le opzioni sono state generate dall'agente e sottoposte all'utente in forma di scelta multipla. Il risultato è stato utile, ma è consulenza, non facilitazione. È la ragione per cui la regola va scritta nel prompt e non lasciata all'intenzione.

### H-c — L'Orchestratore raccomanda, e si espone

L'Orchestratore non presenta una scelta neutra: dichiara una raccomandazione **e il suo motivo**, perché è l'unico che ha appena letto gli artefatti esistenti.

| Ciò che l'Orchestratore osserva | Raccomandazione |
|---|---|
| Progetto nuovo, nessun Project Brief esistente | **fare** il brainstorming |
| L'utente descrive un problema ma non una soluzione | **fare** |
| Esistono più direzioni plausibili e nessuna è stata scelta | **fare** |
| La richiesta è precisa, circoscritta, e la soluzione è già decisa dall'utente | **saltare** |
| La feature ricade su passi di journey già mappati e non ne aggiunge | **saltare** |
| L'Orchestratore non ha elementi per giudicare | **fare**, dichiarando di non avere elementi |

L'ultima riga è la più importante. Una raccomandazione costruita su informazioni che non si hanno è peggio dell'assenza di raccomandazione: ha la forma di un giudizio senza esserlo. Il default in assenza di conoscenza è eseguire — coerente con l'avvertimento di BMad sul costo di saltare l'analisi.

**Anche il Product Manager contribuisce.** Se durante `-1.1` il PM constata che l'intento è vago o che le assunzioni non reggono, lo segnala all'Orchestratore, che può proporre un `-1.0` a posteriori. Lo step è ripetibile proprio per questo: la scoperta che sarebbe servito arriva spesso dopo.

### H-d — Saltare è una decisione registrata

In `progress.md` lo step risulta `saltato (motivo, attore)` — mai assente, mai spuntato.

Uno step assente si legge come dimenticanza, e alla rilettura nessuno lo distingue da un errore. Uno step spuntato mente. Uno step dichiarato saltato con il suo motivo resta leggibile fra sei mesi, ed è anche l'unica forma che permette di accorgersi che lo si salta **sempre**.

### H-e — La Fase -1 entra nella tabella delle classi di change

`docs/SCALE-ADAPTIVE-FLOW.md` scala già `plan.md`, `risk-register.md`, le checklist e i gate secondo la classe. **La Fase -1 non vi compare**, e ne risulta un'incoerenza: una correzione di refuso in Fast Track salta il piano, il risk register e due gate interi, ma deve comunque verificare le user journeys, perché `CLAUDE.md` dichiara `-1.2` obbligatorio *«anche se la feature sembra piccola»*.

Il framework scala tutto tranne l'unico step che dichiara non scalabile — dentro un documento che afferma che ciò che scala è *«il numero di artefatti e di revisioni»*. Le user journeys sono un artefatto.

| | **Fast Track** | **Standard** | **High-Risk** |
|---|---|---|---|
| `-1.0` Brainstorming | non richiesto | facoltativo, su raccomandazione | facoltativo, raccomandato |
| `-1.1` Project Brief | non richiesto se già esistente | richiesto una tantum | richiesto una tantum |
| `-1.2` User Journeys | verifica ridotta | richiesta | richiesta, con revisione degli scoperti |

**La «verifica ridotta» non è un salto.** È un controllo solo: che la feature ricada su un passo già mappato. Se non ci ricade, la verifica **fallisce** e la Fase -1 va eseguita per intero — perché il caso che quella fase esiste per intercettare, la feature che sembra piccola e non lo è, si manifesta esattamente così.

---

## Rischi

**Si salterà sempre.** Il costo dell'esplorazione è immediato e visibile; il beneficio è differito e invisibile — nessuno ringrazia il controllo che ha evitato un problema, perché quel problema non è accaduto. Mitigazioni: il default in assenza di elementi è *fare*; la verifica ridotta del Fast Track non è un salto; e gli skip sono visibili in `progress.md`, quindi una serie consecutiva è un segnale leggibile.

**Il brainstorming diventa un verbale.** Se il documento di sessione registra solo le conclusioni, non aggiunge nulla agli artefatti che già le contengono. Il suo valore sta interamente nelle **alternative scartate e nel motivo**: è l'unica informazione che nessun altro artefatto conserva.

**Circolarità, dichiarata e non risolta.** Per sapere se la feature ricade su un journey esistente bisogna aprire `user-journeys.md`, cioè fare una parte di ciò che si vorrebbe saltare. La proposta la limita — leggere una tabella invece di riscrivere un documento — ma non la elimina. Chi affermasse di poter decidere lo skip senza aprire il file starebbe indovinando.

**È l'unica proposta che rimuove un controllo.** Tutte le precedenti ne aggiungevano. Va valutata sapendolo.

---

## Punti aperti

| # | Punto | Nota |
|---|---|---|
| H1 | Il brainstorming è di `@product-manager` o serve un ruolo di facilitatore? | BMad usa un agente Analyst distinto dal PM. Qui il PM è il candidato naturale, ma facilitare e redigere sono attitudini diverse, e chi ha appena facilitato è meno adatto a mettere in dubbio ciò che ne è uscito |
| H2 | Chi verifica che lo skip fosse legittimo? | Oggi nessuno. Candidato: il Checker al Gate 1, che ha già gli artefatti sotto gli occhi |
| H3 | Interazione con la promozione di classe | Se una feature passa da Fast Track a Standard in corsa, la Fase -1 saltata va recuperata come gli altri artefatti mancanti. Da rendere esplicito |
| H4 | Il documento di sessione entra nella tracciabilità? | Oggi `pre-speckit/` è fuori dal canonical store per il vincolo del link a senso unico. Il brainstorming non farebbe eccezione, ma va detto |

---

## Impatto

- **Ampiezza:** Fase -1, tabella delle classi, prompt di `@product-manager`, `progress-template.md`.
- **Profondità:** modifica il flusso. Aggiunge uno step e rimuove un «obbligatorio» esplicito, presente in **due file** — `CLAUDE.md` e il prompt del PM — che vanno aggiornati entrambi.
- **Controlli P0:** nessun impatto. Non tocca tracciabilità, evidenza fingerprinted, test obbligatori né `refresh --strict`. Coerente con il vincolo che *«ciò che scala è il numero di artefatti, mai il rigore della misurazione»*.
- **Rischio:** medio.

---

## Fonti

- [Analysis Phase: From Idea to Foundation — BMAD Method](https://docs.bmad-method.org/explanation/analysis-phase/)
- [Brainstorming — BMAD Method](https://docs.bmad-method.org/explanation/brainstorming/)
