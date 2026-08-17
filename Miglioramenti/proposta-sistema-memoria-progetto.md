# Proposta: Sistema di memoria di progetto — continuità cross-sessione, cross-tool, cross-persona

> ## ✅ VALIDA — con un miglioramento reso possibile dalla v4
>
> **Baseline del documento:** v3 · **Baseline reale del repository:** v4.0.0-beta.1
> **Verificato il:** 2026-08-06 — né `AGENTS.md` né `PROJECT-STATE.md` esistono in `repo-bundle-v4/`.
>
> È l'unica proposta della cartella **interamente non coperta** dalla v4. Il contenuto resta valido così com'è scritto, con una modifica sostanziale alla sezione 5:
>
> **`PROJECT-STATE.md` va *generato*, non scritto a mano.** La proposta prevede che l'orchestratore lo aggiorni ai Gate, e riconosce onestamente (sezione 7) che il rischio principale è la staleness. La v4 offre una soluzione migliore che il documento non poteva conoscere: `burnup gate status` è già la fonte di verità deterministica sullo stato dei gate, con invalidazione automatica per confronto di fingerprint. Le sezioni "feature attiva / fase / gate" vanno quindi generate dall'engine; restano scritte a mano solo "ultimo evento significativo" e "decisioni in attesa dell'utente". Questo è anche coerente col principio architetturale v4 — *il Markdown è una proiezione rigenerabile, mai un database*.
>
> `AGENTS.md` resta invece esattamente come proposto: la "Nota su Codex CLI" in `CLAUDE.md` è ancora lì come avvertimento passivo.
>
> Dettaglio in `ANALISI-CROSS-CHECK-MIGLIORAMENTI.md`.

---

**Stato originario dichiarato: PROPOSTA — non ancora implementata nel framework.**

**Destinatario di questo documento:** un'istanza AI (Claude Code, Codex CLI, o altro strumento) incaricata in futuro di valutare e/o implementare questa modifica al framework di governance SDD a 6 agenti. Documento autosufficiente, non richiede la cronologia della conversazione che lo ha prodotto. Dove necessario, questo documento riporta **testualmente** frammenti del `CLAUDE.md` reale del progetto (recuperati e verificati, non ricostruiti a memoria), per ancorare la proposta a ciò che esiste davvero oggi nel repository.

**Documenti collegati:**
- `proposta-adr-progetto.md` — copre il **perché** delle decisioni architetturali. Questa proposta non lo tocca, lo referenzia soltanto come terzo pezzo della stessa architettura di memoria (sezione 3). Nessuna dipendenza nella direzione ADR → questa proposta: se in futuro si implementa solo l'ADR, resta perfettamente autonomo.
- Questa proposta **generalizza e formalizza** un'idea discussa ma mai scritta come documento a sé in una sessione precedente: un "digest condiviso" per ridurre il costo di rilettura tra agenti nella stessa sessione. Qui lo scope cambia da singola feature a intero progetto, perché il problema reale che motiva questa proposta è più ampio: continuità tra sessioni diverse, tra strumenti diversi, tra persone diverse — non solo tra agenti nella stessa sessione.

---

## 1. Contesto e problema

Il framework oggi è stato pensato e verificato per un solo strumento (Claude Code) e, implicitamente, un solo operatore per sessione. Il contesto d'uso reale è più ampio:

- **Più strumenti sullo stesso repository**: Claude Code e Codex CLI, usati in sessioni diverse, anche a distanza di tempo.
- **Più persone sullo stesso repository GitHub**: non solo l'utente originale, ma altri membri del team 123trading.
- **Due tipi di informazione che si perdono oggi**, in egual misura: **lo stato** (dove eravamo rimasti, cosa manca) e **il perché** (le decisioni prese e il ragionamento dietro — già indirizzato da `proposta-adr-progetto.md`).

### Il gap tecnico concreto, verificato

Claude Code e Codex CLI non condividono automaticamente le istruzioni di progetto:

- Codex CLI legge automaticamente un file **`AGENTS.md`** alla radice del repository (e in sottocartelle, con precedenza a quello più vicino alla working directory). È uno standard aperto, oggi gestito dalla Linux Foundation (Agentic AI Foundation), adottato da un numero ampio di strumenti diversi da Codex.
- Claude Code legge `AGENTS.md` **solo come fallback**, cioè solo se non trova un `CLAUDE.md`. Questo progetto **ha già un `CLAUDE.md`** corposo con tutta la logica di orchestrazione a 6 agenti — quindi Claude Code oggi ignorerebbe comunque un eventuale `AGENTS.md`, e Codex CLI ignora comunque `CLAUDE.md`, che non è un formato che riconosce.

