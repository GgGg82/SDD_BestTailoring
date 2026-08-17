# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/it/1.1.0/). Versionamento semantico.

## [4.0.0-rc.2] — 2026-08-09

**Otto difetti trovati facendo girare il framework su un progetto vero**, non
leggendo il codice: un progetto Spec Kit costruito da zero, i sei agenti
impersonati nell'ordine prescritto da `CLAUDE.md`, pytest vero, JUnit vero, Git
vero, poi 40 feature sintetiche per la scala. Sono difetti che nessuna suite
unitaria poteva vedere, perché stanno nell'attrito fra l'engine e gli strumenti
che lo circondano.

### Corretto

- **C-21 (P0)** — `current-revision`, la policy che il template presenta come
  «la policy rigorosa», era **insoddisfabile**. L'engine legge la propria
  revisione con `git rev-parse --short HEAD` (7 caratteri) e la confrontava per
  uguaglianza di stringa con quella del sidecar; una pipeline che scrive
  `git rev-parse HEAD` — la forma canonica — ne produce 40. Stesso commit,
  confronto fallito, ogni requisito fermo a `implemented`, Gate 4 mai
  approvabile. Il rilievo stampava le due stringhe accanto: *«eseguito su
  e8d3138e4915…, la revisione corrente e' e8d3138»*. Il confronto è ora per
  prefisso, come fa Git con le abbreviazioni, con un minimo di 7 caratteri.

- **C-20 (P1)** — Una riga di task con l'ID in enfasi Markdown
  (`- [x] **T001** [REQ:FR-001] …`, forma frequente nel Markdown generato) non
  combaciava con la regex e **spariva senza alcun rilievo**. Il sintomo non
  puntava alla causa: ogni requisito riceveva `incomplete-tasks`, si andava a
  guardare `tasks.md` e lo si trovava tutto spuntato. L'enfasi è ora assorbita,
  e il formato prescritto dal preset resta valido.

- **C-19 (P1)** — `main()` intercettava `BurnupError` e `KeyboardInterrupt`;
  qualunque altra eccezione risaliva come traceback grezzo con exit code **1**,
  che il contratto riserva a `CONFIG_ERROR` — mandando chi legge a cercare un
  errore nella propria configurazione mentre il guasto era nell'engine. È
  esattamente il difetto che il docstring di `errors.py` dichiara chiuso dalla
  v3 in avanti. Ora esce `3` con un messaggio che dice che è un bug.

- **C-26 (P2)** — `refresh` elencava **ogni** finding bloccante senza limite:
  486 requisiti producevano 491 righe. Il consumatore principale di questo
  output è un agente con una finestra di contesto finita, quindi la lunghezza
  non può crescere con il progetto. Ora si ferma a 20 e riassume la coda per
  tipo, rimandando a `--json` e ai report.

- **C-24 (P2)** — `gate status` mostrava `change_class` in `--json` ma non
  nella vista che legge una persona, ed elencava i Gate 2 e 3 di una Fast Track
  come `not-approved`, cioè come lavoro ancora da fare. Ora l'intestazione
  dichiara classe e gate previsti, e i gate non previsti sono marcati tali.

- **C-23 (P2)** — `uncommitted-changes` diceva che qualcosa non era committato
  senza dire **cosa**. In simulazione questo ha portato a diagnosticare come
  bug dell'engine una situazione che era un `.pyc` tracciato per errore: senza
  i nomi, il rilievo manda a cercare nel posto sbagliato. Ora nomina i file
  (fino a 10, poi riassume) e gestisce le rinomine.

- **C-22 (P3)** — Il diagramma del ciclo di vita in `sdd-workflow-v4.html`
  mostrava `tested → defined` alla riscrittura di un requisito; la transizione
  reale, coerente con `STATUS-RULES.md`, è `tested → implemented`: decade la
  verifica, non l'implementazione.

### Verificato, non corretto

- Il formato JUnit prodotto da **pytest reale** è importato correttamente:
  è la forma che aveva motivato C-07, ora validata su output vero.
