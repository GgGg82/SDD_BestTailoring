# Classifica dei miglioramenti — dal più al meno promettente

**Baseline:** v4.0.0-beta.1, verificata sui file reali di `repo-bundle-v4/`
**Data:** 2026-08-06
**Scopo:** decidere uno per uno cosa implementare. Nessuna voce è stata implementata.

---

## Come leggere la classifica

**Criterio di ordinamento:** rapporto tra valore e impegno, corretto per l'indipendenza dalle altre voci e per la compatibilità con le decisioni già congelate nella v4. Non è ordinamento per solo impatto: per un framework il cui problema aperto dichiarato è il costo, ordinare per impatto senza guardare l'impegno è stato l'errore delle stesure precedenti.

**Scala di impegno.** Il vero discriminante è se la voce tocca l'engine: la v4 ha 76 test automatici e 89% di copertura, quindi ogni modifica al codice porta con sé test da scrivere e regressioni da evitare. Una modifica a un prompt no.

| | Significato |
|---|---|
| **XS** | Testo in un file esistente. Nessun codice, nessun test. |
| **S** | Uno o due file nuovi di documentazione/prompt, più un rimando in `CLAUDE.md`. |
| **M** | Modifica a più file agente **oppure** estensione contenuta dell'engine con i suoi test. |
| **L** | Nuovo comando CLI o nuovo campo che attraversa parser, store, render e gate, con test. |
| **XL** | Cambia agenti, artefatti, gate ed engine insieme. Richiede bump di versione. |

**Legenda dello stato:** 🟢 pronta da implementare · 🟡 richiede una decisione preliminare · 🔴 richiede una verifica tecnica o una riprogettazione.

---

## Quadro d'insieme

| # | Miglioramento | Valore | Impegno | Stato | Dipendenze |
|---|---|---|---|---|---|
| 1 | Corner-case sweep obbligatorio in `clarify` | Alto | S | 🟢 | Nessuna |
| 2 | Criterio di coerenza multi-punto in `SCALE-ADAPTIVE-FLOW` | Medio | XS | 🟢 | Nessuna |
| 3 | `AGENTS.md` + `PROJECT-STATE.md` generato | Alto | M | 🟡 | Referenzia #4 |
| 4 | Registro delle decisioni di processo | Medio | S | 🟡 | Nessuna |
| 5 | Prioritizzazione dei requisiti a doppio asse | Medio-alto | L | 🔴 | Alza il valore di #6 |
| 6 | `burnup forecast` | Medio | L | 🟡 | Beneficia di #5 |
| 7 | FMEA completa | Alto (potenziale) | XL | 🔴 | #1 ne è già estratto |
| — | Escalation spot di modello | Medio | ? | 🔴 | Verifica tecnica bloccante |
| — | Riduzione del costo degli agent-hop | Alto | ? | 🔴 | Nessuna proposta esiste ancora |
| — | Migrazione delle feature v3 → v4 | Situazionale | ? | 🔴 | Serve solo se esistono feature v3 aperte |

---

## 1 · Corner-case sweep obbligatorio in `/speckit.clarify`

**Cosa fa.** Rende obbligatoria, nello step 1.2, una lista di categorie di condizione limite da attraversare prima di chiudere il clarify: input nulli/vuoti/estremi/malformati, concorrenza, timeout e partial failure, permessi e ruoli, dati incoerenti o obsoleti, perdita di connettività, limiti di volume, timezone e precisione numerica, errori umani e sequenze fuori ordine, stato iniziale/finale/recovery, comportamento degradato, casi rari ad alta severità. I casi che definiscono comportamento atteso diventano requisiti in `spec.md`.

**Valore: alto.** È l'unico intervento che alza la qualità della spec *nel punto in cui il framework poi misura*. Un requisito che non è stato scritto non compare in nessuna metrica: il Burn-up può dire con precisione che il 100% dei requisiti è `tested` e non accorgersi che manca il requisito giusto. Questo intervento attacca proprio quel punto cieco, ed è a monte di tutto il resto.

**Impegno: S.** Una sezione nel prompt di `@business-analyst-qa` più un riferimento in `CLAUDE.md`. Nessun agente nuovo, nessun artefatto nuovo, nessuna riga di Python, nessun test.