**Punto importante: questo gap è già stato individuato onestamente dagli autori del framework**, anche se non ancora risolto. Il `CLAUDE.md` reale del progetto termina con questa sezione, riportata qui testualmente:

> ## Nota su Codex CLI
>
> Questo `CLAUDE.md` e i file in `.claude/agents/` sono meccanismi specifici di Claude Code. Se in una sessione usi Codex CLI sullo stesso repository, il meccanismo nativo di subagent isolato non è detto sia equivalente — verificalo separatamente quando arrivi a quel punto, non dare per scontato che la stessa suddivisione in 6 agenti si trasferisca automaticamente.

Questa proposta trasforma quella nota da **avvertimento passivo** ("verificalo tu quando ci arrivi") a **ponte concreto** — è la cornice giusta per leggere tutto il resto del documento: non introduciamo un problema nuovo, completiamo una soluzione a un problema già riconosciuto.

---

## 2. Perché non uno strumento di memoria sofisticato (RAG / Mem0 / Graphiti)

Sintesi per chi non ha visto la discussione che ha portato a questa proposta, così da non doverla riaprire in fase di implementazione:

Strumenti come **Mem0** (memoria semantica per-utente, vettoriale) e **Graphiti/Zep** (grafo di conoscenza temporale) risolvono un problema di forma diversa da quello di questo progetto: **volume di informazione troppo grande per stare in un contesto**, dove serve selezionare automaticamente pochi frammenti rilevanti tra migliaia. Lo stato di questo progetto — feature attiva, ultimo evento, decisioni chiave — è invece piccolo e strutturato: un file letto per intero ci sta comodamente in un contesto.

Motivi concreti dello scarto, verificati e non solo presunti:
- **Nessuna integrazione nativa**: né Codex CLI né Claude Code interrogano questi sistemi in automatico. Servirebbe costruire e mantenere un MCP server dedicato solo per fare da ponte — un progetto satellite, non una configurazione.
- **Costo e infrastruttura**: Mem0 ha un tier gratuito limitato (poi a pagamento); Graphiti richiede comunque un database a grafo sempre attivo da gestire. Entrambi vanno contro il vincolo esplicito di semplicità e gratuità di questo progetto.
- **Fragilità silenziosa**: se il servizio esterno non risponde, la sessione perde memoria senza errore visibile. Un file nel repository non può "essere giù".
- **Nessun vantaggio di audit trail**: Git offre già, gratis, `git log`/`git blame` — cronologia completa di chi ha cambiato cosa e quando. Nessuno dei due strumenti lo eguaglia nativamente.

**Soglia esplicita per riconsiderare in futuro**: se il volume di stato/decisioni accumulate cresce oltre quanto un singolo file possa contenere in modo leggibile (centinaia di ADR, mesi di log di sessione), o se emerge un bisogno di memoria *per singolo sviluppatore* invece che di progetto condiviso, vale la pena rivalutare. Non è uno scarto definitivo, è un "non ancora, non a questo volume".

---

## 3. Architettura proposta — tre pezzi con nature diverse

Il punto di design più importante: la "memoria di progetto" **non è un solo artefatto**, sono tre pezzi con cicli di vita opposti. Fonderli in un solo documento abbasserebbe la qualità di ciascuno.

| Pezzo | Risponde a | Ciclo di vita | Stato |
|---|---|---|---|
| **`AGENTS.md`** | Chi legge questo repo, con quale strumento? | Aggiornato raramente, quando cambiano le convenzioni cross-tool | Nuovo — oggetto di questa proposta |
| **`PROJECT-STATE.md`** | Dove eravamo rimasti? | **Sempre sovrascritto**, aggiornato ad ogni Gate/sessione significativa | Nuovo — oggetto di questa proposta |
| **`docs/adr/`** | Perché abbiamo deciso così? | **Mai sovrascritto**, un file immutabile per decisione | Già proposto in `proposta-adr-progetto.md`, non toccato qui |

Le sezioni 4 e 5 dettagliano i due pezzi nuovi. Per il terzo, vedere il documento collegato.

---

## 4. Dettaglio: `AGENTS.md` — l'ancora cross-tool

**Posizione:** radice del repository (accanto a `CLAUDE.md`).

