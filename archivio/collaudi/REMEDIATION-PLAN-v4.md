# Piano di remediation — SDD Multi-Agent Framework v4.0.0-beta.1

**Input:** `SDD_MULTI_AGENT_FRAMEWORK_V3_FULL_AUDIT.md` (50 finding: 12 P0, 32 P1, 6 P2)
**Baseline sotto esame:** `repo-bundle/` (26 file, ~1.900 righe Python)
**Metodo:** ogni finding è stato riverificato leggendo il codice ed eseguendo probe sull'engine reale. Nessun finding è stato accettato sulla fiducia.
**Data:** 2026-07-31

---

## 1. Verdetto per perimetro

L'audit emette un unico verdetto NO-GO sul framework. **Non lo condivido nella forma**: aggrega due sistemi con maturità molto diverse, e questo porterebbe a rifare anche ciò che funziona.

| Perimetro | Verdetto mio | Motivazione |
|---|---|---|
| **Engine Requirement Burn-up** | **NO-GO confermato** | Corruzione dati, evidenze stantie certificate come valide, zero test automatici. Verificato end-to-end, vedi §2.1. |
| **Layer agenti / gate / Maker–Checker** | **Utilizzabile dopo 3 fix mirati** | L'impianto concettuale è corretto. I difetti sono di *sequenza* e *contratto*, non di struttura. Non va riscritto. |
| **Installazione e distribuzione** | **Rotto oggi** | Il comando in `INSTALL.md` non funziona più: `--ai` è stato rimosso in Spec Kit v0.10.0, non solo deprecato. |
| **Documentazione normativa** | **Assente** | 7 documenti citati dal codice come fonte di verità non esistono. |

La distinzione conta: **il grosso del lavoro è sull'engine**, non sugli agenti.

### 1.1 Decisioni prese (input dell'utente)

| Decisione | Scelta | Conseguenza sul piano |
|---|---|---|
| Strategia engine | **Canonical store + Markdown generato** | Il Markdown smette di essere database. Chiude alla radice P0-05/06/07 e P1-16..20. |
| Portabilità | **Genericizzazione totale** — nessun riferimento a progetti specifici | Rimozione di ogni traccia `123trading`/MQL5. Packaging promosso da C a B. |
| Verifica indipendente | **Allargare l'allowlist Bash del Technical Auditor** | Nessun settimo agente. Costo minimo, separazione dei ruoli comunque reale. |
| Deliverable | **Piano scritto, poi esecuzione** | Questo documento va approvato prima di toccare il codice. |

---

## 2. Registro di triage

### 2.1 Confermati con riproduzione diretta

Ho costruito un progetto Spec Kit minimo e fatto girare l'engine. Il probe più significativo — **non presente nell'audit in questa forma**:

```
Stato iniziale:  FR-001 "il sistema deve autenticare l'utente"
                 tasks.md con T001 completo, marker REQ nel codice, TEST-1 pass
                 → refresh: Tested/Done: 1
Poi:             cambio il testo in "cancellare tutti i dati dell'utente al logout"
                 cancello tasks.md
                 rimuovo il marker dal codice
Risultato:       refresh → "Tested/Done: 1 | Findings totali: 0"
                 Matrix → Task `T001`, Code `src/auth.py:1`, Test `TEST-1`, `tested`
```

Requisito semanticamente diverso, nessuna evidenza residua, **e il sistema riporta zero findings**. Non è un falso positivo: è una certificazione attiva di uno stato falso. Questo da solo giustifica il NO-GO sull'engine.

