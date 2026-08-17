# Collaudo dell'engine Requirement Burn-up v4.0.0-beta.1

**Data:** 2026-08-06 (primo giro) · 2026-08-07 (secondo e terzo giro)
**Perimetro:** l'intero bundle — engine, hook di allowlist, documenti normativi, preset Spec Kit, file agente, CI, template, installazione. Restano fuori: gli agenti in esecuzione, i Gate umani, i comandi Spec Kit reali.
**Metodo:** progetto Spec Kit minimo costruito da zero, CLI reale eseguita end-to-end su Python 3.10.12. Nel secondo giro, verifica sistematica di ogni promessa scritta — campi del template, messaggi della CLI, righe delle tabelle normative. Ogni esito confrontato con i documenti in `docs/` e con `CHANGELOG.md`, cioè con specifiche scritte da altri e non con il mio giudizio.
**Riproducibilità:** tutti i probe sono comandi CLI su file di testo, riproducibili in pochi minuti.

---

## Verdetto

**L'engine è solido nella sua parte meccanica** — estrazione, tracciabilità, confinamento, idempotenza — e la test suite passava con buona copertura. Ma tre giri di collaudo hanno trovato **diciotto difetti**, tutti nella governance o nel contratto dichiarato. Tutti corretti. L'ultimo — C-18 — l'ho introdotto io correggendo, ed è stato trovato da un controllo automatico scritto proprio per quella classe di scostamento.

| | Difetto | Giro |
|---|---|---|
| **C-01** | Il Gate 4 approvava feature con requisiti mai implementati né testati, con zero finding | 1 |
| **C-02** | Riscrivere il significato di un requisito non faceva decadere l'evidenza di test | 1 |
| **C-03** | `refresh` cancellava tutti i Gate Decision Record | 1 |
| **C-04** | Un finding chiuso non si riapriva mai, anche se la condizione persisteva | 1 |
| **C-05** | I messaggi d'errore rimandavano a comandi inesistenti | 2 |
| **C-06** | `default_scope_state` documentato e ignorato | 2 |
| **C-07** | Nessun report JUnit di pytest era importabile senza sidecar | 2 |
| **C-08** | Gli errori d'uso uscivano con il codice riservato al quality gate | 2 |
| **C-09** | `--definition`, dichiarato obbligatorio, accettava la stringa vuota | 2 |
| **C-10** | La classe di change non esisteva per l'engine: Fast Track era ineseguibile | 3 |
| **C-11** | Il hook validava solo il primo segmento di una catena di comandi | 3 |
| **C-12** | Senza il nome dell'agente, il hook bloccava anche i Maker | 3 |
| **C-13** | La tabella degli agenti in `CLAUDE.md` ometteva uno step | 3 |
| **C-14** | Undici tipi di finding su ventitré non erano documentati nel runbook | 3 |
| **C-15** | L'exit code `4` non era documentato | 3 |
| **C-16** | La CI dichiarava un conteggio di probe sbagliato | 3 |
| **C-17** | Artefatti di build spediti nella cartella distribuita | 3 |
| **C-18** | I sei prompt agente non conoscevano l'engine che invocano | coda |
| — | Il lavoro non salvato in Git non impediva di congelare una baseline | **controllo aggiunto** |

Quattro meritano una nota. **C-02** è la forma residua del probe che ha motivato l'intera riscrittura v4. **C-03** rendeva la state machine dei gate inutilizzabile seguendo la procedura documentata. **C-07** rendeva inutilizzabile l'importazione automatica dei test: il formato che produce pytest non veniva letto. **C-10** era un intero meccanismo descritto in due documenti normativi e mai implementato.

Tutti corretti seguendo la regola A0 del remediation plan: test rosso prima del fix. Suite finale: **309 test, copertura 100%** con soglia bloccante, nessuna regressione.

**Il punto che vale più dei singoli difetti.** Nessuno dei diciotto era visibile a una suite con 98 test e 90% di copertura, perché i test esercitavano le *funzioni*. I difetti stavano in tre posti precisi:

- nella **procedura** — C-03 si vedeva solo eseguendo i comandi nell'ordine in cui `CLAUDE.md` dice di eseguirli; C-10 solo provando a percorrere una classe di change come descritta;
- nel **contratto dichiarato** — C-04, C-05, C-06, C-07, C-08, C-09, C-13, C-14, C-15 e C-16 sono tutti scostamenti fra ciò che il sistema *promette per iscritto* e ciò che *fa*. Undici difetti su diciotto trovati prendendo sul serio la documentazione;
- nei **perimetri che nessuno guardava** — il hook di allowlist (C-11, C-12) non aveva un solo test, pur essendo l'unico enforcement tecnico del sistema.