**Cosa contiene — solo materiale tool-agnostico:**
1. Descrizione sintetica del progetto (rimando a `pre-speckit/project-brief.md` per il dettaglio, non duplicarlo).
2. Dichiarazione esplicita che il repository segue un flusso di governance strutturato Maker-Checker con Gate numerati.
3. **Regole minime valide anche per strumenti senza meccanismo di subagent** (rilevante soprattutto per Codex CLI, che oggi non replica la suddivisione in 6 agenti isolati):
   - non considerare una feature "conclusa" senza un passaggio di verifica indipendente equivalente a un Gate, anche se eseguito senza un agente Checker dedicato;
   - richiedere sempre conferma esplicita dell'utente prima di considerare superato un Gate;
   - leggere `PROJECT-STATE.md` a inizio sessione e aggiornarlo a fine sessione/Gate (dettagli in sezione 5).
4. Puntatori, non contenuto duplicato: a `CLAUDE.md` per il dettaglio completo dell'orchestrazione a 6 agenti (se si sta usando Claude Code), a `PROJECT-STATE.md` per lo stato corrente, a `docs/adr/` per le decisioni architetturali.

**Cosa NON deve contenere, e perché:** la tabella dei 6 agenti e dei loro step. Esiste già in `CLAUDE.md`. Duplicarla in `AGENTS.md` creerebbe due fonti che possono divergere nel tempo — lo stesso tipo di fragilità già evitato altrove nel framework (es. la scelta di tenere il tag di priorità inline in `spec.md` invece che in un file separato, nella proposta sulla prioritizzazione dei requisiti).

**Modifica minima a `CLAUDE.md`:** estendere — non riscrivere — la sezione "Nota su Codex CLI" già esistente, aggiungendo un rimando esplicito:

> *(testo esistente invariato, poi aggiungere:)* Per la continuità tra strumenti diversi su questo stesso repository, vedi `AGENTS.md` alla radice — contiene le regole minime valide anche per strumenti senza meccanismo di subagent — e `PROJECT-STATE.md` per lo stato corrente del progetto.

---

## 5. Dettaglio: `PROJECT-STATE.md` — lo stato del progetto

### Perché a livello di progetto e non di singola feature

Il framework ha già un file di stato per-feature, `.specify/specs/<NNN-feature>/progress.md`, e funziona bene per quello scopo. Ma non esiste nulla che risponda a **"qual è la feature attiva adesso, e a che punto è"** senza dover prima sapere quale cartella aprire — un problema che non si pone finché sei tu, nella stessa sessione continua, ma si pone eccome per un collega che apre il repository per la prima volta, o per una sessione Codex CLI che parte da zero.

`PROJECT-STATE.md` **non sostituisce `progress.md`**: lo referenzia. Contiene una sintesi di poche righe con un puntatore al file di dettaglio, non lo duplica.

### Posizione

Radice del repository.

### Campi (template)

```markdown
# Stato del progetto — aggiornato automaticamente

**Ultimo aggiornamento:** [data] · [agente/strumento/persona che ha aggiornato]

## Feature attiva
[Nome/numero feature] — Fase [N], Gate [N] [superato / in attesa di conferma]
Dettaglio step-by-step: `.specify/specs/<NNN-feature>/progress.md`

## Ultimo evento significativo
[Una riga: cosa è successo, quando, chi/cosa lo ha fatto]

## Prossimo step previsto
[Una riga]

## Decisioni o blocchi in attesa dell'utente umano
[Elenco breve, o "Nessuno al momento"]

## Altre feature in corso (se presenti)
[Tabella breve: nome feature — fase/gate — link a progress.md. Omettere la sezione se una sola feature è attiva.]
```

### Owner e trigger di aggiornamento — riuso di un pattern già esistente, non una novità procedurale

Questo è il punto che riduce di più il rischio di implementazione: **il framework ha già un precedente funzionante per esattamente questo tipo di disciplina**. Dal `CLAUDE.md` reale, il compito dell'orchestratore a ogni turno include già:

> Aggiorna tu stesso `progress.md` spuntando lo step completato e annotando data/agente. **Nessuno dei 6 agenti modifica `progress.md` direttamente — è compito esclusivo tuo.**

`PROJECT-STATE.md` segue **la stessa identica regola**: single-writer, aggiornato esclusivamente dall'orchestratore (o da chi ne fa le veci in una sessione Codex CLI, secondo la regola dichiarata in `AGENTS.md`), nello stesso momento in cui oggi si aggiorna già `progress.md` — cioè ai Gate, quando l'orchestratore si ferma comunque per la conferma esplicita dell'utente. Non introduciamo una nuova disciplina da rispettare: **estendiamo di un file un'abitudine già in uso**.

### Compatibilità cross-tool della regola di aggiornamento

