# Change Proposal — Visibilità di Step e Agente

**ID proposta:** G
**Framework di riferimento:** 4.0.0-rc.2
**Stato:** formalizzata, non implementata
**Data:** 2026-08-14 · **Rev:** 2 (aggiunto il nome della fase)
**Origine:** emersa durante il test di utilizzo reale del framework sul progetto LLM Wiki

---

## Premessa — non è un requisito nuovo

`CLAUDE.md`, sezione *«Il tuo compito a ogni turno»*, punto 2, prescrive già:

> «**Determina lo step corrente** e annuncialo esplicitamente, inclusi gli step opzionali non ancora considerati.»

L'obbligo esiste. Questa proposta **non lo introduce**: ne chiude tre lacune di attuazione. Il ridimensionamento è deliberato — una proposta che si presenta come nuova funzionalità quando è una precisazione di una regola esistente gonfia il proprio valore percepito.

---

## Problema

Tre lacune nell'attuazione dell'obbligo esistente:

1. **Nessun formato prescritto.** L'annuncio è richiesto ma la sua forma è libera. Una prescrizione senza formato produce annunci di lunghezza e struttura variabile, che l'occhio smette di cercare perché non sa dove guardare.

2. **L'identità dell'agente non è coperta.** L'obbligo riguarda lo *step*, non l'*agente*. Ma in un'architettura Maker–Checker l'informazione critica per l'operatore è **chi** sta parlando: lo stesso contenuto ha peso diverso se prodotto da un Maker o da un Checker. Un rilievo di `@business-analyst-qa` e una bozza di `@product-manager` vanno letti con criteri opposti. Oggi questa distinzione va dedotta dal contenuto.

3. **Nessun rinforzo lato agenti.** L'obbligo vive solo nel prompt dell'Orchestratore. I sei agenti in `.claude/agents/` non dichiarano la propria identità nell'output: la prescrizione è centralizzata su un solo attore, e quando quell'attore la omette non esiste ridondanza che la recuperi.

**Costo attuale.** In sessioni lunghe, o quando la sessione riprende dopo un'interruzione, l'operatore ricostruisce step e attore dal contenuto. La ricostruzione è silenziosa e fallibile: si valuta un artefatto applicando i criteri dello step sbagliato, o si attribuisce a un Checker un giudizio prodotto da un Maker. È un errore che non lascia traccia — non produce un fallimento, produce un'approvazione mal fondata.

---

## Proposta

Ogni output prodotto dentro il flusso è preceduto da un'**annotazione di intestazione** che dichiara step e agente.

**Formato:**

```
Fase <N> <Nome fase> · Step <N.M> — <descrizione breve> — <@agente>
```

Quando l'attività non corrisponde a uno step formale (esplorazione, chiarimento, brainstorming), la parte `Step <N.M>` si omette e resta la sola descrizione:

```
Fase <N> <Nome fase> · <descrizione breve> — <@agente>
```

**Nomi delle fasi** — elenco chiuso, deriva da `CLAUDE.md` e chiude il punto G1 della prima stesura:

| Fase | Nome |
|---|---|
| -1 | Pre-Spec Kit |
| 0 | Bootstrap |
| 1 | COSA |
| 2 | COME |
| 3 | Task |
| 4 | Implementazione e verifica |
| 5 | Rilascio |

**Esempi con la nomenclatura reale del framework:**

```
Fase -1 Pre-Spec Kit · Step -1.2 — verifica delle user journeys — @product-manager
Fase -1 Pre-Spec Kit · brainstorming sul confine con il progetto ospite — Orchestratore
Fase 2 COME · Step 2.2 — checklist di scope del piano — @business-analyst-qa
Fase 4 Implementazione e verifica · Step 4.2 — verifica indipendente del codice — @technical-auditor
Fase 3 Task · Gate 3 — approvazione prontezza all'implementazione — Orchestratore
```

