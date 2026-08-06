# ARCHITECTURE — Requirement Burn-up

**Versione:** 2.0 · **Stato:** normativo

## La regola che spiega tutto il resto

```
Il canonical store è la verità.
Il Markdown è una proiezione.
Nessuna decisione umana viene mai registrata modificando un report generato.
```

La v3 usava gli stessi file Markdown come report leggibile **e** come database transazionale. Da quella singola scelta discendevano, direttamente, otto dei difetti dell'audit: corruzione da escape dei pipe, impossibilità di garantire l'append-only, evidenza stantia preservata, finding senza identità stabile, scritture non atomiche, storia riscritta ad ogni giro.

## Flusso dei dati

```
  spec.md ─┐
 tasks.md ─┼─→ specscan ─→ requisiti + relazioni ─┐
  sorgenti ┘                                       │
                                                   ├─→ status ─→ engine ─→ store.commit()
  report di test ─→ ingest ─→ esecuzioni ──────────┘                          │
                                                                              ├─→ state/*.json[l]
  decisioni umane (CLI) ────────────────────────────────────────────────────→ │
                                                                              └─→ reports/*.md
                                                                                       │
                                                                                       ✗ mai riletto
```

La freccia sbarrata è il punto: `reports/` è un vicolo cieco per l'engine.

## Moduli

| Modulo | Responsabilità | Difetti v3 che chiude |
|---|---|---|
| `errors` | tassonomia ed exit code | N-01, P1-32 |
| `paths` | confinamento al project root | P0-09, N-07 |
| `fingerprint` | identità immutabile | P0-06, P1-17 |
| `mdparse` | parser strutturale, tabelle simmetriche | P0-05, P0-04, N-03 |
| `models` | entità del canonical store | P1-16, P1-21 |
| `store` | persistenza atomica, lock, schema | P0-12, P1-19, P1-20, N-02 |
| `ids` | ULID, ID stabili derivati dal contenuto | P1-11, P1-16 |
| `config` | validazione completa pre-scrittura | P1-06, P1-07 |
| `specscan` | scoperta ed estrazione dell'evidenza | P0-04, P1-13, P1-14, P1-29 |
| `ingest` | importazione idempotente | P0-07, P0-08, P1-12 |
| `status` | ciclo di vita | P0-06, P1-30 |
| `gates` | state machine dei phase gate | P1-26, P1-27, P1-28 |
| `engine` | orchestrazione dello scan | P1-10, P1-18, N-05 |
| `render` | proiezioni Markdown | P0-05 |
| `cli` | comandi ed exit code | P0-03, P0-10 |
| `risk_link` | lettura del risk register | P1-09 |

Dipendenze aciclike: `errors` ← `paths`/`fingerprint`/`ids` ← `models`/`mdparse` ← `config`/`store` ← `specscan`/`ingest`/`status`/`gates` ← `engine` ← `render`/`cli`.

## Canonical store

```
requirement-burnup/
├── state/
│   ├── schema-version.json      governa la compatibilità
│   ├── requirements.json        requisiti + fingerprint
│   ├── relations.jsonl          relazioni tipizzate e datate
│   ├── test-definitions.json    sorgente autorevole dei test
│   ├── test-runs.jsonl          esecuzioni, append-only reale
│   ├── findings.jsonl           rilievi con ID stabile e ciclo di vita
│   ├── decisions.jsonl          ogni atto umano
│   ├── gate-decisions.jsonl     Gate Decision Record
│   ├── snapshots.jsonl          storia dei conteggi
│   ├── scan-manifest.json       fingerprint degli input dell'ultimo scan
│   └── .lock                    transitorio
└── reports/                     rigenerabile: cancellarlo non perde nulla
```

**`state/` va versionato.** È la storia del progetto, non un artefatto derivato.

## Transazionalità

Ogni comando che scrive:

1. acquisisce il lock (`O_CREAT|O_EXCL`, atomico su POSIX e Windows);
2. carica lo stato;
3. calcola **tutto in memoria**;
4. serializza tutto — un errore qui fallisce prima di toccare il disco;
5. scrive ogni file con temp + `fsync` + `os.replace`;
6. rilascia il lock.

Il passo 4 prima del 5 è la correzione di N-02: la v3 creava i file di output all'inizio del refresh, quindi un errore successivo lasciava artefatti vuoti che il refresh seguente trattava come stato precedente valido.

## Determinismo

Lo stesso input produce sempre lo stesso output, byte per byte:

- glob ordinati esplicitamente, mai nell'ordine del filesystem;
- JSON con `sort_keys=True`;
- newline forzati a `\n` in scrittura, così Windows e Linux producono file identici;
- "ultima esecuzione" per timestamp con ULID come tie-breaker, mai per ordine di elaborazione;
- ULID al posto dei contatori: non serve leggere lo storico per generare un ID, quindi non esiste un modo di sbagliare il calcolo.

## Exit code

| | |
|---:|---|
| 0 | successo |
| 1 | errore di configurazione |
| 2 | quality gate fallito |
| 3 | errore di engine — è un bug |
| 4 | uso errato della CLI |

Una pipeline decide dal solo exit code, senza fare parsing dello stderr.
