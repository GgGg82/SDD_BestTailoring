# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/). Versionamento semantico.

## [4.0.0-beta.1] — 2026-07-31

Riscrittura controllata, non una patch: cambiano contratti dati, workflow, ownership e semantica degli stati. Origine: audit completo della v3 (12 P0, 32 P1, 6 P2), riverificato finding per finding con probe eseguiti sul codice reale.

### Cambiamenti che rompono la compatibilità

- **Il Markdown non è più il database.** La fonte di verità è il canonical store in `requirement-burnup/state/`; i file in `reports/` sono proiezioni rigenerabili e non vengono mai riletti dall'engine.
- **`schema_version` sale a `2.0`** e governa davvero la compatibilità: una config allo schema precedente viene rifiutata invece di essere interpretata a caso.
- **La CLI si chiama `burnup`** ed espone sottocomandi per le decisioni umane.
- **Exit code ridefiniti:** `0` ok, `1` configurazione, `2` quality gate fallito, `3` errore di engine.
- **`specify init` è uno step di progetto**, non più per-feature.
- **`/speckit.analyze` si esegue una sola volta**, dopo `tasks.md` (step 3.2). Rimosso dagli step 2.3 e 4.2.
- **Ogni riferimento a domini, tecnologie o progetti specifici è stato rimosso** da `CLAUDE.md` e dai 6 agenti. Il contesto di progetto vive nella constitution.

### Corretto — release blocker

- **P0-01** `analyze` usato in due punti non validi. Lo step 2.3 girava prima che `tasks.md` esistesse; lo step 4.2 pretendeva di verificare il codice, che `analyze` non ispeziona. Sostituito da verifica indipendente via lint, analisi statica e test.
- **P0-02** Contratto di traceability non prodotto da nessun agente. Ora Tech Lead e Software Engineer hanno l'obbligo esplicito di Requirement Key e marcatore `REQ:`.
- **P0-03** Decisioni umane senza percorso tecnico. Introdotti `burnup link confirm`, `requirement remove`, `test define`, `test confirm-manual`, `finding waive`, `finding close`. Nessuna remediation richiede più di editare una tabella generata.
- **P0-04** Requisiti estratti ovunque nel documento ed ereditarietà della user story. Parser strutturale con heading stack: l'appartenenza è strutturale, l'estrazione avviene solo dalle sezioni configurate.
- **P0-05** Corruzione dei dati nelle tabelle Markdown: il writer produceva pipe escapati che il parser non riconosceva. Escape e unescape ora simmetrici, verificati con property test su 12.000 casi.
- **P0-06** Evidenza stantia preservata: un requisito riscritto da capo restava `tested`. L'evidenza è ora legata al `requirement_fingerprint`, e decade da sola al cambio di contenuto.
- **P0-07** Ingestione non idempotente, matching per sottostringa, ordine cronologico errato. Deduplica su `run_identity`, matching con confini di token, "latest" per timestamp di esecuzione.
- **P0-08** Freschezza inaffidabile: ai report veniva assegnato l'HEAD del refresh. Ora la revisione arriva dal report o da un sidecar `.meta.json`; `manual-confirmation` richiede una conferma reale con attore, motivo ed evidenza; il working tree sporco invalida `current-revision`.
- **P0-09** Violazione del confinamento: `output_dir` assoluto e glob assoluti uscivano dal repository. Tutti i percorsi sono ora relativi e confinati, con reject di assoluti, traversal e symlink escape.
- **P0-10** `refresh` restituiva `0` anche con findings bloccanti. Introdotto `--strict` con exit code `2`, da eseguire **prima** dell'approvazione del Gate 4.
- **P0-11** Il Checker non poteva verificare in modo indipendente. Allargata l'allowlist Bash del Technical Auditor a lint, analisi statica, security e test runner.
- **P0-12** Nessuna test suite, scritture non transazionali. 76 test automatici, 89% di copertura, scritture atomiche con fsync e rename, lock di processo.

### Aggiunto — governance (incrementi B e C)