- **Prestazioni**: 486 requisiti su 41 feature in **0,21 s** e 27 MB.
- L'asimmetria fra decadenza dell'evidenza di test e di codice è **deliberata**
  e documentata; il sospetto che fosse un difetto è stato respinto leggendo
  `STATUS-RULES.md` §«Le tre evidenze non decadono allo stesso modo».
- Un sospetto P0 sull'esclusione dei file dell'engine dal calcolo del worktree
  sporco è stato **ritirato**: l'esclusione funziona: il file sporco era un
  `.pyc` tracciato. È il motivo per cui C-23 vale la pena.

### Copertura

**339 test, 100%**, verdi anche sotto `python -O`. Cinque dei nuovi test hanno
trovato difetti nelle correzioni stesse mentre le scrivevo — fra cui uno
`.strip()` che spostava di un carattere ogni percorso restituito.

## [4.0.0-rc.1] — 2026-08-07

**Perché `rc.1` e non `5.0.0`.** Il numero maggiore segnala rotture rispetto a una versione **rilasciata**. La `4.0.0` non lo è mai stata: `4.0.0-beta.1` è una pre-release, e per definizione dichiara che la 4.0.0 non è ancora uscita. Le rotture introdotte qui — schema del canonical store da `2.0` a `3.0`, exit code `4` per gli errori d'uso — sono rotture rispetto a una beta, non rispetto a un contratto pubblicato: si risolvono avanzando l'identificatore di pre-release. Chiamarla `5.0.0` racconterebbe che una `4.x` stabile è esistita ed è stata rotta, e non è successo.

`rc` invece di `beta.2` perché lo stato è cambiato di natura: nessun difetto noto aperto, ogni procedura documentata verificata eseguibile, copertura al 100% con soglia che blocca le regressioni. Manca una cosa sola per la `4.0.0` definitiva — **girare su un progetto reale**, che è esattamente ciò che un release candidate dichiara di non aver ancora fatto.

Lo schema del canonical store ha una propria numerazione, indipendente da quella del pacchetto: è passato a `3.0`, e quello sì è un incremento maggiore a pieno titolo.

Origine: tre giri di collaudo end-to-end della beta.1 (2026-08-06 e 2026-08-07). Primo giro sul comportamento, secondo sul contratto della CLI e della configurazione, terzo sui perimetri fuori dall'engine — hook, documenti normativi, preset, CI, template. **Diciotto difetti trovati e corretti**, più un controllo aggiunto sul lavoro non salvato. Nessuno era visibile alla test suite, che pure aveva 98 test e 90% di copertura: i test esercitavano le funzioni, non la *procedura* e non il *contratto dichiarato*. Referto completo in `COLLAUDO-ENGINE-v4.md`.

### Corretto — release blocker

- **C-01 · Il Gate 4 non era ancora un quality gate.** Una feature con metà dei requisiti mai implementati superava tutti e quattro i gate con **zero finding aperti** e `refresh --strict` a exit code 0, e il Gate Decision Record registrava `{'scope': 2, 'tested': 1}` approvando comunque. Causa: in `status.py` tutti i finding vivevano dentro un ramo, e l'intero blocco `tested` — quindi anche `missing-mandatory-test` — era annidato dentro `implemented`; il requisito su cui nessuno ha lavorato cadeva fuori da ogni ramo in silenzio. Non era una questione di severità: senza finding emesso, nessun valore di `strict_blocks_on` poteva intercettarlo. Introdotto **`requirement-not-verified`**, severità `high`, emesso per ogni requisito attivo che non raggiunge `tested`. È il segnale uniforme su cui il Gate 4 si misura; gli altri finding restano come spiegazione del perché. Il rinvio resta possibile ma non silenzioso, con `finding waive` o `requirement remove`.