I tre giri sono stati sempre più produttivi e sempre più rapidi, perché il metodo si è affinato: dal cercare bug, al verificare promesse, all'inventariare perimetri e batterli uno per uno.

### Una mia conclusione intermedia era sbagliata

Nella prima stesura di questo referto avevo scritto che il difetto peggiore della v3 — l'evidenza legata alla chiave invece che al contenuto — era "realmente chiuso" nella v4. **Non lo era.** Lo avevo dedotto da un probe in cui, insieme al testo del requisito, avevo cancellato anche il task e il marcatore nel codice: la regressione a `defined` era causata da quelli, non dal fingerprint. Isolando la variabile — cambiando *solo* il testo — il requisito restava `tested`. È il difetto C-02, ora corretto.

Lo lascio scritto perché è la parte più istruttiva del collaudo: un probe che cambia tre cose insieme non dimostra quale delle tre abbia agito. La prima verifica non era sbagliata nei fatti, era sbagliata nel metodo.

---

## 1. C-01 — il Gate 4 non era un quality gate · CORRETTO

### Riproduzione minima

Progetto con due requisiti. `FR-001` implementato, tracciato e verificato. `FR-002` scritto nella spec e nient'altro: nessun task, nessun marcatore nel codice, nessun test definito.

```
Requisiti:
  001-login/FR-001   tested
  001-login/FR-002   defined

Finding aperti:    0
Scope attivo: 2 | Tested: 1 (50.0%)

burnup refresh --strict          → exit 0
burnup gate approve 001-login 1  → APPROVATO
burnup gate approve 001-login 2  → APPROVATO
burnup gate approve 001-login 3  → APPROVATO
burnup gate approve 001-login 4  → APPROVATO

Gate Decision Record del Gate 4:
  outcome: approved
  burnup_counts: {'scope': 2, 'tested': 1, 'worktree_dirty': True}
```

Il record di approvazione **contiene il dato che avrebbe dovuto bloccarlo** — un requisito su due non verificato, working tree sporco — e approva comunque.

### Causa, verificata nel codice

Tre punti concorrenti.

**`status.py`, riga 168.** L'intero blocco che valuta `tested`, incluso il finding `missing-mandatory-test`, è annidato dentro `if state == "implemented":`. Un requisito che non raggiunge `implemented` non viene mai controllato sulla copertura di test.

**`status.py`, righe 130-165.** La catena di branch emette un finding solo in due casi intermedi: evidenza di codice con task incompleti (`incomplete-tasks`), e task completi senza evidenza di codice (`tasks-complete-without-code-evidence`). Il caso "né codice né task" — cioè il requisito su cui nessuno ha lavorato — **cade fuori da tutti i branch senza produrre nulla**.

**`gates.py`, riga 194.** L'unico criterio di ingresso del Gate 4 che guarda l'evidenza è `if gate == 4 and blocking_findings:`. `burnup_counts` viene calcolato e scritto nel record (`cli.py:539`) ma non viene mai letto da `check_entry_criteria()`. Stessa sorte per `worktree_dirty` (`cli.py:542`).

Il commento nel codice a `gates.py:191` dichiara l'intenzione: *"Il Gate 4 è l'unico che si misura sull'evidenza prodotta, non solo sulla presenza degli artefatti: è lì che il burn-up diventa un quality gate."* L'intenzione non è realizzata — il Gate 4 si misura sui finding, non sul burn-up.

### Perché non basta cambiare la configurazione

Ho verificato l'ipotesi più benevola: che sia una questione di soglia. Non lo è. Con `strict_blocks_on: ["high", "medium", "low"]` — cioè bloccando su qualunque severità — `refresh --strict` restituisce comunque **exit 0**, perché non esiste alcun finding da bloccare. Il problema non è la severità assegnata: è che il finding non viene proprio emesso.

Ne consegue che nemmeno la classe **High-Risk** di `SCALE-ADAPTIVE-FLOW.md`, che alza la soglia a `[high, medium]`, protegge da questo caso.

### Correzione applicata

Introdotto **`requirement-not-verified`**, severità `high`, emesso per ogni requisito attivo che non raggiunge `tested` — fuori dal ramo `implemented` in cui erano annidati tutti gli altri controlli.