| ID | Finding | Esito verifica | Note mie |
|---|---|---|---|
| P0-01 | `/speckit.analyze` usato male | **Confermato** | Verificato contro la doc ufficiale corrente: `analyze` gira *solo* dopo `tasks.md`, è read-only, copre spec/plan/tasks e **non il codice**. Step 2.3 e 4.2 sono entrambi invalidi; solo 3.2 è corretto. |
| P0-02 | Contratto di traceability non prodotto | **Confermato** | Nessun agente impone Requirement Key nei task né marker `REQ:` nel codice. Il motore misura l'assenza di metadata, non l'assenza di implementazione. |
| P0-03 | Decisioni umane senza percorso tecnico | **Confermato e più grave** | Per portare un requisito a `tested` ho dovuto **editare a mano la tabella Markdown** del Test Register — l'unica strada esistente, ed è quella che la documentazione vieta esplicitamente. `link_state=proposed` è dichiarato in `LINK_STATES` ma nessun flusso lo produce mai. |
| P0-04 | Estrazione requisiti e attribuzione User Story | **Confermato** | Probe: `FR-001` e `NFR-001` sotto `## Requirements` ereditano entrambi `US2`; `FR-999` citato sotto `# Notes` viene estratto come requisito reale. |
| P0-05 | Corruzione tabelle Markdown | **Confermato, severità alzata** | `alpha \| beta` → riletto come `{'A': 'alpha \\', 'B': 'beta'}`: dato perso e colonne sfasate. **Nota mia:** non è un rischio teorico. Le spec contengono `\|` con frequenza alta (tabelle, notazioni, regex, alternative). La corruzione è attesa, non ipotetica. |
| P0-06 | Evidenze stantie preservate | **Confermato, peggiore del descritto** | Vedi probe sopra. `reconcile` preserva task/code/test link confermati; `_sync_test_links` fa union e non rimuove mai. |
| P0-07 | Ingestione test non idempotente | **Confermato** | Tre refresh dello stesso report JUnit → tre righe `RUN-...-001/002/003` identiche nella Execution History. `TEST-1` cattura `suite.TEST-10_login` (matching substring). Lo stato "latest" è l'ultimo record processato, non il più recente per timestamp. |
| P0-08 | Freshness dei test inaffidabile | **Confermato** | `cli.py` passa l'HEAD *del refresh* al parser del report: un report vecchio risulta eseguito sulla revisione corrente. `manual-confirmation` ritorna `True, ""` incondizionatamente — non contiene alcuna conferma. |
| P0-09 | Violazione del confinamento al repository | **Confermato** | `output_dir: /tmp/OUTSIDE` → risolto fuori dal repo (`Path / assoluto` sovrascrive la radice). Glob assoluto `/tmp/secret.txt` → letto e potenzialmente riportato negli artefatti. |
| P0-10 | Gate 4 non è un quality gate | **Confermato** | Finding `high` `missing-mandatory-test` → **exit code 0**. Nessuna pipeline può bloccare deterministicamente. |
| P0-11 | Checker senza verifica indipendente | **Diagnosi accettata, rimedio ridimensionato** | Vero che BA/QA non ha Bash né test runner. Ma il Technical Auditor **ha già Bash e non ha Write/Edit**: è solo il suo prompt a restringerlo a due usi. Allargare l'allowlist ottiene lo stesso risultato senza un settimo agente. |
| P0-12 | Nessuna test suite, scritture non transazionali | **Confermato** | Zero file di test nel bundle. `_run_scan` scrive i tre artefatti in sequenza senza temp file, fsync, rename atomico o lock. |

### 2.2 Confermati (P1, verifica documentale o su codice)