- **C-03 · `refresh` cancellava tutte le approvazioni.** `engine.py` costruiva lo `StoreData` del refresh senza riportare `gate_decisions` — mentre `decisions` veniva riportato — quindi `commit` riscriveva `gate-decisions.jsonl` vuoto. Poiché `CLAUDE.md` impone `refresh --strict` **prima** di ogni approvazione del Gate 4, la procedura documentata azzerava i Gate 1-3 e rendeva il Gate 4 inapprovabile con l'errore "il Gate 3 non è valido". La state machine era inutilizzabile esattamente nel percorso per cui era stata scritta. Si vedeva solo approvando i quattro gate di fila senza refresh in mezzo, che è l'unico ordine in cui i test la esercitavano.

- **C-02 · La decadenza dell'evidenza di test non funzionava.** Riscrivendo il significato di un requisito e lasciando intatti `tasks.md` e il marcatore nel codice — che citano l'ID, non il testo — il requisito **restava `tested`**, contrariamente a `docs/STATUS-RULES.md`. È la forma residua del probe che ha motivato l'intera riscrittura v4: il probe originale sembrava superato solo perché cancellava anche task e marcatore, e la regressione veniva da quelli. Causa: la relazione `verified-by` veniva ricostruita ad ogni refresh dalla definizione del test e **ristampata con il fingerprint corrente**, quindi non poteva mai risultare stantia — mentre a poche righe di distanza il criterio giusto era già applicato alle relazioni confermate a mano. `TestDefinition` registra ora il `requirement_fingerprint` al momento di `burnup test define`, e la relazione si ricrea solo se combacia; altrimenti decade con `test-definition-stale`. Per tornare a `tested` serve riaffermare la definizione con `--replace` e registrare una nuova esecuzione.

- **C-04 · Un finding chiuso non si riapriva mai.** `burnup finding close` stampa *"Se la condizione che lo ha generato persiste, il prossimo refresh lo riaprirà"*, ma la `FindingFactory` ereditava `status=prior.status`: il rilievo veniva ri-emesso già chiuso e non tornava visibile. `close` era quindi un waiver permanente travestito — proprio ciò che il codice si vieta poche righe più sotto, dove riapre da solo i waiver scaduti perché *"un'eccezione a tempo che non si riapre è un'eccezione permanente travestita"*. Ora solo `waived` e `accepted` sopravvivono alla ri-emissione.

### Aggiunto

- **Il Gate 4 non congela più una baseline con lavoro non salvato.** Ogni refresh su un albero con modifiche non committate a specifiche, task o codice emette `uncommitted-changes` (`high`). `worktree_dirty` era già calcolato e scritto nel Gate Decision Record, ma nessun criterio lo consultava. **Non contano i file scritti dall'engine stesso**: verificato in collaudo che, seguendo la procedura di `CLAUDE.md`, sarebbe il `refresh --strict` obbligatorio ad aver appena riscritto `state/` e `reports/`, rendendo la procedura ineseguibile. L'esclusione è coerente con `TRACEABILITY-RULES.md`, che esclude sempre la directory di output dalla scansione.

### Cambiamenti che rompono la compatibilità

- **`schema_version` del canonical store sale a `3.0`.** `TestDefinition` porta ora `requirement_fingerprints`. Uno store `2.0` non ha quel campo, e interpretarlo come "nessun vincolo" significherebbe considerare valide per sempre proprio le verifiche di cui non ci si può fidare: l'engine si rifiuta di aprirlo, come già fa con qualunque schema sconosciuto. Nessun comando di migrazione, perché non esistono store `2.0` popolati — la beta.1 non è mai stata eseguita su un progetto reale.

### Corretto — secondo giro di collaudo (2026-08-07)

Metodo: invece di cercare bug nelle funzioni, verificare una per una le **promesse scritte** — nel template di configurazione, nei messaggi della CLI, nei documenti normativi. È il metodo che aveva prodotto C-04, applicato sistematicamente.

- **C-05 · Messaggi che rimandavano a comandi inesistenti.** In caso di schema incompatibile l'engine suggeriva `burnup migrate` (store) o `burnup migrate-config` (configurazione): nessuno dei due esiste. Il difetto era latente finché lo schema non cambiava — e il passaggio a `3.0` lo ha reso raggiungibile. I suggerimenti indicano ora azioni realmente eseguibili. Un test verifica che nessuna stringa destinata all'utente citi un comando che la CLI non espone.