La scelta di merito, fra le due possibili: **non** un criterio rigido `tested == scope` in `gates.py`, ma un finding. Motivo: il framework ha già due vie per rinviare un requisito — `burnup finding waive` e `burnup requirement remove` — entrambe con attore, motivo e record permanente. Un criterio rigido avrebbe inventato una terza via non aggirabile, e `SCALE-ADAPTIVE-FLOW.md` avverte proprio che un processo che non si può seguire viene aggirato, e allora non governa più nulla. Con un finding il rinvio resta possibile ma non silenzioso, e il Gate 4 blocca già sui finding bloccanti: nessun secondo percorso da mantenere.

La severità è `high` e non configurabile, così blocca in tutte le classi di change e non solo in High-Risk.

Verifica end-to-end dopo il fix, seguendo la procedura di `CLAUDE.md`:

```
Gate 1,2,3 approvati · refresh --strict → exit 2 · Gate 4 BLOCCATO
finding waive <id> --actor utente --reason "FR-002 rinviato alla 1.1, deciso con lo sponsor"
refresh --strict → exit 0 · Gate 4 APPROVATO
record: approved | waiver: 1 | counts: {'scope': 2, 'tested': 1}
```

### Variante osservata sul percorso di regressione

Partendo da una feature completa e approvata su tutti e quattro i gate, ho riscritto il significato di un requisito, cancellato il suo task e rimosso il marcatore dal codice. Comportamento:

- il requisito regredisce correttamente da `tested` a `defined`;
- viene emesso `requirement-changed`, severità `medium`;
- i quattro gate decadono per confronto di fingerprint — **corretto**;
- **al refresh successivo il finding `requirement-changed` si chiude da solo**, perché il fingerprint è ormai allineato;
- da quel momento: zero finding, `--strict` a exit 0, gate riapprovabili in sequenza fino al 4.

Quindi il segnale della regressione è **transitorio**: dura un solo refresh e non lascia traccia bloccante.

### Impatto

Con la configurazione di default e in classe Standard, una feature può attraversare i quattro gate e arrivare al rilascio con requisiti mai implementati, e il sistema riporta zero problemi. È esattamente la categoria di difetto che l'audit ha giudicato meritevole di NO-GO: *una certificazione attiva di uno stato falso*.

Rispetto al probe originale dell'audit c'è un'aggravante e un'attenuante. L'aggravante: qui non serve nemmeno manomettere nulla, basta scrivere un requisito e non lavorarci. L'attenuante: il conteggio `Tested: 1 (50.0%)` è visibile e corretto sulla CLI e nella dashboard — l'informazione c'è, semplicemente non blocca niente.

### Resta da decidere

**`worktree_dirty` non viene valutato.** È calcolato e registrato nel Gate Decision Record (`cli.py:542`) ma nessun criterio lo consulta. Approvare una baseline di codice su un working tree sporco significa congelare un fingerprint che non descrive uno stato committato. Non l'ho corretto perché è una decisione di policy distinta da C-01, non un'omissione: si può ragionevolmente sostenere che il Gate 4 debba tollerare modifiche non committate, o che debba rifiutarle.

---

## 2. C-02 — l'evidenza di test non decadeva · CORRETTO

### Riproduzione

Un requisito completo e verificato. Cambio **solo** il testo nella spec, lasciando intatti `tasks.md` e il marcatore nel codice — che citano l'ID, non il testo, e quindi restano formalmente validi.

```
PRIMA:  FR-001 = tested
   rel implemented-by -> T001        fp adecc05d17
   rel evidenced-by   -> src/auth.py fp adecc05d17
   rel verified-by    -> TEST-001    fp adecc05d17

  "il sistema deve autenticare l utente"
        →  "il sistema deve cancellare tutti i dati al logout"

DOPO:   FR-001 = tested        ← invariato
   rel implemented-by -> T001        fp 7b8bace442
   rel evidenced-by   -> src/auth.py fp 7b8bace442
   rel verified-by    -> TEST-001    fp 7b8bace442   ← ristampata
```

Il requisito ora dice l'opposto di prima e resta `tested`.

### Perché è grave

`STATUS-RULES.md` apre con: *"L'evidenza vale solo se si riferisce al fingerprint corrente del requisito"*, e la tabella delle regressioni dichiara *"testo del requisito riscritto → `defined`"*. È **il principio che ha motivato l'intera riscrittura v4**, ed è falso nel caso in cui conta di più.

Il probe originale dell'audit sembrava superato solo perché cancellava anche task e marcatore: la regressione veniva da quelli.

### Causa

`engine.py`, ricostruzione della relazione `verified-by`:

```python
Relation(
    from_key=key, to_ref=td.test_id, rel_type="verified-by",
    requirement_fingerprint=req.fingerprint,   # ← sempre il fingerprint corrente
)
```