| ID | Esito | Nota |
|---|---|---|
| P1-01 | **Confermato e aggravato** | `--ai` non è "legacy": è stato **rimosso** in v0.10.0. Il comando in `INSTALL.md` oggi fallisce. Manca inoltre il pin di release. |
| P1-02 | Confermato | `specify init` è bootstrap di progetto, non attività per-feature. |
| P1-03 | Confermato | `/speckit.checklist` valida la *scrittura* dei requisiti, non la completezza tecnica del piano né il comportamento del prodotto. |
| P1-04 | Confermato | `converge` fa scrivere task all'Auditor, che poi li valuta. Va dichiarata come eccezione formale o separato il ruolo. |
| P1-05 | Confermato | Il risk register manca di owner, trigger, esposizione, due date, contingency, rischio residuo, escalation. |
| P1-06 | Confermato | `load_config` verifica solo la presenza delle chiavi top-level; tipi, enum, regex e path non sono validati. |
| P1-07 | Confermato | `test_source_globs`, `default_scope_state`, `allow_forced_snapshot`, `schema_version`, `risk_register_path()`: **zero occorrenze** fuori da `config.py`. Sono documentati e ignorati. |
| P1-09 | Confermato | `` `FR-001`, `FR-002` `` → `['FR-001`', '`FR-002']`. Le annotazioni di rischio chiuso non vengono mai rimosse (`annotate_matrix_with_risks` solo aggiunge). |
| P1-10 | Confermato | Rimozione + aggiunta a parità di conteggio → `(False, 'no-change')`: nessuno snapshot. `removed_total` non partecipa alla decisione. |
| P1-11 | Confermato | Con storico `001, 003` → genera di nuovo `003` (usa `len()`, non `max()`). `next_snapshot_id` usa correttamente `max()`: l'incoerenza è solo su `next_run_id`. |
| P1-12 | Confermato | Dict comprehension: l'ultima definizione con lo stesso Test ID vince in silenzio. |
| P1-13 | Confermato | Il primo layout candidato vince senza warning. |
| P1-14 | Confermato | `XFR-001Y` in un task → collegato a `FR-001`. Un marker `REQ:` dentro una stringa eseguibile conta come evidenza di codice. |
| P1-16 | Confermato | I Finding ID sono rigenerati a ogni refresh: nessun aging, nessuna chiusura tracciabile. |
| P1-17 | Confermato | L'evidenza è un percorso mutabile, senza hash né dimensione. |
| P1-18 | Confermato | `status` legge gli artefatti senza verificare se gli input siano cambiati dopo l'ultimo refresh. |
| P1-21 | Confermato | `dashboard.py` deduce la feature via split del subject: un finding su `TEST-001` non è attribuibile. |
| P1-22 | Confermato | 7 documenti citati dal codice come normativi e mai forniti: `DESIGN-DECISIONS`, `TRACEABILITY-RULES`, `OPERATING-PROCEDURE`, `STATUS-RULES`, `BURNUP-CALCULATION`, `ARCHITECTURE`, `TEST-REGISTER-SPEC`. |
| P1-23 | Confermato, **priorità alzata** | Nessun `pyproject.toml`, nessun changelog, nessuna versione, `__pycache__` incluso nel bundle. Con la decisione "framework riusabile su molti progetti", questo diventa strutturale. |
| P1-25 | Confermato | Nessun handoff envelope: con più feature o worktree un subagent può lavorare sulla feature sbagliata. |
| P1-26 | Confermato | `progress.md` è una checklist editata a mano, senza transizioni ammesse né invalidazione. |
| P1-27 | Confermato | Nessuna regola invalida i gate a valle quando cambia un artefatto a monte. |
| P1-28 | Confermato | Il template registra solo "approvato da / il". Nessun evidence package. |
| P1-29 | Confermato | Nessuna exclude rule: un marker citato in un README o nella Matrix stessa può diventare evidenza di codice. |
| P1-30 | Confermato | `tasks_ok = (task_info is None) or ...`: in assenza di task, il solo marker nel codice rende il requisito `implemented`. |
| P1-31 | Confermato | Nessun vincolo su `mandatory`, `kind`, comando, owner, ambiente. |
| P1-32 | Confermato | La CLI intercetta solo `ConfigError`/`SpecsLayoutError`; il resto propaga come traceback. |

### 2.3 Respinti, declassati o fusi

Questa sezione è il valore aggiunto rispetto ad accettare il report così com'è.

