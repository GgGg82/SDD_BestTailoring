# Audit + simulazione sul campo — SDD Multi-Agent Framework

**Versione consegnata:** `4.0.0-rc.2` · **Partenza:** `4.0.0-rc.1` · **Data:** 2026-08-09
**Metodo:** un progetto Spec Kit costruito da zero, i sei agenti impersonati nell'ordine prescritto da `CLAUDE.md`, pytest vero, JUnit vero, Git vero. Poi 40 feature sintetiche per la scala.

---

## 1. Sintesi

| | Prima | Dopo |
|---|---|---|
| Difetti noti | 0 dichiarati | **8 trovati, 8 corretti** |
| Test | 309 | **339** |
| Copertura | 100% | **100%** (soglia bloccante) |
| Feature portate a termine end-to-end | 0 | **2** (una Standard, una Fast Track) |
| Requisiti misurati | — | **486** su 41 feature |

**Perché la rc.1 non li aveva visti.** La rc.1 è stata verificata leggendo il codice e i documenti, e da lì aveva chiuso 18 difetti. Questi otto stanno altrove: nell'**attrito fra l'engine e gli strumenti che lo circondano** — la forma esatta di un SHA scritto da una pipeline, il Markdown che un LLM genera davvero, l'output letto da un agente con un contesto finito. Nessuna suite unitaria li poteva vedere, perché ognuno richiede che qualcosa *fuori* dall'engine si comporti come si comporta nella realtà.

---

## 2. Gli otto difetti

Legenda: **P0** impedisce al sistema di fare ciò per cui esiste · **P1** rompe una procedura documentata · **P2** disallineamento fra ciò che dichiara e ciò che fa · **P3** documentazione.

| ID | Grav. | Difetto | Come si manifestava | Correzione |
|---|:---:|---|---|---|
| **C-21** | **P0** | `current-revision` — «la policy rigorosa» — era **insoddisfabile** | L'engine legge la propria revisione con `--short` (7 char) e la confrontava per uguaglianza con quella del sidecar; `git rev-parse HEAD` ne produce 40. Ogni requisito fermo a `implemented`, **Gate 4 mai approvabile**. Il rilievo stampava *«eseguito su e8d3138e4915…, la revisione corrente e' e8d3138»* — lo stesso commit, presentato come due | Confronto per prefisso, come fa Git con le abbreviazioni, minimo 7 caratteri |
| **C-20** | P1 | Un task con l'ID in grassetto **spariva senza rilievo** | `- [x] **T001** [REQ:FR-001] …` non combaciava con la regex. Sintomo: `incomplete-tasks` su ogni requisito → si guarda `tasks.md`, lo si trova tutto spuntato, si conclude che l'engine sbaglia i conti | L'enfasi Markdown è assorbita; il formato del preset resta valido |
| **C-19** | P1 | Un'eccezione inattesa usciva con **exit 1** (`CONFIG_ERROR`) | `main()` intercettava due soli tipi. Chi legge veniva mandato a correggere la propria configurazione mentre il guasto era nell'engine. È il difetto che il docstring di `errors.py` **dichiara chiuso dalla v3 in avanti** | Exit `3` con messaggio che dice che è un bug |
| **C-26** | P2 | L'elenco dei finding cresceva senza limite | 486 requisiti → **491 righe** di output. Il consumatore principale è un agente con una finestra di contesto finita | Si ferma a 20, riassume la coda per tipo, rimanda a `--json` |
| **C-24** | P2 | `gate status` non diceva quali gate esistono | `change_class` era in `--json` ma non nella vista umana; i Gate 2 e 3 di una Fast Track comparivano come `not-approved`, cioè come lavoro da fare | Intestazione con classe e gate previsti; i non previsti marcati tali |
| **C-23** | P2 | `uncommitted-changes` non diceva **quali** file | Manda a cercare senza dire dove | Nomina i file (max 10, poi riassume), gestisce le rinomine |
| **C-22** | P3 | Il diagramma del ciclo di vita mostrava `tested → defined` | La transizione reale è `tested → implemented` | Diagramma corretto + callout sull'asimmetria |

> **C-21 è il difetto più grave trovato in tutto il lavoro su questo framework**, incluso il collaudo della rc.1. Non produce un numero sbagliato: rende **inutilizzabile il percorso principale** — la policy rigorosa, quella che un progetto serio sceglierebbe — e lo fa con un messaggio che sembra confermare che il sistema funziona (*«eseguito su X, la revisione corrente è Y»*, due stringhe diverse). Un utente ci avrebbe passato ore prima di sospettare l'engine.

---

## 3. Cosa la simulazione ha confermato funzionare

Vale quanto i difetti, perché è la prima volta che viene verificato eseguendo.