- **C-06 · `requirements.default_scope_state` documentato e ignorato.** Letto, validato, salvato nella configurazione e mai applicato: `scope_state` era fissato a `"active"` nel modello. È uno dei cinque campi che la v3 documentava senza usarli (P1-07) e il solo che la v4 non aveva chiuso, malgrado il template dichiari *"Se un campo compare in questo template, ha effetto"*. Ora vale per i requisiti nuovi; un requisito già noto conserva il proprio stato, perché una decisione registrata con `requirement remove` non può essere ribaltata da un default.

- **C-07 · Nessun report JUnit era importabile senza sidecar.** `parse_junit` leggeva l'ora di esecuzione da `root.get("timestamp")`. Funzionava solo con `<testsuite>` come radice; nella forma prodotta da pytest e dalla maggior parte dei CI — `<testsuites>` che avvolge i `<testsuite>` — il timestamp sta sul figlio e veniva ignorato, quindi ogni risultato veniva scartato con `missing-execution-timestamp`. `TEST-REGISTER-SPEC.md` prescriveva già l'ordine corretto: *"testcase@timestamp → testsuite@timestamp → sidecar"*. Ora l'ora e la revisione vengono cercate anche sul `<testsuite>` che contiene il caso.

- **C-08 · Gli errori d'uso collidevano con l'exit code del quality gate.** `ExitCode.USAGE_ERROR = 4` era definito e mai usato: argparse usciva con `2`, che il contratto riserva a "quality gate fallito". Una pipeline non poteva distinguere un refuso sulla riga di comando da un gate respinto — cioè *"hai sbagliato a scrivere"* da *"il codice non è pronto"*. Introdotto un parser che rispetta il contratto.

- **C-09 · `--definition` accettava la stringa vuota**, benché `TEST-REGISTER-SPEC.md` la dichiari obbligatoria. Un catalogo di test senza criterio di esito è un elenco di nomi.

### Corretto — terzo giro di collaudo (2026-08-07)

Perimetri battuti: hook di allowlist, documenti normativi residui, preset Spec Kit, file agente, CI, template, installazione.

- **C-10 · La classe di change non esisteva per l'engine.** `docs/SCALE-ADAPTIVE-FLOW.md` è normativo e prescrive per Fast Track *"Gate: 1 e 4"*; `progress-template.md` lo ripete. Ma la state machine esigeva che ogni gate avesse il precedente valido, quindi il Gate 4 era irraggiungibile senza i Gate 2 e 3, e cercando `fast-track` o `change_class` nel codice non compariva nulla: la classe viveva solo in `progress.md` e nessun meccanismo la leggeva. Introdotto **`burnup feature class <feature> <classe>`**, che registra una decisione permanente con attore e motivo; `check_entry_criteria` usa la sequenza di gate della classe. La promozione in corsa è ammessa, la retrocessione **rifiutata**. Il rigore non scala: `requirement-not-verified` resta `high` e non configurabile in tutte le classi.

- **C-11 · Il hook validava solo il primo segmento di una catena.** `ls && npm install <qualunque cosa>` passava, come `ls; make install` e `pytest && ./script.sh`. Il hook dichiara di coprire *"gli usi accidentali e le scorciatoie"*, e concatenare con `&&` è la scorciatoia per eccellenza. Ora ogni segmento viene validato.

- **C-12 · Senza il nome dell'agente, il hook bloccava anche i Maker.** Con un payload che non dichiarava l'agente, l'allowlist dei Checker si applicava a chiunque — e Solutions Architect e Software Engineer hanno Bash per lavorare. Il README del hook detta il criterio da sé: *"un hook che blocca il lavoro normale viene disattivato, e a quel punto non protegge più nulla"*.

- **C-13 · La tabella degli agenti in `CLAUDE.md` ometteva lo step 0.1**, che la prosa dello stesso file, il file agente e il progress-template assegnano tutti al Solutions Architect. Un test verifica ora che le due fonti coincidano.