| ID | Verdetto mio | Motivazione |
|---|---|---|
| **P1-08** — CRLF | **Respinto nella forma. Riscritto come N-03.** | `Path.read_text()` applica la traduzione universal-newline: attraverso `load_document()` — l'**unico** percorso usato dall'engine — un file CRLF parsa il frontmatter correttamente (verificato). Il probe dell'audit ha passato una stringa `\r\n` grezza direttamente a `parse_document()`, che non è il percorso reale. **Difetto vero adiacente:** il BOM UTF-8 rompe davvero il frontmatter (verificato). Da riscrivere come "BOM non gestito", severità P2. |
| **P1-15** — scope della metrica | **Declassato a P2** | Legittimo, ma è una questione definitoria (come si chiama la metrica), non un difetto di correttezza. Si risolve rinominando o estendendo il measurement unit; non blocca nulla. |
| **P1-19** — "append-only non è vero" | **Fuso in P0-05 / P0-12** | È una conseguenza del Markdown usato come database, non una causa indipendente. Il canonical store lo chiude automaticamente. |
| **P1-20** — scritture non atomiche | **Fuso in P0-12** | L'audit stesso lo segnala come "collegato al P0-12". Tenerlo separato gonfia il backlog senza aggiungere lavoro. |
| **P1-24** — `pip --break-system-packages` | **Accettato, ma banale** | Corretto, ma è una riga di documentazione. Rientra nel lavoro di packaging (B), non merita trattamento autonomo. |
| **P0-11** — rimedio | **Ridimensionato** | Vedi §2.1. Il finding resta P0; la soluzione "settimo agente" non è necessaria. |
| **Verdetto globale NO-GO** | **Riformulato** | Vedi §1. Aggregare engine e layer agenti in un unico verdetto porterebbe a riscrivere anche la parte sana. |

### 2.4 Finding non rilevati dall'audit

| ID | Finding | Sev. | Evidenza |
|---|---|---|---|
| **N-01** | `assert` usato per l'invariante di burn-up in `compute_counts` | P1 | Sparisce sotto `python -O`, disabilitando un controllo di integrità dichiarato critico. Quando scatta, `AssertionError` non è intercettata dalla CLI: traceback grezzo ed exit code 1, indistinguibile da un errore di configurazione. Va sostituita con un'eccezione tipizzata e un exit code dedicato. |
| **N-02** | `_ensure_output_files` copia i template prima del completamento delle validazioni | P1 | Chiamata all'inizio di `_run_scan`, prima di ingestione e calcolo stato. Un crash successivo lascia nel repo tre artefatti vuoti che sembrano legittimi e che il refresh successivo tratterà come stato precedente valido. |
| **N-03** | BOM UTF-8 non gestito nel frontmatter | P2 | Sostituisce P1-08. Verificato: `load_document` su file con BOM → `frontmatter: {}`. Una scrittura successiva aggiunge un secondo frontmatter lasciando il primo nel body. |
| **N-04** | `unbacktick` duplicato in tre file con guardie divergenti | P2 | `requirements.py` protegge con `len(v) >= 2`, `tests_register.py` e `risk_link.py` no. Una cella contenente un solo backtick si azzera. Va estratto in un modulo condiviso. |
| **N-05** | `get_current_revision` inghiotte ogni fallimento | P2 | Ritorna `""` senza distinguere "git assente", "non è un repo" e "comando fallito". Con la policy di default `manual-confirmation` la cosa è invisibile, e gli snapshot registrano `Source Revision: UNKNOWN` senza spiegazione. Non copre inoltre il working tree sporco. |
| **N-06** | `reconcile` muta le righe scoperte in place | P2 (latente) | `row = discovered` seguito da assegnazioni: nessuna copia. Innocuo oggi perché `discovered_rows` non è riusato, latente appena lo sarà. |
| **N-07** | Nessuna exclude di `requirement-burnup/` dai source glob | P2 | Variante concreta di P1-29: la Matrix generata contiene marker `REQ:` nelle celle Code Evidence. Se un glob include `**/*`, l'output si auto-alimenta. |