| Meccanismo | Esito |
|---|---|
| **Ciclo Standard completo, Gate 1→4** | Chiuso. `Scope 5 · Implemented 5 · Tested 5 · 0 findings` |
| **Fast Track** | Gate 4 approvato subito dopo il Gate 1, senza reclamare i Gate 2 e 3 — C-10 validato sul campo |
| **Retrocessione di classe** | Rifiutata, con la motivazione corretta |
| **Invalidazione a cascata** | Modificare `tasks.md` dopo il Gate 3 ha invalidato Gate 3 e 4 automaticamente |
| **Decadenza dell'evidenza** (il P0 della v3) | Riscrivendo FR-001 da «registrare un prestito» a «cancellare i dati del lettore»: `Tested 5→4`, `test-definition-stale`, `requirement-changed`, tutti i gate invalidati, `--strict` exit 2 |
| **Recupero** | `test define --replace` con attore e motivo → 0 findings. L'attrito è esattamente quello voluto |
| **JUnit di pytest reale** | Importato correttamente — la forma che aveva motivato C-07, ora validata su output vero e non sintetico |
| **Gate 4 con criteri non soddisfatti** | Rifiutato in tutti i casi provati: senza `plan.md`, senza `tasks.md`, con finding bloccanti, con gate precedente invalidato |
| **Prestazioni** | 486 requisiti su 41 feature: **0,21 s**, 27 MB |

---

## 4. Un sospetto P0 ritirato

Avevo diagnosticato un P0: *«l'engine sporca il worktree scrivendo i propri file, e così invalida la propria evidenza ad ogni refresh»*. Sintomo coerente: `Tested: 0`, e `git status` mostrava **solo** file dell'engine.

**Era falso.** L'esclusione dei file dell'engine funziona correttamente. Il file sporco era un `.pyc` tracciato per errore da me, che `git status` non mostrava perché lo stavo leggendo filtrato.

Lo registro perché è la prova più forte a favore di C-23: **con accesso completo al sorgente ho comunque diagnosticato male**, perché il messaggio non nomina i file. Un utente senza quel accesso non avrebbe avuto scampo. Il difetto minore ha causato l'errore diagnostico maggiore.

---

## 5. Le correzioni verificate contro la simulazione

Non basta che la suite sia verde: ogni fix è stato riprovato sul progetto reale.

| Fix | Prova |
|---|---|
| C-21 | Sidecar con `git rev-parse HEAD` (40 char) → `Tested: 6` |
| C-20 | `tasks.md` con `**T001**` → `Implemented: 6` |
| C-26 | 486 requisiti → **27 righe** invece di 491 |
| C-24 | `gate status` Fast Track → «classe: fast-track — gate previsti: 1, 4» |
| C-23 | Il rilievo ora dice: «File interessati: `specs/001-prestiti/tasks.md`» |

**Cinque dei nuovi test hanno trovato difetti nelle correzioni stesse** mentre le scrivevo — fra cui uno `.strip()` che spostava di un carattere ogni percorso restituito, e una regressione di firma che il fix C-19 ha intercettato correttamente come `engine-error` invece di lasciarla uscire come traceback. La regola A0 (test rosso prima del fix) ha pagato immediatamente.

---

## 6. Cosa questo lavoro ancora non dice

| Non verificato | Perché |
|---|---|
| **Il flusso a sei agenti in esecuzione** | Ho impersonato gli agenti, non li ho invocati. Handoff, isolamento del contesto e costo per hop restano non misurati |
| **La qualità dei Gate umani** | Ho approvato io: non è stata messa alla prova la capacità dei Checker di trovare un difetto che nessuno sapeva ci fosse |
| **I comandi Spec Kit reali** | `spec.md`, `plan.md`, `tasks.md` scritti a mano nel formato atteso. Il JUnit invece è vero, e lì un difetto è emerso |
| **L'hook di allowlist in esecuzione** | Testato unitariamente, mai attivo in una sessione reale |
| **Spec malformate su larga scala** | Le 40 feature sintetiche sono ben formate |

---

## 7. Perché `rc.2` e non `4.0.0`

Un release candidate dichiara: *nessun difetto noto, non ancora usato in produzione*. La rc.1 lo dichiarava e **otto difetti sono emersi al primo uso reale**, uno dei quali P0. Questo non toglie valore alla rc.1 — toglie valore all'idea che la lettura del codice basti.

`4.0.0` sarà corretto dopo che il framework avrà governato **una feature vera, decisa da te, su un repository che ti interessa**. È l'unica prova che resta.

---

## 8. Cosa farei ora — lista esaustiva

Ordinata per rapporto fra ciò che protegge e ciò che costa.

### Priorità 1 — chiude un rischio noto

