# OUTPUT-ANNOTATION — Chi parla, e da quale punto del flusso

**Versione:** 1.0 · **Stato:** normativo · **Vale per:** Orchestratore e tutti e sei gli agenti

---

## Perché esiste

`CLAUDE.md` prescrive già che l'Orchestratore *«determini lo step corrente e lo annunci esplicitamente»*. L'obbligo c'è. Mancano tre cose, e sono quelle che lo rendono inefficace:

1. **Nessun formato.** Un annuncio richiesto ma di forma libera cambia lunghezza e struttura a ogni turno, e l'occhio smette di cercarlo perché non sa dove guardare.
2. **L'agente non è coperto.** L'obbligo riguarda lo *step*, non *chi parla*. Ma in un'architettura Maker–Checker l'informazione critica è proprio quella: lo stesso contenuto va letto con criteri opposti a seconda che venga da un Maker o da un Checker. Un rilievo di `@business-analyst-qa` e una bozza di `@product-manager` non si valutano allo stesso modo.
3. **Un solo attore responsabile.** La prescrizione vive nel prompt dell'Orchestratore. Quando lui la omette, non esiste ridondanza che la recuperi.

**Il costo dell'assenza non è l'estetica.** In una sessione lunga, o quando si riprende dopo giorni, chi legge ricostruisce step e attore dal contenuto. È una ricostruzione silenziosa e fallibile: si finisce per valutare un artefatto con i criteri dello step sbagliato, o per attribuire a un Checker un giudizio prodotto da un Maker. L'errore non produce un fallimento visibile — produce **un'approvazione mal fondata**, che è peggio, perché nessuno la va a cercare.

---

## Il formato

```
Fase <N> <Nome fase> · Step <N.M> — <descrizione breve> — <@agente>
```

Quando l'attività non corrisponde a uno step formale — esplorazione, chiarimento, una domanda all'utente — la parte `Step <N.M>` si omette:

```
Fase <N> <Nome fase> · <descrizione breve> — <@agente>
```

### Nomi delle fasi

Elenco chiuso. Sono i nomi che `CLAUDE.md` usa nelle proprie intestazioni: non inventarne altri e non tradurli.

| Fase | Nome |
|---|---|
| `-1` | Pre-Spec Kit |
| `0` | Bootstrap |
| `1` | COSA |
| `2` | COME |
| `3` | Task |
| `4` | Implementazione e verifica |
| `5` | Rilascio |

### Esempi

```
Fase -1 Pre-Spec Kit · Step -1.0 — brainstorming sul confine con il progetto ospite — @product-manager
Fase 1 COSA · Step 1.2 — corner-case sweep, categorie 1-5 — @business-analyst-qa
Fase 2 COME · Step 2.2-risk — intervista sui rischi tecnici — @business-analyst-qa
Fase 4 Implementazione e verifica · Step 4.2 — verifica indipendente del codice — @technical-auditor
Fase 3 Task · Gate 3 — approvazione prontezza all'implementazione — Orchestratore
Fase 5 Rilascio · Step 5.1 — merge — Utente umano
```

### Perché il nome della fase e non il solo numero

`Step 4.2` è un indirizzo, non un significato. Chi legge deve ricordare a memoria che cosa sia la Fase 4 per sapere con quali criteri valutare l'output — ed è proprio quella traduzione mentale il costo che questa convenzione elimina.

---

## Regole

**Sempre presente.** Nessuna eccezione, nemmeno per output di due righe. Un'annotazione a intermittenza è peggio della sua assenza: rende ambigua l'omissione, e chi legge non sa più se manca perché non serviva o perché ci si è dimenticati.

**Una riga sola.** Nessun riquadro, nessuna formattazione elaborata, nessuna spiegazione. La descrizione dello step è un'etichetta, non un riassunto: se supera una decina di parole, non è più un'annotazione.

**Non compete con il contenuto.** Sta in cima, e finisce lì.

**Usa gli identificativi che esistono.** `-1.0`, `0.2`, `2.1-loop`, `4.3-review`, `burnup-refresh`: sono quelli di `CLAUDE.md`. Non coniarne di nuovi per comodità descrittiva — un identificativo inventato sembra un riferimento e non lo è.

### Attori che non sono agenti

| Chi | Come si scrive | Quando |
|---|---|---|
| L'Orchestratore | `Orchestratore` | presentazione di un Gate, diagnosi, domande all'utente |
| L'utente | `Utente umano` | step 5.1, approvazioni, decisioni di spesa |

**I Gate si attribuiscono all'Orchestratore**, non al Checker che ha prodotto l'esito. L'esito è del Checker; la presentazione e la richiesta di conferma sono dell'Orchestratore. Attribuire il Gate al Checker confonderebbe chi ha prodotto il giudizio con chi lo sta sottoponendo ad approvazione — che è esattamente la distinzione che la separazione Maker–Checker esiste per mantenere.

### Quando l'output attraversa due step o due agenti

**Si spezza l'output**, con una nuova annotazione a ogni cambio. Non si accorpa sotto l'annotazione del primo.

È più verboso, ed è voluto: un blocco unico che contiene il lavoro di due attori diversi è precisamente ciò che rende difficile capire chi ha detto cosa — cioè il problema che questa convenzione risolve.

---

## Rapporto con `progress.md`

L'annotazione **non è una seconda fonte di verità.** Riporta lo step che l'Orchestratore ha determinato secondo `CLAUDE.md`, sezione *Il tuo compito a ogni turno*, punto 2. `progress.md` resta la vista leggibile dello stato, e `PROJECT-STATE.md` quella generata.

Se annotazione e `progress.md` divergono, non è l'annotazione a essere sbagliata: è lo stato che nessuno ha aggiornato. Va corretto lì.

---

## Come si verifica che funzioni

Una convenzione di sola presentazione rischia di essere invalidabile — di quelle che si adottano e non si sa mai se servano. Il criterio è questo:

> Su una feature completa, chi legge deve poter rispondere a **«in che step siamo e chi ha prodotto l'ultimo output»** senza scorrere all'indietro e senza aprire `progress.md`.

Se dopo l'adozione la risposta richiede ancora ricostruzione, la convenzione non ha funzionato e va **ritirata**, non rifinita.

---

## Il modo in cui questa convenzione muore

Non viene abbandonata con una decisione: **decade**. Si omette una volta in un output breve perché sembrava superfluo, poi due, e dopo un mese non significa più nulla — esattamente com'era già successo alla prescrizione originale del punto 2, che esiste dalla v3 e che nessuno vedeva.

Per questo la regola non vive solo nel prompt dell'Orchestratore, ma è ripetuta nella sezione *Al termine* di tutti e sei gli agenti: nessun singolo attore ne è l'unico custode.