**Riconciliazione del conteggio.**

| | |
|---|---:|
| Finding dell'audit | 50 |
| — respinto e riscritto (P1-08 → N-03) | −1 |
| — fusi in altri finding (P1-19, P1-20) | −2 |
| **Accettati come voci di backlog** (12 P0 + 29 P1 + 6 P2, di cui P1-15 declassato) | **47** |
| Aggiunti da questa revisione (N-01..N-07) | +7 |
| **Totale backlog v4** | **54** |

Controllo di coerenza sui P1: 27 confermati in §2.2 + 5 trattati in §2.3 (P1-08, P1-15, P1-19, P1-20, P1-24) = 32. ✓

---

## 3. Architettura target

### 3.1 Principio

> Il canonical store è la verità. Il Markdown è una proiezione rigenerabile. **Nessuna decisione umana viene mai registrata modificando un report generato.**

Questo singolo principio chiude P0-05, P0-06, P0-07, P1-16, P1-17, P1-19, P1-20 e P1-12 — ed è il motivo per cui le patch puntuali sul parser Markdown non sarebbero state sufficienti.

### 3.2 Layout

```
requirement-burnup/
├── state/                        ← canonical, machine-readable, versionato
│   ├── schema-version.json
│   ├── requirements.json         ← key, fingerprint, testo normalizzato, scope
│   ├── relations.jsonl           ← relazioni tipizzate con validità temporale
│   ├── test-definitions.yml      ← sorgente autorevole dei test (scrivibile via CLI)
│   ├── test-runs.jsonl           ← append-only reale, con report hash
│   ├── findings.jsonl            ← ID stabili + lifecycle
│   ├── decisions.jsonl           ← ogni decisione umana: actor, reason, revision
│   └── scan-manifest.json        ← fingerprint degli input dell'ultimo scan
└── reports/                      ← generati, mai letti dall'engine
    ├── traceability-matrix.md
    ├── test-register.md
    └── governance-dashboard.md
```

**Regola di direzione:** l'engine scrive `reports/` e non li rilegge mai. Oggi li rilegge, ed è precisamente da lì che nasce la corruzione.

### 3.3 Identità e fingerprint

Ogni entità ha identità stabile e verificabile:

- `requirement_fingerprint = SHA-256(testo normalizzato + criteri di accettazione + riferimenti NFR)`
- l'evidenza (task, codice, test) è legata al **fingerprint**, non solo alla chiave
- al cambio di fingerprint l'evidenza si invalida automaticamente e lo stato retrocede a `defined`
- `RunID` ULID; `ReportHash` sui byte del report; `FindingID` stabile tra refresh; `DecisionID` per ogni atto umano

Questo è ciò che rende impossibile il probe di §2.1.

### 3.4 Relazioni tipizzate

Sostituisce sia il matching per substring sia il campo Notes usato come metadato macchina (P1-09, P1-14, P1-21):

```json
{
  "from": "001-demo/FR-001",
  "to": "T014",
  "type": "implemented-by",
  "status": "confirmed",
  "source": "tasks.md",
  "requirement_fingerprint": "…",
  "artifact_fingerprint": "…",
  "valid_from": "…",
  "valid_to": null
}
```

Il campo **Notes torna a essere esclusivamente umano**.

### 3.5 Modello di stato

| Stato | Condizioni |
|---|---|
| `defined` | requisito attivo, ID valido, testo normativo non vuoto, fingerprint corrente |
| `implemented` | tutti i task di implementazione obbligatori completi **e** evidenza di codice corrente **e** evidenza riferita al fingerprint corrente **e** nessun finding P0/P1 aperto |
| `tested` | `implemented` + tutti i test obbligatori collegati + ultimo run applicabile `pass` + run riferito alla revisione e al fingerprint correnti + evidenza immutabile disponibile |
| `removed` | decisione di change esplicita con motivo, attore, data, impact analysis e invalidazione dei gate a valle |

