# TRACEABILITY-RULES — Cosa conta come collegamento

**Versione:** 2.0 · **Stato:** normativo · **Implementato in:** `burnup/specscan.py`, `burnup/engine.py`

## Principio

> **Nessun matching semantico. Mai.**

Un collegamento esiste solo se qualcuno lo ha dichiarato esplicitamente. Un collegamento indovinato da un modello linguistico non è tracciabilità: è una supposizione con l'aspetto di un dato, e come tale è peggio dell'assenza di dato — perché nessuno la metterà in discussione.

Corollario: una regola di **lettura** rigorosa richiede una regola di **scrittura** corrispondente. La v3 aveva solo la prima, e il burn-up mostrava zero requisiti implementati su un prodotto funzionante.

## Le quattro relazioni

| Tipo | Da → A | Sorgente | Proprietario |
|---|---|---|---|
| `implemented-by` | requisito → task | `tasks.md` | Tech Lead |
| `evidenced-by` | requisito → riga di codice | commenti nel sorgente | Software Engineer |
| `verified-by` | requisito → test | `state/test-definitions.json` | BA/QA |
| `derived-from` | requisito → requisito | decisione esplicita | Product Manager |

Ogni relazione porta il `requirement_fingerprint` al momento della creazione. È il campo che la fa decadere da sola quando il requisito cambia contenuto.

## Estrazione dei requisiti

Un requisito viene estratto **solo se entrambe** le condizioni valgono:

1. la riga combacia col pattern (`- **FR-001**: testo`, `FR-001: testo`, `- **FR-002** (US1): testo`);
2. la riga si trova **dentro una delle sezioni configurate** in `requirements.sections`.

Un ID citato altrove è un rimando, non un requisito: genera un rilievo informativo e non entra nello scope.

> v3: `- FR-999: vedi documento esterno` scritto sotto `# Notes` entrava nel burn-up come requisito reale, gonfiando lo scope.

### User story

L'appartenenza è **strutturale**: si guarda il percorso gerarchico della sezione. In alternativa vale il tag inline `(US1)` sulla stessa riga.

**Nessun requisito eredita mai la user story di una sezione precedente.**

> v3: una variabile `current_user_story` veniva impostata da un heading "User Story N" e non azzerata mai. Attraversando `## Requirements`, ogni requisito globale ereditava l'ultima user story vista. Verificato: FR-001 e NFR-001 sotto `## Requirements` risultavano entrambi appartenere a US2.

## Collegamento ai task

```
- [x] T014 [P] [US2] [REQ:FR-003,NFR-002] Implementa … in src/…
- [ ] T003 [NON-REQ: script di build] Configura la pipeline
```

L'engine applica **confini di token** attorno agli ID accettati, indipendentemente dalla regex scritta dall'utente.

> v3: `- [x] T001 Implement XFR-001Y helper` veniva collegato a FR-001.

Un task senza né `[REQ:...]` né `[NON-REQ:...]` viene contato fra gli `unlinked_tasks`.

## Evidenza nel codice

```python
# REQ: 001-feature/FR-001
def authenticate(...): ...
```

Due condizioni non negoziabili:

1. **il marcatore deve stare in un commento** — riga che inizia con un prefisso di commento, oppure commento in coda al codice;
2. **la chiave è composita**, `feature/requisito`.

Un marcatore dentro una stringa viene **rifiutato** con un rilievo esplicito. Una stringa eseguibile non è una dichiarazione di tracciabilità.

> v3: `msg = "REQ: 001-demo/FR-001 not a real link"` contava come evidenza di codice valida.

### Esclusioni obbligatorie

La directory di output è **sempre** esclusa dalla scansione dei sorgenti, insieme a `.git`, `node_modules`, virtualenv e cache. Senza questa esclusione i marcatori presenti nelle celle "Code Evidence" della Matrix generata verrebbero riletti come evidenza, e il sistema si auto-alimenterebbe.

## Collegamento ai test

Viene dalla `requirement_keys` della definizione del test, che è la fonte autorevole ed è scritta tramite `burnup test define`. Rispecchiarla nella Matrix è sincronizzazione, non inferenza.

Un test che dichiara un requisito inesistente genera un finding `test-orphan`.

## Conferma manuale di un collegamento

Quando un collegamento è reale ma non deducibile — il task implementa il requisito senza citarne l'ID, e riscrivere `tasks.md` non è praticabile:

```bash
burnup link confirm 001-feat/FR-001 T014 --type implemented-by \
    --actor "lead@team" --reason "il task non cita l'ID ma lo implementa"
```

Il collegamento resta valido **finché il fingerprint del requisito non cambia**. Se il requisito viene riscritto, la conferma decade e va rinnovata: è corretto, perché ciò che era stato confermato non è più ciò che c'è scritto.

## Catena end-to-end (P2-01)

L'audit segnalava che il vincolo "a senso unico" verso `pre-speckit/` interrompe la tracciabilità strategica: nessun file nativo di Spec Kit può citare Obiettivi o User Journey, quindi la catena si spezza prima di arrivare al business.

Il vincolo resta — serve a tenere puliti gli artefatti nativi — ma la catena si ricompone **fuori** da essi:

```
Objective (OBJ-001, project-brief.md)
    ↓  citato in
Journey (JRN-001, user-journeys.md)
    ↓  la tabella del journey cita la feature Spec Kit
Feature (001-nome)
    ↓  spec.md
User Story  →  Requirement (FR-001)
    ↓  relations.jsonl
Task  ·  Code  ·  Test
```

I due anelli superiori vivono in `pre-speckit/`, che referenzia le feature per nome. Dalla feature in giù la catena è nel canonical store, con relazioni tipizzate e fingerprint.

Per rendere esplicito un collegamento fra un requisito e un obiettivo di prodotto:

```bash
burnup link confirm 001-feat/FR-001 OBJ-001 --type derived-from \
    --actor "pm@team" --reason "il requisito realizza l'obiettivo di riduzione dell'attrito in onboarding"
```

`derived-from` non partecipa al calcolo del ciclo di vita: è tracciabilità strategica, non evidenza di implementazione. Serve a rispondere alla domanda "perché stiamo costruendo questa cosa", che è diversa da "è fatta?".

**Limite dichiarato.** Il collegamento è manuale e opzionale: il framework non lo pretende e non lo verifica. Renderlo obbligatorio significherebbe imporre una struttura al Project Brief che non tutti i progetti vogliono. Chi ha bisogno di tracciabilità strategica completa può assegnare ID a obiettivi e journey — i template li prevedono già — e usare questo comando in modo sistematico.