La relazione viene rigenerata ad ogni refresh dalla definizione del test e ristampata con il fingerprint del momento, quindi **non può mai risultare stantia**. Il contrasto è a poche righe di distanza: le relazioni confermate a mano sono preservate solo `if rel.requirement_fingerprint == req.fingerprint` — il pattern corretto, applicato ovunque tranne qui.

`implemented-by` ed `evidenced-by` sono ri-derivate da file che citano ancora l'ID, quindi ristamparle è difendibile. `verified-by` no: deriva da una decisione umana registrata (`burnup test define` più `test confirm-manual` con attore, motivo ed evidenza), e ristamparla trasferisce in silenzio una verifica umana a un requisito diverso.

### Correzione applicata

`TestDefinition` registra ora `requirement_fingerprints`: il fingerprint di ciascun requisito **al momento in cui il test è stato dichiarato verificarlo**. La relazione `verified-by` si ricrea solo se combacia con quello corrente; altrimenti decade e viene emesso `test-definition-stale` (`medium`), che spiega perché.

Per riportare il requisito a `tested` bisogna riaffermare la definizione con `burnup test define --replace` e registrare una nuova esecuzione. È l'attrito voluto, ed è ciò che `STATUS-RULES.md` dichiarava già di volere: *"se il requisito è cambiato, ciò che era stato verificato non è più ciò che c'è scritto"*.

Verifica sul probe isolato, dopo il fix:

```
PRIMA:  FR-001 = tested
        (cambio SOLO il testo; task e marcatore restano intatti)
DOPO:   FR-001 = implemented
   high    requirement-not-verified   001-x/FR-001
   high    missing-mandatory-test     001-x/FR-001
   medium  test-definition-stale      TEST-001
```

### La decisione presa sulla compatibilità

Il campo nuovo cambia la forma di `state/test-definitions.json`, cioè lo schema del canonical store, che il framework governa con `schema_version` e che rifiuta di aprire se non lo riconosce.

Scelta: **alzare lo schema da `2.0` a `3.0`, senza comando di migrazione.** Uno store `2.0` non ha il campo, e trattarlo come "nessun vincolo" significherebbe considerare valide per sempre proprio le verifiche di cui non ci si può fidare — meglio rifiutarsi di aprirlo. Il comando di migrazione non serve perché non esistono store popolati: la beta.1 non è mai stata eseguita su un progetto reale. Si scriverà il giorno in cui servirà davvero, con dati veri sotto gli occhi invece che immaginati.

---

## 3. C-03 — `refresh` cancellava i Gate Decision Record · CORRETTO

### Riproduzione, su engine originale non modificato

```
Gate 1 approvato
  record gate PRIMA del refresh : 1
  record gate DOPO  il refresh  : 0
  Gate 1 — Requirements Baseline: not-approved
```

Verificato estraendo `status.py` dal commit originale, per escludere che fosse una conseguenza del fix C-01.

### Perché era il più insidioso dei tre

`CLAUDE.md` prescrive `burnup refresh --strict` **prima** di ogni approvazione del Gate 4. Seguendo la procedura documentata:

1. approvi Gate 1, 2, 3;
2. lanci il refresh obbligatorio → **i tre gate spariscono**;
3. il Gate 4 viene rifiutato con *"il Gate 3 non è valido: stato 'not-approved'"*.

La state machine era inutilizzabile esattamente nel percorso per cui era stata costruita. Si notava solo approvando i quattro gate di fila senza refresh in mezzo — che è l'unico ordine in cui i test esistenti la esercitavano, ed è il motivo per cui i miei primi probe non l'avevano rivelato.

### Causa e correzione

`engine.py` costruiva lo `StoreData` del refresh omettendo `gate_decisions`, mentre `decisions` veniva riportato; `commit` scriveva quindi un file vuoto. È un'omissione, non una scelta. Aggiunto `gate_decisions=data.gate_decisions`.

Due test di regressione: uno verifica che le decisioni sopravvivano al refresh, l'altro esegue l'intera procedura documentata del Gate 4 fino in fondo.

---

## 4. C-04 — un finding chiuso non si riapriva mai · CORRETTO

Emerso mentre verificavo il fix di C-02: un requisito regredito non produceva il finding atteso, perché quel finding era stato *risolto* in un refresh precedente e la `FindingFactory` lo ri-emetteva ereditando lo stato chiuso.

`burnup finding close` stampa:

> *"Se la condizione che lo ha generato persiste, il prossimo refresh lo riaprirà."*