Nota su P1-30: `implemented` **richiede** i task. L'assenza di `task_info` smette di significare "va bene così".

---

## 4. Backlog per incrementi

### Incremento A — Fondazione dati, correttezza, sicurezza

> Chiude: P0-04, P0-05, P0-06, P0-07, P0-08, P0-09, P0-12, P1-06, P1-07, P1-09, P1-10, P1-11, P1-12, P1-13, P1-14, P1-16, P1-17, P1-18, P1-29, P1-31, P1-32, N-01..N-07

**A0 — Harness di regressione, prima del codice.**
I 23 probe dell'audit più i 7 miei diventano test automatici che **falliscono** sulla v3. Nessun fix viene scritto prima che il test corrispondente esista ed è rosso. Questa è la contromisura diretta contro il rischio principale del piano: correggere un sintomo credendo di aver corretto la causa.

**A1 — Canonical data model.** Schema, migrazioni, identità, fingerprint, relazioni tipizzate (§3).

**A2 — Sostituzione del parser.** Parser Markdown strutturale con heading stack; estrazione dei requisiti solo dalle sezioni configurate; nessuna ereditarietà implicita della User Story; supporto multiline; diagnostica dei duplicati con source range; gestione BOM.

**A3 — Modello di path sicuro.** Tutti i path relativi e risolti sotto `project_root`; reject di assoluti, `..` e symlink escape; allowlist di root sorgente; exclude obbligatorie di `.git`, output, virtualenv, segreti (N-07).

**A4 — Ridisegno dell'ingestione test.** Matching esatto con token boundary o mapping esplicito; `run_identity` con hash del report; deduplica idempotente; "latest" calcolato per timestamp con tie-breaker deterministico; revision reale dal report o da sidecar, **mai** l'HEAD del refresh.

**A5 — Proiezioni di report.** I tre `.md` diventano output puro. Nessuna rilettura.

**A6 — Scritture transazionali.** Write-to-temp + rename atomico, lock di processo, validazione completa **prima** di creare qualsiasi file (N-02), taxonomy degli errori con exit code distinti: `0` successo, `1` errore di configurazione, `2` quality gate fallito, `3` errore di engine (N-01, P1-32).

**A7 — CI.** Unit, property-based, integration, end-to-end su Linux e Windows.

**Criteri di uscita A:**
- `parse(render(x)) == x` su ≥ 1.000 casi generati, inclusi pipe, backslash, backtick, Unicode, newline, celle vuote
- reimportare due volte lo stesso report non cambia nulla
- `TEST-1` non corrisponde mai a `TEST-10`
- l'ordine di elaborazione dei file non influenza il risultato
- **il probe di §2.1 fa retrocedere il requisito a `defined` e produce finding espliciti**
- 100% dei test di path escape respinti
- copertura di branch ≥ 85%, 100% su status rules, parser, ingestione e path safety
- interruzione iniettata a ogni step di scrittura non lascia mai artefatti incoerenti

### Incremento B — Workflow, ruoli, distribuzione

> Chiude: P0-01, P0-02, P0-03, P0-10, P0-11, P1-01..P1-05, P1-21..P1-28, P1-30, P2-02, P2-06

**B1 — Baseline di compatibilità.** Pin esplicito della release Spec Kit, comando di installazione corretto (`--integration`), matrice di compatibilità, verifica `specify version`, procedura di upgrade controllata.

**B2 — Sequenza Spec Kit corretta.**
- `analyze` rimosso da 2.3 e 4.2; **una sola** esecuzione dopo `tasks.md` e prima dell'implementazione
- per la compliance del codice: verifica indipendente con static analysis, esecuzione test, security check, conformità alla constitution
- `converge` dopo l'implementazione, con l'eccezione Maker–Checker dichiarata formalmente (P1-04)
- `progress-template.md` e `CLAUDE.md` riallineati