**Vantaggi**

- Rapporto valore/impegno migliore di qualunque altra voce.
- Zero conflitti: non tocca gate, engine, ownership né numerazione degli step.
- Si aggancia a qualcosa che esiste già — la classe High-Risk richiede "scenari negativi espliciti", oggi senza una lista che dica quali.
- Recupera il pezzo migliore del change proposal FMEA senza pagarne il costo.

**Svantaggi e rischi**

- Allunga lo step 1.2 e quindi il tempo fino al Gate 1. Mitigabile modulando la lista per classe di change: completa su High-Risk, ridotta su Standard, saltabile su Fast Track.
- Rischio di degenerare in checklist a timbro ("nessun caso applicabile" ripetuto). Va richiesta una risposta esplicita per categoria, non un `PASS` complessivo.
- Il Product Manager riceverà più domande: è il costo voluto, ma va detto.

**Decisioni da prendere:** quali categorie sono obbligatorie per classe di change; se le risposte "non applicabile" vanno tracciate in `spec.md` o solo nel clarify.

---

## 2 · Criterio di coerenza multi-punto in `SCALE-ADAPTIVE-FLOW`

**Cosa fa.** Innesta nella domanda 7 delle classi di change (*"tocca più di due requisiti esistenti?"*) la formulazione raffinata sopravvissuta alla proposta sul percorso snello: quello che conta non è quanti file la modifica tocca né quanto sono importanti, ma **quante cose devono restare coerenti tra loro dopo la modifica**.

**Valore: medio.** Corregge un falso positivo reale, già validato su un caso concreto: aggiungere un log diagnostico dentro un file centrale non richiede alcun coordinamento multi-punto, ma con una formulazione basata sull'importanza del file finirebbe in classe superiore. Dato che in caso di dubbio la regola v4 impone di salire, formulazioni imprecise costano artefatti veri.

**Impegno: XS.** Un paragrafo in un documento normativo esistente.

**Vantaggi**

- Costo quasi nullo, effetto su ogni feature futura.
- Rende esplicito un ragionamento già fatto e già stress-testato, invece di lasciarlo morire con la proposta superata.

**Svantaggi e rischi**

- Resta un criterio di giudizio, non una regola meccanica: sposta la soggettività, non la elimina.
- Chi decide è l'Orchestratore, che è la sessione principale e non un agente specialistico. Se in futuro si volesse davvero renderlo deterministico, servirebbe un'analisi delle dipendenze che oggi non esiste.

**Decisioni da prendere:** nessuna. È un chiarimento redazionale.

---

## 3 · `AGENTS.md` + `PROJECT-STATE.md` generato

**Cosa fa.** `AGENTS.md` alla radice come ancora tool-agnostica, letta automaticamente da Codex CLI e da altri strumenti che seguono quello standard, con le regole minime valide anche senza meccanismo di subagent. `PROJECT-STATE.md` come stato corrente del progetto — con le sezioni "feature attiva / fase / gate" **generate da `burnup gate status`**, non scritte a mano.

**Valore: alto.** È l'unica voce che non è un'ottimizzazione ma una protezione da un rischio di correttezza già presente: più strumenti e più persone sullo stesso repository, con `CLAUDE.md` che segnala il problema di Codex CLI e non lo risolve. Oggi un collega che apre il repository, o una sessione Codex che parte da zero, non ha modo di sapere qual è la feature attiva e a che punto è senza sapere prima quale cartella aprire.

**Impegno: M.** `AGENTS.md` è scrittura pura. La parte generata di `PROJECT-STATE.md` richiede un piccolo renderer che legga il canonical store — poco codice, ma codice, quindi con i suoi test.

**Vantaggi**

- La generazione elimina alla radice il rischio principale che la proposta stessa identificava: uno stato non aggiornato è peggio di uno stato assente.
- Coerente con il principio v4 già consolidato: il Markdown è una proiezione rigenerabile.
- Elimina anche il rischio di conflitti Git sul file, perché la parte volatile non è scritta a mano.
- `AGENTS.md` è uno standard aperto e adottato: il beneficio non è legato a un singolo strumento.

**Svantaggi e rischi**