Non succedeva. `close` era quindi un waiver permanente travestito — proprio ciò che il codice si vieta poche righe più sotto, dove riapre da solo i waiver scaduti perché *"un'eccezione a tempo che non si riapre è un'eccezione permanente travestita"*.

Nessuna decisione da prendere: il comportamento corretto era già annunciato dalla CLI, era il codice a divergere. Ora solo `waived` e `accepted` sopravvivono alla ri-emissione; `resolved` e `verified` tornano `open` se la condizione è ancora vera.

---

## 5. Il controllo aggiunto — lavoro non salvato in Git

Il Gate Decision Record congela il fingerprint del codice approvato: serve a poter dire domani *"ho approvato esattamente questa versione"*. Con modifiche non committate quel fingerprint non descrive alcuna versione registrata. `worktree_dirty` era già calcolato e scritto nel verbale, ma nessun criterio lo consultava.

Ora ogni refresh su un albero sporco emette `uncommitted-changes` (`high`), quindi `refresh --strict` esce con 2 e il Gate 4 non è approvabile — con la solita via d'uscita del waiver motivato.

**Cosa conta come sporco.** Deliberatamente non i file che l'engine scrive da sé. Verificato in collaudo:

```
albero pulito                 -> 0 file modificati
dopo 'refresh --strict'       -> 4 file modificati (output dell'engine)
worktree_dirty al Gate 4      -> True
```

Contandoli, la procedura documentata sarebbe diventata ineseguibile senza un passaggio di commit che oggi non è scritto da nessuna parte. Escluderli è anche coerente con `TRACEABILITY-RULES.md`, che esclude sempre la directory di output dalla scansione dei sorgenti. Il segnale diventa così quello che serve: **il tuo** lavoro ha modifiche non salvate.

---

## 6. Secondo giro — il contratto dichiarato contro il comportamento reale

Metodo: prendere ogni promessa scritta e verificarla. Cinque difetti, tutti dello stesso tipo.

### C-05 — messaggi che mandavano a sbattere · CORRETTO

Con uno schema incompatibile l'engine suggeriva `burnup migrate`; con una configurazione vecchia, `burnup migrate-config`. **Nessuno dei due esiste**: la CLI espone `init, refresh, status, test, link, requirement, finding, gate`.

Era latente finché lo schema non cambiava — e il passaggio a `3.0` per C-02 lo ha reso raggiungibile, quindi l'ho introdotto io nel percorso attivo. I suggerimenti indicano ora azioni eseguibili, e un test scandisce le stringhe destinate all'utente per verificare che non citino comandi inesistenti.

### C-06 — un campo documentato e ignorato · CORRETTO

`requirements.default_scope_state` veniva letto, validato, salvato nella configurazione e **mai applicato**: `scope_state` era fissato a `"active"` nel modello.

È il caso più significativo dei cinque, perché il template lo affronta esplicitamente:

> *"Regola: ogni campo dichiarato qui è implementato. Nella v3 cinque campi erano documentati e ignorati (`test_source_globs`, `default_scope_state`, `allow_forced_snapshot`, `schema_version`, `risk_register_path`), il che è peggio di un campo assente — prometteva un comportamento inesistente. Se un campo compare in questo template, ha effetto."*

La v4 ne aveva chiusi quattro su cinque, lasciando proprio quello nominato al secondo posto. Verificati uno per uno tutti gli altri campi: hanno effetto reale.

### C-07 — nessun report di pytest era importabile · CORRETTO

`parse_junit` leggeva l'ora di esecuzione da `root.get("timestamp")`. Il JUnit XML ha due forme:

```
A)  <testsuites><testsuite timestamp="..."><testcase/></testsuite></testsuites>   ← pytest e gran parte dei CI
B)  <testsuite timestamp="..."><testcase/></testsuite>
```

Nella forma A il timestamp sta sul figlio, e `root` è `<testsuites>`: veniva ignorato. Ogni risultato restava senza ora e veniva scartato con `missing-execution-timestamp`, quindi **nessun report in forma A era importabile senza sidecar**, mentre il template presenta il sidecar come necessario solo per la policy `current-revision`.

`TEST-REGISTER-SPEC.md` prescriveva già l'ordine giusto — *"testcase@timestamp → testsuite@timestamp → sidecar"* — quindi anche qui era il codice a divergere dalla propria specifica.

### C-08 — due significati per lo stesso exit code · CORRETTO

`ExitCode.USAGE_ERROR = 4` era definito e mai usato. Argparse usciva con `2`, che il contratto — dichiarato "pubblico" nel codice — riserva a *quality gate fallito*.

