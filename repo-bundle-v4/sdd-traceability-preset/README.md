# Preset `sdd-traceability`

Impone che ogni task generato da `/speckit.tasks` dichiari i requisiti che implementa.

## Installazione

```bash
specify preset add --dev ./sdd-traceability-preset --priority 5
specify preset list
specify preset resolve speckit.tasks    # verifica quale layer vince
```

Priorità 5 (numero basso = precedenza alta) perché il contratto di tracciabilità deve prevalere su preset più generici eventualmente installati.

## Cosa cambia

Usa la strategia `append`: il comando `speckit.tasks` del core resta intatto e questo preset aggiunge le proprie regole in coda. Non c'è nulla da risincronizzare quando Spec Kit si aggiorna.

**Prima:**

```
- [ ] T014 Implementa la validazione dell'input
```

**Dopo:**

```
- [ ] T014 [P] [US2] [REQ:FR-003,NFR-002] Implementa la validazione dell'input in src/validation.py
- [ ] T003 [NON-REQ: configurazione della pipeline di build] Imposta la CI
```

## Perché serve

Lo strumento Requirement Burn-up collega un task a un requisito **solo** se l'ID compare letteralmente nella riga del task: nessun matching semantico, nessuna euristica. È una scelta deliberata — un collegamento indovinato da un LLM non è tracciabilità, è una supposizione con l'aspetto di un dato.

Ma una regola di lettura rigorosa richiede una regola di scrittura corrispondente. Nella v3 del framework mancava la seconda: il motore pretendeva gli ID, nessun template li produceva. Il burn-up mostrava zero requisiti implementati su un prodotto funzionante — sbagliato in modo silenzioso e plausibile.

## Verifica dopo l'installazione

```bash
specify preset resolve speckit.tasks
```

Deve mostrare questo preset in cima allo stack per il comando `speckit.tasks`. Poi genera i task di una feature di prova e controlla che ogni task funzionale porti `[REQ:...]`.

## Nota sulla compatibilità

`requires.speckit_version` è impostato a `>=0.10.0` come minimo prudenziale. **Allinealo al tag effettivamente fissato in `INSTALL.md`** al momento del bootstrap del progetto, e verifica il manifest con `specify preset info sdd-traceability` prima di darlo per buono: la struttura è quella documentata, ma va validata contro la versione di Spec Kit che stai realmente usando.