- Due file alla radice che possono divergere da `CLAUDE.md` se qualcuno vi duplica contenuto. La proposta lo previene già con la regola "puntatori, non contenuto".
- La parte scritta a mano — "ultimo evento significativo", "decisioni in attesa dell'utente" — resta soggetta a staleness. Va tenuta minima, o dichiarata esplicitamente come non autorevole.
- Uno strumento che legge `AGENTS.md` non ha i sei agenti isolati: le regole minime vanno scritte sapendo che chi le legge non può eseguire il processo completo. C'è un rischio di falsa sicurezza da gestire con onestà nel testo.

**Decisioni da prendere:** quali sezioni sono generate e quali scritte a mano; se `AGENTS.md` debba dichiarare il framework "non eseguibile integralmente" fuori da Claude Code, invece di suggerire un equivalente approssimato.

---

## 4 · Registro delle decisioni di processo

**Cosa fa.** Una sede unica e persistente per le decisioni sulla struttura del framework — perché il Tech Lead resta separato, perché i due Checker non si accorpano, perché "backlog" e "MVP" sono stati scartati come termini — con contesto, decisione, conseguenze e alternative scartate.

**Valore: medio, ma dimostrato.** Non è un valore ipotetico: i documenti della cartella contengono già ripetutamente frasi come "già valutata e scartata, non riaprire" e "per contesto, non riaprire". Quelle avvertenze esistono perché il rischio si è già materializzato. Ogni ri-discussione da zero di una decisione già chiusa costa una sessione intera.

**Impegno: S.** Un template, una convenzione, una regola di trigger nel prompt del `@technical-auditor`, più la scrittura retroattiva delle decisioni già prese e ancora valide.

**Vantaggi**

- Costo marginale quasi nullo se l'ADR si scrive **subito**, quando il ragionamento è ancora in contesto.
- Metà dell'infrastruttura concettuale esiste già: `docs/DESIGN-DECISIONS.md` ha già il formato giusto.
- Il registro retroattivo ha valore immediato, non solo futuro: le decisioni da scrivere esistono già e sono documentate nelle proposte.

**Svantaggi e rischi**

- **Il rischio principale è la duplicazione di sede.** Se `docs/adr/` e `DESIGN-DECISIONS.md` coesistono senza un criterio esplicito, divergono — ed è lo stesso tipo di fragilità che il framework evita ovunque altrove.
- Il trigger è euristico ("discussione consultiva chiusa con esito netto"). Rischia sia falsi positivi su discussioni ancora aperte, sia silenzi su decisioni prese di sfuggita. Un comando invocabile esplicitamente dall'utente è più affidabile di un riconoscimento inferito.
- Rischio di proliferazione: senza una soglia, ogni micro-scelta diventa un ADR e il registro perde valore.

**Decisioni da prendere:** sede unica (`docs/adr/` a file immutabili, oppure una sezione di `DESIGN-DECISIONS.md`); trigger inferito o comando esplicito; soglia minima perché una decisione meriti un ADR.

---

## 5 · Prioritizzazione dei requisiti a doppio asse

**Cosa fa.** Due assi indipendenti su ogni requisito: la **criticità**, derivata automaticamente dal risk register; e la **priorità** essenziale/rimandabile, dichiarata dal Product Manager e verificata dal BA/QA con un tetto anti-inflazione. Il Technical Auditor segnala i conflitti fra i due — in particolare un "rimandabile" collegato a un rischio grave.

**Valore: medio-alto.** Il valore non sta nell'etichetta ma nel conflitto fra i due assi: è l'unico meccanismo che intercetta un giudizio di prodotto sbagliato usando un dato già raccolto per altri motivi. Abilita inoltre la domanda che serve davvero al forecast — "quando è pronto ciò che conta" invece di "quando finisce tutto".

**Impegno: L.** Tocca il template della spec, tre file agente e l'engine su tre fronti: parser, derivazione della criticità, esposizione nei filtri. Con i test.

**Vantaggi**

- L'Asse 1 non è inflazionabile: non si può marcare tutto critico senza che diventi visibilmente insostenibile in un registro già passato sotto Maker-Checker.
- Nessun agente nuovo, nessun artefatto nuovo.
- Rende il risk register una serie storica invece di una fotografia: quanti requisiti ad alta criticità sono già `tested`.
- Riusa `risk_link.py`, che già collega rischi e requisiti.