- **State machine dei phase gate** (`burnup gate status|approve|reject`). Transizioni controllate: un gate non è approvabile se il precedente non è valido, se manca il suo artefatto, o — per il Gate 4 — se esistono finding bloccanti. Chiude P1-26.
- **Invalidazione automatica dei gate a valle** al cambio di un artefatto a monte. Non è una procedura da ricordare: è il confronto fra i fingerprint registrati nel Gate Decision Record e quelli correnti. Lo stato non viene mai memorizzato, per non reintrodurre il difetto di un valore che qualcuno deve aggiornare. Chiude P1-27.
- **Gate Decision Record** in forma PMI: decision ID, approvatore, fingerprint degli artefatti approvati, finding aperti, waiver, condizioni, rationale, conteggi del burn-up. `--force` non nasconde i criteri non soddisfatti: li scrive nel record e marca la decisione `conditionally-approved`. Chiude P1-28.
- **Preset Spec Kit `sdd-traceability`**: impone i Requirement Key nei task generati da `/speckit.tasks`, con strategia `append` così il comando core resta intatto fra un aggiornamento e l'altro. Chiude la parte mancante di P0-02 e P2-06.
- **Nove documenti normativi versionati** in `docs/`: ARCHITECTURE, STATUS-RULES, TRACEABILITY-RULES, BURNUP-CALCULATION, TEST-REGISTER-SPEC, OPERATING-PROCEDURE, DESIGN-DECISIONS, RACI, SCALE-ADAPTIVE-FLOW. I primi sette erano citati dal codice della v3 come fonte di verità **senza esistere**. Chiude P1-22.
- **RACI** per artefatto, decisione e attività di verifica, con una sola Accountable per riga e verifica di coerenza Maker–Checker. Chiude P2-04.
- **Flusso scale-adaptive** con classi Fast Track / Standard / High-Risk. Scala il numero di artefatti e revisioni, **mai** il rigore della misurazione: tracciabilità, test obbligatori e `refresh --strict` valgono identici in tutte le classi. Promozione ammessa in corsa, retrocessione no. Chiude P2-03.
- **Risk register PMI completo**: owner, trigger, esposizione, azione con scadenza, contingency, rischio residuo, risposte per minacce e opportunità. Chiude P1-05.
- **Hook `PreToolUse` per l'allowlist Bash dei Checker** (`.claude/hooks/`). Trasforma in enforcement tecnico la restrizione che INSTALL.md dichiara onestamente essere comportamentale: blocca redirezioni, `sed -i`, comandi git che modificano il repository e installazioni di pacchetti quando l'agente in esecuzione è un Checker. È un filtro sintattico, non una sandbox, e il README lo dichiara. Chiude la parte implementabile di P2-05.
- **Catena di tracciabilità end-to-end** documentata: `Objective → Journey → Feature → User Story → Requirement → Task/Code/Test`, ricomposta tramite la relazione `derived-from` senza violare il vincolo a senso unico verso `pre-speckit/`. Chiude P2-01, con il limite dichiarato che il collegamento strategico resta manuale e opzionale.
- **Genericizzazione completa** del framework: zero riferimenti a progetti, domini o tecnologie specifiche in `CLAUDE.md`, nei 6 agenti e nei template. Il contesto di progetto vive nella constitution, che è il posto previsto da Spec Kit ed è per-progetto per costruzione. Chiude P2-02, con l'ampiezza decisa dall'utente (genericizzazione totale, non solo isolamento in sezioni marcate).

### Corretto — high

P1-01 (`--ai` rimosso a monte, pin mancante), P1-02, P1-03, P1-04, P1-05, P1-06, P1-07 (cinque campi documentati e ignorati), P1-09, P1-10, P1-11, P1-12, P1-13, P1-14, P1-16, P1-17, P1-18, P1-21, P1-22, P1-23, P1-24, P1-25, P1-26, P1-27, P1-28, P1-29, P1-30, P1-31, P1-32.

### Respinto o riclassificato dopo verifica

- **P1-08 (CRLF) — respinto.** Verificato: `Path.read_text()` normalizza i newline, quindi nel percorso reale il frontmatter CRLF veniva parsato correttamente. Il probe dell'audit passava una stringa grezza a una funzione interna. Il difetto adiacente reale era il **BOM UTF-8**, riclassificato come N-03 e corretto.
- **P1-19, P1-20 — fusi** in P0-05 e P0-12: erano conseguenze del Markdown usato come database, non cause indipendenti.
- **P1-15 — declassato** a questione definitoria della metrica, non difetto di correttezza.

### Corretto — difetti trovati dalla suite della v4 stessa

- **N-08 — lo stato si riscriveva ad ogni refresh anche a input invariati.** `Requirement.last_seen`, `Finding.last_seen` e `Relation.valid_from` venivano rigenerati ad ogni scansione, producendo un diff Git ad ogni `refresh` e violando la proprietà MSA "nessun cambio di stato senza cambio di input" che questo stesso progetto dichiarava come target.

  Nel caso di `valid_from` non era solo rumore: il campo significa *da quando* una relazione è valida, e riscriverlo faceva perdere l'informazione "da quando esiste questo collegamento".

  `last_seen` è stato rinominato in `last_changed` con semantica onesta — si muove solo quando il contenuto cambia davvero — e `valid_from` viene preservato per le relazioni identiche già presenti. Quando è avvenuta l'ultima scansione lo dice `scan-manifest.json`, che è l'unico posto in cui quel dato deve vivere.

  Il difetto era mascherato da un test intermittente: `test_property_refresh_is_idempotent` passava 37 volte su 40, fallendo solo quando i due refresh cadevano a cavallo di un secondo. Il test ora forza il superamento del secondo ed è deterministico.

### Aggiunto — difetti non rilevati dall'audit

- **N-01** L'invariante di burn-up era protetta da un `assert`, che sparisce sotto `python -O` e produceva un traceback non intercettato. Sostituita da `InvariantError` con exit code dedicato, con test che verifica la persistenza del controllo sotto `-O`.
- **N-02** I file di output venivano creati prima del completamento delle validazioni: un errore successivo lasciava artefatti vuoti che il refresh seguente trattava come stato valido.
- **N-03** BOM UTF-8 non gestito nel frontmatter.
- **N-04** `unbacktick` duplicato in tre moduli con guardie divergenti.
- **N-05** `get_current_revision` inghiottiva ogni causa di fallimento e ignorava il working tree sporco.
- **N-06** `reconcile` mutava in place le righe scoperte, senza copia.
- **N-07** La directory di output non era esclusa dalla scansione dei sorgenti: i marcatori nei report generati potevano auto-alimentare l'evidenza di codice.