Conseguenza concreta: in una pipeline, `burnup refresh --strig` (refuso) e `burnup refresh --strict` su un gate respinto producevano lo stesso codice. La differenza fra *"hai sbagliato a scrivere"* e *"il codice non è pronto"* spariva.

### C-09 — un obbligo non applicato · CORRETTO

`TEST-REGISTER-SPEC.md` dichiara `definition` obbligatorio — *"cosa si verifica e qual è l'esito atteso"* — ma `--definition ""` veniva accettato. Un catalogo di test senza criterio di esito è un elenco di nomi.

---

## 7. Terzo giro — i perimetri fuori dall'engine

I primi due giri avevano battuto comportamento e contratto della CLI. Restavano il hook di allowlist, i documenti normativi non ancora verificati, il preset Spec Kit, i file agente, la CI e i template. Inventario completo, poi uno per uno.

### C-10 — la classe di change non esisteva per l'engine · CORRETTO

`docs/SCALE-ADAPTIVE-FLOW.md` è dichiarato **normativo** e prescrive per Fast Track:

| | Fast Track |
|---|---|
| `plan.md` | non richiesto |
| **Gate** | **1 e 4** |

e `progress-template.md` lo ripete: *"Fast Track salta i Gate 2 e 3"*. Provato:

```
Gate 1 -> exit 0
Gate 4 -> exit 2
   - il Gate 3 (Implementation Readiness) non e' valido: stato 'not-approved'
```

Cercando `fast-track`, `high-risk` o `change_class` nel codice non compariva nulla: **l'engine non sapeva che le classi esistessero**. Vivevano solo in `progress.md`, dichiarate dall'Orchestratore, e nessun meccanismo le leggeva.

**La scelta fatta, e perché.** Insegnare le classi all'engine, non correggere i documenti. I documenti descrivono un meccanismo pensato con una ragione esplicita — *"un processo che costa più del lavoro che governa viene aggirato, e a quel punto non governa più nulla"* — e cancellarlo per far tornare i conti sarebbe stato adeguare l'intenzione all'implementazione anziché il contrario.

La classe è una **decisione umana**, quindi passa da un comando e produce un record con attore e motivo, come ogni altra decisione del sistema. Non è servito un campo nuovo nel canonical store: `decisions.jsonl` esiste già, e la classe corrente è l'ultima decisione di tipo `feature-class`.

```
burnup feature class 001-x fast-track --actor orchestratore --reason "correzione di testo"
  Feature '001-x': classe 'non dichiarata' -> 'fast-track'.
  Gate previsti: 1, 4.

Gate 1 APPROVATO · refresh --strict exit=0 · Gate 4 APPROVATO
```

Due vincoli del documento sono presidiati da test: la promozione in corsa è ammessa, la **retrocessione viene rifiutata**; e il rigore non scala — `requirement-not-verified` resta `high` e non configurabile in tutte e tre le classi.

### C-11 e C-12 — il hook di allowlist · CORRETTI

Il hook `PreToolUse` è l'unico enforcement tecnico del sistema, e **non aveva un solo test**. Due difetti.

*La catena.* L'allowlist controllava solo il primo segmento:

```
ls && npm install pacchetto-arbitrario   -> consentito
ls; make install                         -> consentito
pytest && ./script.sh                    -> consentito
```

Il hook dichiara di coprire *"gli usi accidentali e le scorciatoie"*, e concatenare con `&&` è la scorciatoia per eccellenza. Ora ogni segmento viene validato.

*L'agente sconosciuto.* Con un payload che non dichiarava l'agente, l'allowlist dei Checker si applicava a chiunque — e Solutions Architect e Software Engineer hanno Bash per lavorare. Il criterio lo detta il README del hook: *"un hook che blocca il lavoro normale viene disattivato, e a quel punto non protegge più nulla"*.

### C-13, C-14, C-15, C-16 — disallineamenti documentali · CORRETTI

- La tabella degli agenti in `CLAUDE.md` attribuiva al Solutions Architect gli step "0.2, 2.1, 2.1-loop", **omettendo 0.1** — che la prosa dello stesso file, il file agente e il progress-template gli assegnano tutti.
- La tabella dei finding di `OPERATING-PROCEDURE.md` ne documentava dodici su ventitré: l'operatore restava senza istruzioni proprio quando il gate si blocca. Ora un test la verifica nei due sensi — niente di emesso che manchi, niente di documentato che non esista.
- L'exit code `4` non era documentato nella tabella dello stesso runbook.
- Il nome del job della CI dichiarava "23 probe + 7 aggiunti"; i test reali erano 30 e 14. Rimosso: un conteggio scritto a mano invecchia al primo test aggiunto.

