---
## Contratto di tracciabilità dei task — preset `sdd-traceability`

Queste regole si applicano **in aggiunta** a quanto sopra e non sono negoziabili: sono la precondizione perché la misurazione del burn-up dei requisiti sia veritiera.

### Ogni task funzionale dichiara i requisiti che implementa

Formato:

```
- [ ] T014 [P] [US2] [REQ:FR-003,NFR-002] Implementa la validazione dell'input in src/validation.py
```

- `[REQ:...]` contiene uno o più ID di requisito separati da virgola, **senza spazi**.
- Gli ID vanno scritti per intero e isolati. Lo strumento di traceability applica confini di token: `XFR-001Y` **non** viene riconosciuto come `FR-001`, e un ID incollato ad altri caratteri viene ignorato.
- Il marcatore può stare in qualunque punto della riga del task, ma per leggibilità va prima della descrizione.

### Ogni task non funzionale si dichiara tale

Un task che deliberatamente non implementa alcun requisito — build, tooling, configurazione, chore — porta il marcatore esplicito **con motivazione**:

```
- [ ] T003 [NON-REQ: configurazione della pipeline di build] Imposta la CI
```

Un task privo sia di `[REQ:...]` sia di `[NON-REQ:...]` viene segnalato come lacuna di tracciabilità. Non è un errore fatale, ma è un rilievo che qualcuno dovrà chiudere: meglio dichiarare l'assenza che lasciarla dedurre.

### Copertura

Prima di considerare `tasks.md` completo, verifica che **ogni requisito attivo della feature abbia almeno un task che lo dichiara**. Un requisito senza task è un requisito che nessuno ha pianificato di implementare: segnalalo esplicitamente invece di lasciarlo scoprire al Gate 4.

Riporta al termine:

- numero di task generati;
- numero di task con `[REQ:...]`, con `[NON-REQ:...]`, e senza nessuno dei due;
- elenco dei requisiti attivi **non** coperti da alcun task.

### Perché

Nella versione precedente di questo framework, lo strumento di traceability cercava l'ID del requisito nella riga del task, ma nessun template lo imponeva. Il risultato — riprodotto in audit — era che il burn-up mostrava zero requisiti implementati su un prodotto funzionante e testato. Il numero era sbagliato in modo silenzioso e plausibile, che è il modo peggiore in cui una metrica può sbagliare.