**Svantaggi e rischi**

- 🔴 **Collisione col fingerprint.** Se il tag finisce dentro la frase normativa del requisito, cambiarne la priorità ne invalida tutta l'evidenza e lo fa retrocedere da `tested`. Va risolto in progettazione, non in corsa: introdurre un difetto di misurazione sarebbe esattamente la classe di problemi che la v4 ha appena chiuso.
- 🔴 **Asse 1 mal derivato.** Ereditare la criticità (probabilità × impatto) invece della severità fa risultare non critico un requisito raro e catastrofico — cioè proprio il caso che motiva la proposta.
- **Il controllo si sposta dopo il Gate 2.** La proposta assegna la rilevazione dei conflitti allo step 2.3, che in v4 non esiste più: `analyze` gira solo allo step 3.2, dopo `tasks.md`. Un conflitto fra assi scoperto lì fa *decadere* il Gate 2 invece di precederlo. Alternativa: anticipare il controllo alla checklist di piano dello step 2.2, che però è del BA/QA e non dell'Auditor.
- La soglia del tetto (~60%) è dichiaratamente arbitraria e va calibrata sull'uso reale.
- Il costo è concentrato nell'engine, dove è più alto.

**Decisioni da prendere:** dove vive il tag senza toccare il fingerprint; severità o esposizione come sorgente dell'Asse 1; dove cade la rilevazione dei conflitti ora che lo step 2.3 non esiste; se il conflitto produce un finding bloccante o solo una segnalazione.

---

## 6 · `burnup forecast`