Poiché una sessione Codex CLI non ha necessariamente un "orchestratore" distinto nello stesso senso di Claude Code, la regola va dichiarata in `AGENTS.md` in forma tool-agnostica: *"a fine sessione o alla chiusura di una fase significativa, chi sta guidando la sessione aggiorna `PROJECT-STATE.md` secondo il template in cima al file"* — senza assumere l'esistenza del meccanismo di subagent descritto in `CLAUDE.md`.

### Mitigazione del rischio di conflitti di merge

Due sessioni (o due persone) che aggiornano `PROJECT-STATE.md` nello stesso istante possono generare un conflitto Git. Il rischio è ridotto dallo stesso meccanismo che lo mitiga già per `progress.md`: aggiornamento **solo a momenti discreti** (Gate, fine sessione), non continuo, e da un solo scrittore alla volta per costruzione del flusso (i Gate richiedono comunque conferma sequenziale dell'utente).

---

## 6. Cosa non cambia, cosa non si duplica

- Non si tocca la struttura a 6 agenti, il principio Maker-Checker, i 4 Gate.
- `progress.md`, `risk-register.md`, e i tre output del Requirement Burn-up restano come sono — `PROJECT-STATE.md` li referenzia, non li assorbe.
- `docs/adr/` (da `proposta-adr-progetto.md`) resta un pezzo indipendente, implementabile prima, dopo, o insieme a questa proposta.

---

## 7. Il rischio principale, e perché qui è più mitigato che altrove

Il rischio più serio di qualunque meccanismo di "memoria scritta" è la disciplina di aggiornamento: un file di stato non aggiornato è **peggio** di non averlo, perché dà falsa sicurezza a chi lo legge. Questo rischio è già emerso più volte nel percorso che ha portato a questa proposta — decisioni prese ma non ancora tradotte in file reali.

Qui il rischio è più contenuto che nelle altre proposte, per un motivo preciso: **non stiamo chiedendo una disciplina nuova**, stiamo estendendo di un file una disciplina che il framework rispetta già per `progress.md`, allo stesso identico trigger (i Gate). Non serve che l'orchestratore "si ricordi" di fare qualcosa di ulteriore — è la stessa azione, ripetuta su un secondo file.

---

## 8. Cosa serve fare per implementare (checklist per l'AI incaricata)

1. **Creare `AGENTS.md`** alla radice, con il contenuto descritto in sezione 4 — solo materiale tool-agnostico, nessuna duplicazione della tabella agenti/step già in `CLAUDE.md`.
2. **Creare `PROJECT-STATE.md`** alla radice, popolato inizialmente con lo stato reale corrente del progetto, usando il template della sezione 5.
3. **Estendere la sezione "Nota su Codex CLI" già esistente in `CLAUDE.md`** con il rimando descritto in sezione 4 — modifica minima e additiva, non una riscrittura.
4. **Aggiungere `AGENTS.md` e `PROJECT-STATE.md` alla sezione "Percorsi di riferimento" di `CLAUDE.md`**, che oggi già elenca i percorsi chiave del progetto (costituzione, Fase Meno Uno, spec/piano/task, checklist, risk register, `progress.md`).
5. **Aggiungere un'istruzione esplicita nel blocco "Il tuo compito a ogni turno" di `CLAUDE.md`**: ai Gate, oltre ad aggiornare `progress.md` come già avviene, aggiornare anche `PROJECT-STATE.md` secondo il template.
6. **Verificare concretamente** che Codex CLI legga `AGENTS.md` nel repository una volta creato (comando di verifica tipico: chiedere a Codex di riassumere le istruzioni correnti e controllare che rifletta il contenuto di `AGENTS.md`).
7. **Prima di implementare**, confermare con l'utente lo stato corrente reale del progetto da inserire come valore iniziale di `PROJECT-STATE.md`, dato che questo documento non ha visibilità sullo stato del repository al momento dell'implementazione.

---

## 9. Nota di provenienza

Documento nato da una sessione di ragionamento congiunto tra l'utente (123trading) e un'istanza Claude, che ha incluso: una valutazione comparativa esplicita di strumenti di memoria per agenti AI (Mem0, Graphiti/Zep, RAG generico) conclusa con lo scarto motivato di tutti a favore di un'architettura a file versionati in Git; e la verifica diretta del contenuto reale di `CLAUDE.md`, inclusa la sezione "Nota su Codex CLI" già esistente, per ancorare la proposta allo stato effettivo del repository invece che a supposizioni. Si aggiunge a `regola-escalation-modello-effort.md`, `proposta-percorso-snello-routing.md`, `proposta-adr-progetto.md`, `proposta-burnup-forecast.md` e `proposta-prioritizzazione-requisiti.md`.