- **C-14 · La tabella dei finding di `OPERATING-PROCEDURE.md` era incompleta**: undici tipi su ventitré non erano documentati, quindi l'operatore restava senza istruzioni proprio quando il gate si blocca. Un test verifica che sia esaustiva nei due sensi — niente di emesso che manchi, niente di documentato che non esista.

- **C-15 · L'exit code `4` non era documentato** nella tabella dello stesso runbook.

- **C-16 · Il nome del job della CI dichiarava "23 probe + 7 aggiunti"**, mentre i test reali erano 30 e 14. Un conteggio scritto a mano invecchia al primo test aggiunto: rimosso.

- **C-17 · Artefatti di build spediti nel bundle.** `.coverage`, `.coverage.*` e `.pytest_cache/` erano presenti nella cartella distribuita pur essendo elencati in `.gitignore`.

### Corretto — C-18, introdotto correggendo

- **I sei prompt agente non conoscevano l'engine che invocano.** Aggiungendo `burnup feature class`, tre tipi di finding (`requirement-not-verified`, `test-definition-stale`, `uncommitted-changes`) e l'exit code `4`, i prompt sono rimasti a descrivere la versione precedente. È la stessa classe di scostamento che il collaudo ha passato tre giri a trovare — il codice avanza, la documentazione resta indietro — questa volta commessa mentre si correggeva.

  Conseguenze concrete: il **Technical Auditor** riporta i finding bloccanti ma non sapeva che i tre nuovi esistessero, e aveva in prompt una tabella di exit code incompleta; il **Business Analyst/QA**, unico responsabile delle definizioni di test secondo il RACI, non sapeva che riscrivere un requisito le fa decadere e che serve `test define --replace`; il **Software Engineer** non sapeva che il lavoro non committato blocca il Gate 4; il **Tech Lead** non sapeva che un requisito senza task ora produce un finding bloccante; il **Solutions Architect** non sapeva che in Fast Track `plan.md` non è richiesto; il **Product Manager** non sapeva che riscrivere un requisito già implementato comporta rilavorazione a valle.

  Tutti e sei aggiornati. Il test di coerenza esistente confrontava solo gli **step** fra `CLAUDE.md` e i file agente: il buco stava fuori dal perimetro definito. Aggiunti tre controlli che lo chiudono — nessun prompt può citare un comando che la CLI non espone, l'Auditor deve nominare ogni finding `high` che può bloccare un gate, e ogni exit code deve essere spiegato a chi lo interpreta. **I nuovi controlli hanno trovato subito altre due lacune** nella tabella che avevo appena scritto: `duplicate-requirement-id` e `revision-unavailable`.

### Aggiunto — copertura dei percorsi d'errore

Due file di test dedicati ai percorsi che si vedono solo quando qualcosa va storto: validazioni di configurazione, confinamento dei percorsi, formati di report malformati, verdetti di freschezza, guasti di I/O, layout ambigui. Copertura da **90.34%** a **98.51%**, con 278 test.

La ragione non è la percentuale: C-05 e C-08 stavano entrambi su percorsi d'errore che nessun test attraversava. Un percorso d'errore non esercitato è codice che gira per la prima volta nel momento peggiore, quando chi legge il messaggio ha bisogno che sia esatto.

### Modificato

- `tests/test_integration.py::test_waiver_unblocks_gate_and_is_auditable` registra ora il waiver per ogni condizione bloccante invece che per la prima: con C-01 chiuso le condizioni sono più d'una, e il rinvio va dichiarato requisito per requisito.
- I test che verificano un `refresh --strict` andato a buon fine committano prima lo stato, tramite la nuova fixture `commit`: un albero sporco è ora di per sé una condizione bloccante.

### Nota

- La sezione della beta.1 dichiarava "76 test automatici, 89% di copertura". Il conteggio reale alla data del collaudo era **98 test e 90.34%**; dopo questi interventi **309 test e 100%**, con `fail_under = 100` che blocca le regressioni.

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