**B3 — Contratto di traceability.** Preset Spec Kit che impone il formato dei task:
```
- [ ] T014 [P] [US2] [REQ:FR-003,NFR-002] Implementa … in src/…
```
Con ownership esplicita: Requirement key → Product Manager; task link → Tech Lead; code evidence → Software Engineer; test definition → BA/QA; ingestione e verifica → Technical Auditor.

**B4 — Command surface per le decisioni umane.** Chiude il finding operativo più grave (§2.1, P0-03):
```
burnup link confirm | requirement remove | test define
burnup test confirm-manual | finding waive | finding close
```
Ogni decisione registra actor, timestamp, reason, source_revision, requirement_fingerprint, eventuale scadenza. **Nessuna remediation richiede più di editare una tabella generata.**

**B5 — State machine dei gate.** Stato machine-readable con transizioni ammesse; fingerprint degli artefatti; invalidazione automatica dei gate a valle al cambio di una baseline; `burnup refresh --strict` **prima** dell'approvazione del Gate 4, con soglie configurabili; `progress.md` generato come vista.

**B6 — Allowlist Bash del Technical Auditor.** Estesa a lint, test runner, static analysis e generazione report in sola lettura; divieto esplicito di modifica del codice di produzione; PreToolUse hook per l'enforcement (P2-05 parziale, a supporto di P0-09).

**B7 — Genericizzazione totale.** Rimozione di ogni riferimento a progetti, domini o tecnologie specifiche da `CLAUDE.md`, dai 6 agenti e dai template. Il framework diventa neutro per costruzione, non per convenzione.

**B8 — Packaging.** `pyproject.toml`, versione applicativa, changelog, dependency lock, licenza, `__pycache__` fuori dal bundle, guida di migrazione e disinstallazione. Distribuzione come **extension + preset Spec Kit ufficiali** con manifest, versione e upgrade path, al posto della copia manuale.

**Criteri di uscita B:**
- una feature demo raggiunge il Gate 4 **senza un solo edit manuale di tabelle generate**
- nessun `analyze` invocato prima che `tasks.md` esista
- ogni tipo di finding ha un percorso di chiusura documentato
- ogni finding `high` blocca il gate salvo waiver approvato e registrato
- una pipeline determina PASS/FAIL dal solo exit code
- il Gate 4 registra run ID del burn-up ed evidence hash
- `grep -ri` su nomi di progetto e tecnologie di dominio: **zero occorrenze**
- installazione riproducibile su un repo pulito partendo da zero

### Incremento C — Maturità di governance

> Chiude: P0-11 (completamento), P1-05, P2-01, P2-03, P2-04, P2-05, P1-15, P1-22

- **C1** — Risk register PMI completo: owner, trigger, esposizione, response owner e due date, contingency, rischio residuo, escalation, transfer. Rinominare in `threat-register.md` oppure estendere alla gestione delle opportunità.
- **C2** — Gate Decision Record versionato: decision ID, approver, fingerprint degli artefatti approvati, finding aperti, waiver, condizioni, rationale. Integrated change control.
- **C3** — RACI versionata per artefatto, decisione, test, rischio e gate.
- **C4** — Flusso scale-adaptive: classi Fast Track / Standard / High-Risk. I controlli P0 di traceability e testing **non si riducono mai**; scalano il numero di artefatti e revisioni.
- **C5** — Strategia di test risk-based ispirata a BMAD TEA, con priorità P0–P3.
- **C6** — I 7 documenti normativi mancanti: scritti come spec versionate, oppure i riferimenti rimossi dal codice. Nessuna via di mezzo — un codice che cita una fonte di verità inesistente è peggio di un codice che non ne cita nessuna.

---

## 5. Piano di verifica

**Unit** — parser requisiti su fixture del template Spec Kit corrente; rendering; validazione config; risoluzione path; transizioni di lifecycle; matching test; decisione di snapshot; generazione ID.