**Perché il nome della fase e non il solo numero.** `Step 4.2` è un indirizzo, non un significato: chi legge deve ricordare a memoria cosa sia la Fase 4 per sapere con quali criteri valutare l'output. Il nome elimina quella traduzione mentale, che è proprio il costo che la proposta vuole abbattere.

**Requisiti dell'annotazione:**

- **Essenziale** — una riga, nessuna formattazione elaborata, nessun riquadro.
- **Sintetica** — solo i tre elementi necessari. La descrizione dello step è un'etichetta, non una spiegazione.
- **Sempre presente** — nessuna eccezione, anche per output brevi. Un'annotazione a intermittenza è peggio della sua assenza, perché rende ambigua l'omissione.
- **Non intrusiva** — non compete visivamente con il contenuto.
- **Coerente con la nomenclatura esistente** — usa gli identificativi di step già definiti in `CLAUDE.md` (`-1.1`, `0.2`, `2.1-loop`, `4.3-review`, `burnup-refresh`), senza introdurne di nuovi.

**Estensione ai Gate.** Quando l'Orchestratore presenta l'esito di un Gate, l'annotazione riporta il Gate e l'Orchestratore come attore — l'esito è del Checker, ma la presentazione e la richiesta di conferma sono dell'Orchestratore. Attribuirla al Checker confonderebbe chi ha prodotto il giudizio con chi lo sta sottoponendo ad approvazione.

---

## Punti aperti

| # | Punto | Nota |
|---|---|---|
| G1 | ~~Nomenclatura delle fasi~~ | **Chiuso**: elenco definito sopra |
| G2 | Handoff intra-output | Se un singolo output attraversa due step o due agenti, l'annotazione va ripetuta a ogni cambio, oppure l'output va spezzato. Da decidere: la seconda è più pulita ma più verbosa |
| G3 | Rapporto con `progress.md` | `progress.md` è la vista leggibile dello stato. L'annotazione dovrebbe derivare da lì, non essere una seconda fonte che può divergere. Da verificare che il template contenga già lo step corrente |
| G4 | Dove va scritta la regola | Solo nel prompt dell'Orchestratore (centralizzato, fragile) o replicata nella sezione «Al termine» dei sei agenti (ridondante, resistente all'omissione). La lacuna 3 suggerisce la seconda |
| G5 | Attori non-agente | Lo step 5.1 è dell'utente umano. Serve un'etichetta convenuta per gli step senza agente |

---

## Impatto

- **Ampiezza:** trasversale — tocca ogni step e ogni agente.
- **Profondità:** superficiale — convenzione di presentazione. Non modifica logica di processo, deliverable, gate, né la semantica del burn-up.
- **Rischio:** basso. Il fallimento tipico non è la corruzione di un artefatto ma la **decadenza della disciplina**: l'annotazione viene omessa progressivamente finché non significa più nulla. È esattamente il modo in cui la prescrizione esistente al punto 2 è già oggi poco visibile. Mitigazione: G4 — replicarla nel prompt di ciascun agente, così che nessun singolo attore sia l'unico responsabile.
- **Dipendenze:** nessuna bloccante.
- **Controlli P0:** nessun impatto. Non tocca tracciabilità, evidenza fingerprinted, test obbligatori, path confinement né `refresh --strict`.

---

## Verifica dell'efficacia

Una proposta di sola presentazione rischia di essere invalidabile. Criterio proposto:

> Su una feature completa, l'operatore deve poter rispondere a «in che step siamo e chi ha prodotto l'ultimo output» **senza scorrere all'indietro** e **senza aprire `progress.md`**.

Se dopo l'adozione la risposta richiede ancora ricostruzione, la proposta non ha funzionato e va ritirata anziché rifinita.

---

## Relazione con il resto del framework

Ortogonale a tutto: agisce sul livello di presentazione. Non sovrappone `docs/RACI.md` (che dice *chi dovrebbe* fare cosa, in astratto) — G dice *chi sta* facendo cosa, adesso. I due si rinforzano: G rende osservabile in esecuzione ciò che RACI prescrive in teoria.