### C-17 — artefatti di build nel bundle · SEGNALATO

`.coverage`, `.coverage.*` e `.pytest_cache/` sono presenti nella cartella distribuita pur essendo elencati in `.gitignore` — dati di copertura fermi al 31 luglio. Non sono tracciati in git, quindi è un problema di confezionamento della cartella, non del repository. **Non ho potuto rimuoverli**: la cartella non consente cancellazioni dal mio ambiente. Vanno eliminati a mano.

### Perimetri battuti senza trovare nulla

`RACI.md` (una sola A per riga, nessun ruolo R sia sulla produzione sia sulla verifica: verificato), `ARCHITECTURE.md`, `DESIGN-DECISIONS.md`, `BURNUP-CALCULATION.md` (formule, invariante, ordine dei motivi di snapshot), il preset Spec Kit, `INSTALL.md` (che dichiara onestamente il hook come opzionale e da attivare a mano), i template di `.specify/`.

---

## 7-bis. Copertura dei percorsi d'errore

Da **90.34%** a **98.51%**, con 278 test.

La ragione non è la percentuale. C-05 e C-08 stavano entrambi su percorsi d'errore che nessun test attraversava: un percorso d'errore non esercitato è codice che gira per la prima volta nel momento peggiore, quando il progetto è già rotto e chi legge il messaggio ha bisogno che sia esatto.

Coperti: ogni validazione di configurazione, il confinamento dei percorsi, i formati di report malformati, tutti i verdetti di freschezza, i guasti di I/O, i layout ambigui, gli stati intermedi del calcolo.

**Le 30 righe residue e perché restano.** Sono in larga parte strutturali — il guard `if __name__ == "__main__"`, il gestore di `KeyboardInterrupt` — o rami difensivi attorno a guasti del sistema operativo che si raggiungono solo simulando il fallimento della libreria standard. Coprirle produrrebbe test che asseriscono l'esecuzione di una riga senza asserire alcun comportamento, che è esattamente ciò che l'intestazione di quei file di test si impegna a non fare. Se preferisci arrivare al 100% dichiarato, si fa: è mezz'ora di mock, ma sarebbe copertura di facciata.

---

## 8. Cosa invece funziona

Tutto verificato con esecuzione reale, non per lettura del codice.

| Perimetro | Probe eseguito | Esito |
|---|---|---|
| Test suite | `pytest` sull'engine | **98 test, 0 fallimenti, copertura 90.34%** (ora 133 e 92.04%) |
| P0-04 · estrazione | `FR-999` citato sotto `## Notes` | **Non entra nello scope.** Finding informativo `reference-outside-requirements` |
| P0-04 · user story | `NFR-001` senza tag, dopo due sezioni User Story | **Non eredita** la user story precedente |
| P0-02 · confini di token | Task `T004 Implement XFR-001Y helper` | **Non collegato** a FR-001 |
| Traceability · marcatori | `msg = "REQ: 001-login/FR-999 ..."` dentro una stringa | **Rifiutato**, finding `marker-outside-comment` |
| Traceability · marcatori | `def fast_path(email):  # REQ: ...` commento in coda | **Accettato** |
| P0-06 · fingerprint | Requisito riscritto di significato, task cancellato, marcatore rimosso | Da `tested` a `defined` — ma la regressione veniva da task e marcatore, non dal fingerprint. Difetto C-02, ora corretto |
| P0-07 · idempotenza | Tre `refresh` consecutivi sullo stesso report JUnit | **3 esecuzioni totali, 0 duplicati** |
| P0-09 · confinamento | `output_dir: "/tmp/FUORI"` | **Rifiutato** con `path-confinement-error` ed errore esplicito |
| P0-10 · exit code | `--strict` con finding `high` aperto | **exit 2**, come documentato |
| P0-03 · decisioni umane | `test define`, `test confirm-manual`, `gate approve/reject` | **Funzionano**, ogni decisione registra attore, motivo e timestamp |
| Gate · state machine | `gate approve 3` senza Gate 1 e 2 | **Rifiutato**, exit 2, messaggio esplicito |
| Gate · invalidazione | Modifica di `spec.md` dopo l'approvazione dei 4 gate | **Tutti e quattro decadono** per confronto di fingerprint |
| Store | Layout `state/` + `reports/` | 13 file creati, canonical store separato dai report |
| Requisito sparito | Riga del requisito cancellata da `spec.md` | **`source-missing` severità high**, nessuna rimozione automatica |