**Property-based** — round-trip del serializzatore; ordinamento arbitrario degli input; idempotenza del refresh ripetuto; nessun cambio di stato senza cambio di input; invarianti dei conteggi.

**Integration** — bootstrap; creazione feature; cambio requisito dopo Gate 1; cambio piano dopo Gate 2; rigenerazione task; marker rimosso; regressione pass→fail; report stantio; working tree sporco; rischio aperto/chiuso; requisito rimosso e reintrodotto; due refresh simultanei.

**Security** — path assoluto; traversal; symlink escape; output in root protette; config o regex malevola; report malformato o sovradimensionato; output generato incluso nei source glob.

**End-to-end** — almeno tre profili di progetto tecnologicamente distinti, per dimostrare che la baseline è davvero neutra e non solo dichiarata tale.

### 5.1 Target Measurement System Analysis

| Metrica | Target |
|---|---|
| Idempotenza | 100% |
| Link falsi a requisiti o test | 0 |
| Perdita dati nel round-trip | 0 |
| Ingestione duplicata di run | 0 |
| Path escape riusciti | 0 |
| Rilevamento di evidenza stantia | 100% sulle fixture |
| Output deterministico a ordine di input mescolato | 100% |
| Recovery dopo crash simulato | 100% |

---

## 6. Definition of Done — v4.0.0-beta.1

- [ ] tutti i P0 chiusi
- [ ] i 23 probe dell'audit e i 7 aggiuntivi sono test automatici e passano nel comportamento corretto
- [ ] versione Spec Kit pinnata e verificata; installazione funzionante
- [ ] `analyze` e `converge` usati secondo la semantica ufficiale
- [ ] Test Register con owner e percorso di scrittura ufficiale via CLI
- [ ] ogni decisione umana persistente e auditabile
- [ ] confinamento dei path dimostrato da test
- [ ] refresh idempotente
- [ ] evidenza immutabile e fingerprinted
- [ ] Gate 4 strict, preceduto dal refresh
- [ ] CI verde su Linux e Windows
- [ ] nessun artefatto parzialmente aggiornato dopo failure injection
- [ ] documentazione normativa inclusa o riferimenti rimossi
- [ ] package con versione, changelog, manifest e guida di migrazione
- [ ] **zero riferimenti a progetti, domini o tecnologie specifiche**

---

## 7. Rischi del piano

| Rischio | Risposta |
|---|---|
| Correggere sintomi invece di cause, e credere di aver chiuso un P0 | A0: nessun fix senza un test rosso che lo precede |
| Il canonical store introduce difetti nuovi in codice oggi funzionante | Property test di round-trip e migrazione + confronto degli output sulla stessa fixture prima/dopo |
| Backlog di 52 voci che perde slancio a metà | Incrementi con criteri di uscita binari; A è autonomo e già rilascia valore |
| La genericizzazione peggiora la qualità degli agenti, che perdono contesto utile | Il contesto di progetto si fornisce a runtime tramite constitution e preset, non incastonato nei prompt |
| Drift di Spec Kit durante il lavoro | B1 come primo passo dell'incremento B: pin prima di ogni altra modifica di workflow |

---

## 8. Sequenza raccomandata

```
A0 → A1 → A2 ─┬→ A3 → A4 → A5 → A6 → A7      Fondazione     [engine utilizzabile]
              │
B1 ───────────┴→ B2 → B3 → B4 → B5 → B6 → B7 → B8   Workflow  [framework distribuibile]

C1 … C6                                              Governance [maturità PMI/BMAD]
```

B1 può partire in parallelo ad A: è indipendente e va fatto presto, perché oggi l'installazione è rotta e ogni ora di lavoro su un workflow non pinnato rischia di essere lavoro su una baseline che si muove.

---

**Prossimo passo:** approvazione di questo piano, poi apertura dell'incremento A0.