| # | Attività | Perché adesso | Costo |
|:-:|---|---|---|
| 1 | **Usare il framework su una feature vera di un tuo progetto** | È l'unica cosa che separa `rc.2` da `4.0.0`, e la simulazione ha appena dimostrato che l'uso reale trova ciò che la lettura non trova. Anche una feature piccola | 1 sessione |
| 2 | **Fissare il tag di Spec Kit nella matrice di compatibilità** (`INSTALL.md` §1) | Oggi dice «da fissare al momento del bootstrap». Finché è vuota, `analyze`/`converge`/`tasks` possono cambiare semantica sotto i piedi in silenzio — è il rischio che il pin doveva chiudere | 15 min |
| 3 | **Verificare il formato reale prodotto da `/speckit.tasks`** | Il preset lo prescrive, ma nessuno ha visto l'output vero. C-20 nasce esattamente lì: il formato generato differiva da quello atteso e il fallimento era silenzioso | 30 min |
| 4 | **Emettere un rilievo per le righe che sembrano task ma non lo sono** | C-20 è corretto per l'enfasi, ma qualunque *altra* forma imprevista sparirà ancora in silenzio. L'engine ha già un vocabolario per «ho visto e non ho potuto usare»: ai task manca | 1-2 h |

### Priorità 2 — riduce l'attrito che fa abbandonare il processo

| # | Attività | Perché | Costo |
|:-:|---|---|---|
| 5 | **`burnup doctor`** — un comando che diagnostica la configurazione | In simulazione ho perso più tempo su `test_id_mapping` e sidecar che su tutto il resto. Un comando che dica «5 test nel report, 0 mappati, ecco le righe da incollare» eliminerebbe l'ostacolo che più probabilmente fa abbandonare | 3-4 h |
| 6 | **Generare `test_id_mapping` invece di scriverlo a mano** | Mappare nome-nel-report → Test ID a mano è l'unico punto in cui si edita YAML riga per riga. `burnup test link <TEST-ID> --from-report <nome>` lo renderebbe un comando come gli altri | 2-3 h |
| 7 | **Un `.gitignore` di riferimento nell'installazione** | `__pycache__` non ignorato invalida **tutta** l'evidenza sotto `current-revision`. Ci sono cascato io. `INSTALL.md` §2 non lo menziona | 20 min |
| 8 | **Dire nel rilievo che la policy `current-revision` è la causa** | Quando l'albero è sporco, il messaggio dice cosa è sporco (ora) ma non che è *quella policy* a renderlo fatale. Con `manual-confirmation` lo stesso stato non bloccherebbe | 1 h |
| 9 | **Avvisare quando nessun requisito ha una user story** | Comportamento corretto e voluto (niente ereditarietà), ma nel layout tipico *nessun* requisito la riceve e nulla lo segnala. Un rilievo `low` una tantum eviterebbe di scoprirlo a valle | 1 h |

### Priorità 3 — protegge da rischi non ancora manifestati

| # | Attività | Perché | Costo |
|:-:|---|---|---|
| 10 | **Attivare l'hook di allowlist in una sessione reale** | È l'unico enforcement tecnico del sistema e non è mai stato eseguito. Va anche verificato che non blocchi comandi legittimi: un hook che intralcia viene disattivato, e allora non protegge nulla | 1 h |
| 11 | **Un test end-to-end che *sia* questa simulazione** | Tutto ciò che ho fatto oggi è ripetibile. Trasformarlo in un test di sistema (progetto sintetico, flusso completo, asserzioni sui conteggi) impedisce che i cinque scenari verificati regrediscano | 3-4 h |
| 12 | **Misurare il costo per agent-hop** | Sei agenti su una feature significa sei ricostruzioni di contesto. Nessuno sa quanto costi, e la risposta decide se il framework conviene su feature piccole | dopo il #1 |
| 13 | **Decidere cosa fare dei 7 miglioramenti in stand-by** | `CLASSIFICA-MIGLIORAMENTI.md` li ordina già. Il primo — corner-case sweep in `clarify` — non richiede né agenti né codice. Gli altri richiedono parametri che **solo l'uso reale può calibrare** | dopo il #1 |
| 14 | **Rivedere l'exit code della retrocessione di classe** | Oggi esce `1` (`CONFIG_ERROR`, «correggi il file») ma non c'è nessun file da correggere: è una decisione rifiutata per policy. Semanticamente è più vicino a `2` | 30 min |

### Cosa **non** farei

- **Non aggiungerei un settimo agente.** Nessuno degli otto difetti sarebbe stato trovato da un agente in più; sette lo sarebbero stati da un controllo automatico.
- **Non aggiungerei funzioni al burn-up** prima del punto 1. Forecast, prioritizzazione e memoria di progetto hanno tutti parametri arbitrari che solo dati reali possono fissare.
- **Non toccherei l'architettura.** Canonical store, fingerprint e state machine hanno retto ogni prova: gli otto difetti sono tutti in superficie — un confronto di stringhe, una regex, un `except` mancante, tre messaggi.

---

## 9. La lezione, in una riga

Diciotto difetti sono usciti leggendo con attenzione. **Otto — fra cui il più grave di tutti — sono usciti al primo tentativo di usare davvero il sistema.** Le due attività non si sostituiscono, e la seconda non è rinviabile oltre.