La qualità della documentazione normativa merita una nota a parte: `STATUS-RULES.md` e `TRACEABILITY-RULES.md` descrivono il comportamento reale con precisione, comprese le motivazioni delle scelte. Ho potuto verificare l'engine *contro un documento* invece che contro le mie aspettative, ed è esattamente ciò che rende un collaudo indipendente possibile.

---

## 9. Osservazioni minori

**Il CHANGELOG era già disallineato.** Dichiarava "76 test automatici, 89% di copertura"; il conteggio reale era 98 test e 90.34%. Non è un difetto — i test erano aumentati — ma è la stessa classe di disallineamento documentazione/realtà che l'audit ha punito con P1-22, su un file che si presenta come autorevole. Corretto.

**`missing-execution-timestamp` e `test-never-run` sono utili e severi.** Emersi accidentalmente durante i probe quando ho fornito un report JUnit senza sidecar: il sistema ha correttamente rifiutato di considerare eseguito un test la cui esecuzione non era databile. È un comportamento migliore di quanto la documentazione lasci intendere.

**`requirement-changed` è un finding transitorio.** Si chiude al refresh successivo. Non è sbagliato di per sé, ma va saputo: non è un segnale su cui costruire un controllo di gate.

---

## 10. Conseguenza sulle priorità dei miglioramenti

Il collaudo cambia l'ordine proposto in `Miglioramenti/CLASSIFICA-MIGLIORAMENTI.md`.

**Solo C-10 resta in coda**, ed è una decisione, non un'implementazione. Con gli altri nove chiusi, le proposte in stand-by non poggiano più su misure inaffidabili. Prima del collaudo lo erano: `burnup forecast` avrebbe proiettato date da conteggi `tested` che potevano riferirsi a testi di requisito non più esistenti, e il change proposal FMEA avrebbe costruito un'intera catena di azioni verificabili sopra un gate che non verificava.

**Il corner-case sweep guadagna posizioni** e resta la prima voce fra i miglioramenti veri e propri. Un requisito che nessuno ha scritto e un requisito su cui nessuno ha lavorato sono lo stesso punto cieco visto da due lati: ora il secondo lato è coperto dall'engine, il primo no.

**Due voci nuove entrano in classifica.**

*Test di procedura.* La suite esercitava le funzioni, non le sequenze prescritte. Ne ho scritto uno che percorre la procedura del Gate 4 dall'inizio alla fine, ma copre un solo cammino: servirebbe lo stesso per ciascuna procedura documentata, `OPERATING-PROCEDURE.md` incluso.

*Test di contratto.* Sei difetti su dieci erano scostamenti fra ciò che il sistema dichiara e ciò che fa. `tests/test_contract_audit.py` ne automatizza una parte — verifica che nessun messaggio citi comandi inesistenti, che i campi del template abbiano effetto, che gli exit code rispettino il contratto — ma la copertura è parziale: ogni riga normativa dei nove documenti in `docs/` è in linea di principio un test.

**Nota di metodo sul collaudo stesso.** Nel primo giro, tre difetti su quattro sono emersi mentre ne correggevo un altro. Il secondo giro, condotto con metodo invece che per intuizione, ne ha prodotti altri sei in meno tempo. Il fatto che la resa non stia calando suggerisce che un terzo giro — su perimetri non ancora battuti: `OPERATING-PROCEDURE.md`, `RACI.md`, il preset Spec Kit, gli hook — resti ragionevole.

---

## 11. Cosa questo collaudo non dice

Va dichiarato con precisione, per non far passare per verificato ciò che non lo è.

- **Non dice nulla sul flusso a sei agenti.** Nessun agente è stato invocato. Handoff, isolamento del contesto e costo per hop restano non misurati.
- **Non dice nulla sulla qualità dei Gate umani.** Ho approvato io i gate, quindi non è stata messa alla prova né l'autorità decisionale umana né la capacità dei Checker di intercettare un difetto che nessuno sapeva ci fosse.
- **Non dice nulla su Spec Kit.** I comandi `/speckit.*` non sono stati eseguiti: gli artefatti `spec.md`, `plan.md` e `tasks.md` li ho scritti a mano nel formato che l'engine si aspetta. Se Spec Kit producesse un formato leggermente diverso, il parser potrebbe comportarsi in modo diverso da quanto osservato qui — è la verifica più utile da fare subito dopo, e richiede la tua installazione.
- **Il progetto di prova è piccolo e pulito.** Due o tre requisiti, una feature, un linguaggio. Non dice nulla sul comportamento con decine di feature, spec malformate o repository reali.