**Cosa fa.** Un comando separato dal refresh che espone tre orizzonti distinti: quando le feature superano il Gate 2 (pronte per l'implementazione), quando tutti i requisiti sono `implemented`, quando sono `tested`.

**Valore: medio.** Risponde a una domanda reale che oggi il sistema non sa affrontare. Ma è la voce con il ritardo intrinseco più lungo: serve uno storico minimo prima che qualunque stima sia difendibile, indipendentemente da quando la si implementa. Implementarla presto non la rende utile presto.

**Impegno: L.** Nuovo comando, lettura dello storico, logica statistica, formattazione, test. Il Gate Decision Record ha però già eliminato la parte che la proposta stimava più costosa: la data di superamento del Gate 2 è già registrata con approvatore e fingerprint.

**Vantaggi**

- Costo computazionale trascurabile: gira su dati già presenti, con codice deterministico e non con inferenza del modello.
- Tenerlo fuori dal refresh automatico è la scelta giusta: il refresh risponde a "dove siamo", il forecast a "quando finiamo", e sono domande che interessano in momenti diversi.
- La Linea A (soglia Gate 2) è la più utile delle tre ed è ora quasi gratuita.

**Svantaggi e rischi**

- 🔴 **La statistica è il punto debole, non l'infrastruttura.** Con poche feature un fit di trend è rumore che oscilla a ogni refresh. Esporre il throughput osservato con intervallo min–max e numero di punti è più onesto di una data proiettata.
- Il denominatore non è fisso: i requisiti possono crescere in corsa. Una proiezione che lo ignora crea falsa sicurezza sul processo.
- Rischio di uso improprio: una stima presentata come data diventa un impegno, anche quando è dichiarata probabilistica.
- Il valore pieno arriva solo dopo la voce #5, che permette di filtrare sul sottoinsieme essenziale.

**Decisioni da prendere:** proiezione o throughput osservato; soglia minima di punti sotto la quale il comando rifiuta di rispondere; se il forecast entra o no nella dashboard generata.

---

## 7 · FMEA completa

**Cosa fa.** Analisi preventiva sistematica dei modi di fallimento, in due passaggi — funzionale prima del piano, tecnica dopo — con failure mode, cause, effetti, controlli preventivi e di rilevazione, azioni tracciate fino a task, test ed evidenze, e review del rischio residuo ai Gate.

**Valore: alto in potenziale.** È l'unico intervento che porterebbe nel framework una disciplina preventiva vera, distinta sia dalla gestione delle incertezze (risk register) sia dalla disambiguazione dei requisiti (clarify). Il documento che la propone è metodologicamente il più solido della cartella.

**Impegno: XL.** Tocca agenti, artefatti, gate, engine e numero di versione insieme. È l'unica voce che da sola giustificherebbe una major release.

**Vantaggi**

- Copre un vuoto reale: oggi nulla nel framework analizza sistematicamente *come una funzione può fallire*.
- Il metodo è già corretto nel documento: bidirezionalità con il risk register, severity override, divieto di false traceability, non-obiettivi espliciti.
- Applicabile anche a deliverable non software, coerentemente con la genericizzazione totale già fatta nella v4.

**Svantaggi e rischi**

- 🔴 **Contraddice una decisione già presa** ("nessun settimo agente") e **un principio già consolidato** ("il Markdown non è il database"). Non è un dettaglio implementativo: sono due scelte che l'utente ha preso esplicitamente il 31 luglio.
- 🔴 **Criteri Gate in prosa.** In v4 i gate sono una state machine con exit code. Criteri scritti solo in linguaggio naturale non sono enforceable — è il difetto P0-10, già chiuso.
- Peggiora il costo degli agent-hop, che è il problema aperto principale, aggiungendo circa cinque step e un interlocutore in più.
- Scoring di Occurrence e Detection senza dati di campo: il rischio è produrre numeri che sembrano misure e non lo sono.
- RPN è deprecato dallo standard di riferimento a favore della tabella Action Priority.
- Il pezzo a più alto valore — il corner-case sweep — è già estraibile separatamente (voce #1), il che riduce l'urgenza di tutto il resto.

**Decisioni da prendere:** se riaprire la decisione sul settimo agente; dove vive lo stato della FMEA (canonical store vs Markdown); come i criteri Gate diventano finding bloccanti; se il tailoring si aggancia alle classi di change esistenti; RPN o Action Priority; se il Pass A resta qualitativo.

---

## Fuori classifica — bloccate da una verifica

### Escalation spot di modello per `@software-engineer`

Il meccanismo è sensato: due rigetti consecutivi sulla stessa causa, l'orchestratore non ritenta in autonomia ma segnala all'utente e propone un rilancio con configurazione più potente, per quella singola invocazione. Il contatore si azzera se cambia la causa. La decisione di spesa resta umana.

**Perché è bloccata.** La premessa tecnica non regge: il frontmatter degli agenti espone `name`, `description`, `tools` e `model` — non esiste alcun campo `effort`. E non è verificato che si possa cambiare il modello di un subagent per una singola invocazione senza modificarne il file.

**Cosa serve prima:** stabilire cosa sia realmente modificabile a runtime. Se la risposta è "nulla", la regola va riscritta come pura segnalazione — l'orchestratore avvisa che il ciclo non converge e lascia decidere l'utente — senza promettere un'escalation automatica che il sistema non sa eseguire.

### Costo degli agent-hop

**Non esiste ancora una proposta.** È il costo principale riconosciuto del framework e il tema esplicitamente messo in coda nelle sessioni precedenti, ma nessuno dei sette documenti lo affronta: quello sulla memoria di progetto era nato proprio da lì — dall'idea di un digest condiviso per ridurre la rilettura di contesto tra agenti — ed è stato generalizzato verso la continuità cross-sessione, lasciando il problema originale scoperto. Le classi di change della v4 lo attenuano indirettamente riducendo il numero di artefatti, non lo risolvono.

È l'unica voce dove il lavoro da fare è **progettare**, non implementare.

### Migrazione delle feature v3 → v4

Nessun documento affronta cosa succede alle feature già avviate sotto la v3 quando il repository passa alla v4, in particolare al cambio di numerazione degli step e alla sostituzione del Markdown con il canonical store. Se non esistono feature v3 aperte, la voce decade; altrimenti va affrontata prima di qualunque altra.

---

## Nota di metodo

Le stime di impegno sono **relative**, non assolute: dicono quali voci costano più di altre, non quante ore costano. Non è mai stato misurato il costo reale di un intervento su questo framework, e una stima assoluta senza quel dato sarebbe una cifra inventata — lo stesso difetto che il change proposal FMEA si impone di evitare per i valori di Occurrence e Detection.
