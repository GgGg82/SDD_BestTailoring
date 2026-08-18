# Report di collaudo — SDD Multi-Agent Framework

**Versione consegnata:** `4.0.0-rc.1` · **Versione di partenza:** `4.0.0-beta.1`
**Periodo:** 2026-08-06 / 2026-08-07 · **Tre giri di collaudo**
**Perimetro:** l'intero bundle — engine, hook, documenti normativi, preset Spec Kit, file agente, CI, template, installazione

---

## 1. Sintesi

| | Prima | Dopo |
|---|---|---|
| Difetti noti | 0 dichiarati | **18 trovati, 18 corretti** |
| Test | 98 | **309** |
| Copertura | 90.34% | **100%** (soglia bloccante in `pyproject.toml`) |
| Difetti aperti | — | **nessuno** |
| Procedure documentate eseguibili | 2 su 4 | **4 su 4** |

Nessuno dei diciotto era visibile alla suite iniziale, pur con il 90% di copertura. Il motivo è uno solo: i test esercitavano le **funzioni**, mentre i difetti stavano nella **procedura** e nel **contratto dichiarato**.

---

## 2. I diciotto difetti

Legenda gravità: **P0** impedisce al sistema di fare ciò per cui esiste · **P1** rompe una procedura documentata · **P2** disallineamento fra ciò che il sistema dichiara e ciò che fa · **P3** igiene.

### Giro 1 — comportamento

| ID | Gravità | Difetto | Causa | Correzione | Test di regressione |
|---|:---:|---|---|---|---|
| **C-01** | P0 | Il Gate 4 approvava una feature con metà dei requisiti mai implementati, con **zero finding** e `--strict` a exit 0 | In `status.py` l'intero blocco che valuta `tested` era annidato dentro `if state == "implemented"`. Il requisito su cui nessuno ha lavorato cadeva fuori da ogni ramo in silenzio | Nuovo finding `requirement-not-verified` (`high`, non configurabile) emesso per ogni requisito attivo non `tested` | `test_requirement_verification.py` (8) |
| **C-02** | P0 | Riscrivere il significato di un requisito **non** faceva decadere l'evidenza di test: restava `tested` | La relazione `verified-by` veniva ricostruita a ogni refresh e ristampata col fingerprint **corrente**, quindi non poteva mai risultare stantia | `TestDefinition` registra il `requirement_fingerprint` al momento di `test define`; la relazione si ricrea solo se combacia, altrimenti `test-definition-stale` | `test_evidence_decay.py` (6) |
| **C-03** | P1 | `burnup refresh` **cancellava tutti i Gate Decision Record** | `engine.py` costruiva lo `StoreData` omettendo `gate_decisions`, mentre riportava `decisions`: `commit` riscriveva il file vuoto | Una riga: `gate_decisions=data.gate_decisions` | `test_gates.py` (2 nuovi) |
| **C-04** | P2 | Un finding chiuso non si riapriva mai, anche a condizione persistente | `FindingFactory` ereditava `status=prior.status` | Solo `waived` e `accepted` sopravvivono alla ri-emissione | `test_integration.py` (2 nuovi) |
| — | P1 | Il Gate 4 congelava una baseline con lavoro non salvato in Git | `worktree_dirty` era calcolato e scritto nel verbale, mai consultato | Nuovo finding `uncommitted-changes` (`high`), che **esclude** i file scritti dall'engine | `test_uncommitted_changes.py` (4) |

> **C-03 era il più insidioso.** `CLAUDE.md` impone `refresh --strict` *prima* di ogni Gate 4: la procedura documentata azzerava i Gate 1-3 e rendeva il Gate 4 inapprovabile. La state machine era inutilizzabile esattamente nel percorso per cui era stata scritta. Si vedeva solo eseguendo i comandi nell'ordine prescritto.

### Giro 2 — contratto della CLI e della configurazione

| ID | Gravità | Difetto | Causa | Correzione | Test |
|---|:---:|---|---|---|---|
| **C-05** | P2 | I messaggi d'errore rimandavano a `burnup migrate` e `burnup migrate-config`, **inesistenti** | Suggerimenti scritti per comandi mai implementati. Latente finché lo schema non cambiava — e il passaggio a `3.0` l'ha reso raggiungibile | Suggerimenti sostituiti con azioni eseguibili; un test scandisce le stringhe destinate all'utente | `test_contract_audit.py` |
| **C-06** | P2 | `requirements.default_scope_state` documentato e **ignorato** | Letto, validato, salvato in configurazione e mai applicato: `scope_state` era fissato a `"active"` nel modello | Applicato ai requisiti nuovi; una decisione registrata con `requirement remove` non è ribaltabile da un default | `test_contract_audit.py` |
| **C-07** | P1 | **Nessun report JUnit di pytest era importabile** senza sidecar | `parse_junit` leggeva l'ora da `root.get("timestamp")`. Con `<testsuites>` come radice — la forma di pytest — il timestamp sta sul figlio e veniva ignorato | Ora e revisione cercate anche sul `<testsuite>` che contiene il caso, come già prescriveva `TEST-REGISTER-SPEC.md` | `test_contract_audit.py` (3 parametrizzati) |
| **C-08** | P2 | Gli errori d'uso uscivano con **exit code 2**, riservato dal contratto a "quality gate fallito" | `ExitCode.USAGE_ERROR = 4` definito e mai usato | Parser che rispetta il contratto | `test_contract_audit.py` (3 parametrizzati) |
| **C-09** | P2 | `--definition`, dichiarato obbligatorio, accettava la stringa vuota | Nessuna validazione | Validazione con messaggio esplicito | `test_contract_audit.py` |

> **C-06 è il più significativo dei cinque.** Il template dichiara: *"Nella v3 cinque campi erano documentati e ignorati […] Se un campo compare in questo template, ha effetto."* La v4 ne aveva chiusi quattro su cinque, lasciando proprio quello nominato al secondo posto nell'elenco.

### Giro 3 — perimetri fuori dall'engine

| ID | Gravità | Difetto | Causa | Correzione | Test |
|---|:---:|---|---|---|---|
| **C-10** | P1 | **La classe di change non esisteva per l'engine**: Fast Track era ineseguibile | Due documenti normativi prescrivevano "Gate 1 e 4", ma la state machine esigeva ogni gate precedente valido. Cercando `fast-track` nel codice non compariva nulla | Nuovo comando `burnup feature class`, che registra una decisione permanente; `check_entry_criteria` usa la sequenza della classe | `test_change_class.py` (9) |
| **C-11** | P1 | Il hook validava **solo il primo segmento** di una catena: `ls && npm install <qualunque cosa>` passava | `command.split("&&")[0].split("|")[0]` | Ogni segmento validato | `test_bundle_contract.py` (5+4 parametrizzati) |
| **C-12** | P1 | Senza il nome dell'agente nel payload, il hook bloccava **anche i Maker**, che hanno Bash per lavorare | `if agent and agent not in CHECKER_AGENTS` — con `agent` vuoto la guardia non scattava | L'allowlist vincola solo i Checker dichiarati | `test_bundle_contract.py` |
| **C-13** | P2 | La tabella degli agenti in `CLAUDE.md` ometteva lo step **0.1** | Disallineamento con la prosa dello stesso file, il file agente e il progress-template | Tabella corretta; un test verifica che le due fonti coincidano | `test_bundle_contract.py` |
| **C-14** | P2 | Il runbook documentava **12 tipi di finding su 23** | Tabella mai aggiornata | Tabella completa; un test la verifica nei due sensi | `test_bundle_contract.py` (2) |
| **C-15** | P2 | L'exit code `4` non era documentato | Tabella incompleta | Documentato, con la ragione della distinzione dal `2` | `test_bundle_contract.py` |
| **C-16** | P3 | La CI dichiarava "23 probe + 7 aggiunti"; i test reali erano 30 e 14 | Conteggio scritto a mano nel nome del job | Conteggio rimosso; un test impedisce di reintrodurne | `test_bundle_contract.py` |
| **C-17** | P3 | `.coverage`, `.coverage.*` e `.pytest_cache/` spediti nella cartella distribuita | Confezionamento della cartella, non del repository | Rimossi | — |

### Coda — introdotto correggendo

| ID | Gravità | Difetto | Causa | Correzione | Test |
|---|:---:|---|---|---|---|
| **C-18** | P1 | **I sei prompt agente non conoscevano l'engine che invocano**: né il comando `feature class`, né i tre finding nuovi, né l'exit code `4` | Ho cambiato l'engine e non ho aggiornato i prompt. Il test di coerenza esistente confrontava solo gli **step**: il buco stava fuori dal perimetro che avevo definito | Sei prompt aggiornati; tre controlli nuovi che chiudono il perimetro. **Hanno trovato subito altre due lacune** nella tabella appena scritta | `test_bundle_contract.py` (3) |

> **C-18 l'ho creato io.** È la stessa classe di scostamento che il collaudo ha passato tre giri a trovare — il codice avanza, la documentazione resta indietro — commessa mentre si correggeva. Vale la pena registrarlo: nessun processo è immune, e la difesa non è l'attenzione ma un controllo automatico che fallisca da solo.
>
> Conseguenze concrete: il **Technical Auditor** riporta i finding bloccanti e non sapeva che i tre nuovi esistessero; il **Business Analyst/QA**, unico R sulle definizioni di test, non sapeva che riscrivere un requisito le fa decadere; il **Software Engineer** non sapeva che il lavoro non committato blocca il Gate 4; il **Tech Lead** non sapeva che un requisito senza task produce un finding bloccante; il **Solutions Architect** non sapeva che in Fast Track `plan.md` non serve; il **Product Manager** non sapeva che riscrivere un requisito già implementato comporta rilavorazione.

---

## 3. Dove stavano i difetti

| Categoria | Difetti | Quota |
|---|---|:---:|
| **Contratto dichiarato** — scostamenti fra ciò che il sistema promette per iscritto e ciò che fa | C-04, C-05, C-06, C-07, C-08, C-09, C-13, C-14, C-15, C-16, C-18 | 11/18 |
| **Procedura** — visibili solo eseguendo i comandi nell'ordine prescritto dai documenti | C-01, C-02, C-03, C-10 | 4/18 |
| **Perimetri senza alcun test** — il hook di allowlist, unico enforcement tecnico del sistema | C-11, C-12 | 2/18 |
| **Igiene di rilascio** | C-17 | 1/18 |

Undici difetti su diciotto sono stati trovati prendendo sul serio la documentazione: leggere una promessa scritta e verificare se il codice la mantiene. L'ultimo — C-18 — è stato trovato da un controllo automatico scritto proprio per quello, il che è il punto: l'attenzione non scala, un test sì.

---

## 4. Test aggiunti

| File | Test | Perimetro |
|---|:---:|---|
| `test_edge_paths.py` | 55 | Percorsi d'errore: configurazione, confinamento, Markdown, importazione, freschezza, store |
| `test_edge_paths_extra.py` | 37 | Validazioni residue, stati intermedi del calcolo, guasti di I/O |
| `test_remaining_branches.py` | 28 | Ultimi rami: lock, relazioni decadute, marcatori in stringa |
| `test_bundle_contract.py` | 13 | Hook, coerenza documentale, CI, coerenza dei prompt agente |
| `test_change_class.py` | 9 | Le tre classi di change end-to-end |
| `test_contract_audit.py` | 9 | Ogni promessa del template e della CLI |
| `test_requirement_verification.py` | 8 | C-01 e le vie d'uscita legittime |
| `test_evidence_decay.py` | 6 | C-02, con il probe isolato correttamente |
| `test_uncommitted_changes.py` | 4 | Lavoro non salvato al Gate 4 |
| *(esistenti, estesi)* | +4 | `test_gates.py`, `test_integration.py` |

**Nove file nuovi, 169 test aggiunti.** Ogni correzione è stata fatta seguendo la regola A0 del remediation plan: **test rosso prima del fix**, senza eccezioni.

---

## 5. Copertura

`TOTAL 2004 0 100%` — soglia `fail_under = 100` in `pyproject.toml`: una regressione che scopre righe fa fallire la build.

Due righe sono escluse con `# pragma: no cover` e la ragione accanto:

| Riga | Ragione |
|---|---|
| `cli.py` · gestore di `KeyboardInterrupt` | richiede un processo e un segnale reali |
| `cli.py` · guard `if __name__ == "__main__"` | punto d'ingresso del processo |
| `paths.py` · segmenti neutri di percorso | irraggiungibile: `PurePosixPath` normalizza già `./` e `//`. La guardia resta perché il confinamento non deve dipendere da un dettaglio di pathlib |

Le esclusioni sono dichiarate nel sorgente, non nascoste in configurazione: chi legge il codice vede *cosa* è escluso e *perché*.

---

## 6. Perché `4.0.0-rc.1` e non `5.0.0`

**Il numero maggiore segnala rotture rispetto a una versione rilasciata.** La `4.0.0` non lo è mai stata: `4.0.0-beta.1` è una pre-release, e per definizione dichiara che la 4.0.0 non è ancora uscita. Il CHANGELOG stesso lo registra — *"la beta.1 non è mai stata eseguita su un progetto reale"*.

Le rotture introdotte qui sono reali ma **rispetto a una beta**, non a un contratto pubblicato:

| Rottura | Impatto |
|---|---|
| Schema del canonical store `2.0` → `3.0` | Uno store `2.0` viene rifiutato. Nessuno esiste |
| Exit code `4` per gli errori d'uso, prima `2` | Una pipeline che trattava `2` come "gate fallito" ora distingue |

Si risolvono avanzando l'identificatore di pre-release. Chiamarla `5.0.0` racconterebbe che una `4.x` stabile è esistita ed è stata rotta, e non è successo.

**`rc` invece di `beta.2`** perché lo stato è cambiato di natura: nessun difetto noto aperto, ogni procedura documentata verificata eseguibile, copertura al 100% con soglia bloccante. Manca una cosa sola per la `4.0.0` definitiva — **girare su un progetto reale**, che è esattamente ciò che un release candidate dichiara di non aver ancora fatto.

Lo **schema del canonical store** ha una numerazione propria e indipendente: è passato a `3.0`, e quello sì è un incremento maggiore a pieno titolo.

> `5.0.0` sarà corretto quando, dopo una `4.x` rilasciata e usata, si romperà di nuovo un contratto pubblico — per esempio aggiungendo un settimo agente, o cambiando la semantica degli stati dei requisiti.

---

## 7. Cosa questo collaudo non dice

Va dichiarato con precisione, per non far passare per verificato ciò che non lo è.

| Non verificato | Perché |
|---|---|
| Il flusso a sei agenti in esecuzione | Nessun agente è stato invocato: handoff, isolamento del contesto e costo per hop restano non misurati |
| La qualità dei Gate umani | Ho approvato io i gate: non è stata messa alla prova né l'autorità decisionale umana né la capacità dei Checker di trovare un difetto che nessuno sapeva ci fosse |
| I comandi Spec Kit reali | `spec.md`, `plan.md` e `tasks.md` scritti a mano nel formato atteso. Se Spec Kit producesse un formato diverso, il parser potrebbe comportarsi diversamente. **È la verifica più utile da fare subito dopo, e richiede la tua installazione** |
| Scala reale | Il progetto di prova ha 2-3 requisiti e una feature. Nulla è noto sul comportamento con decine di feature o spec malformate |

---

## 8. Cosa resta da fare

| Priorità | Attività | Nota |
|:---:|---|---|
| 1 | **Girare su un progetto reale** | È l'unica cosa che separa `rc.1` da `4.0.0`, e l'unica che può calibrare i parametri lasciati arbitrari nelle proposte in stand-by |
| 2 | Verificare il formato prodotto da Spec Kit reale | Richiede la tua installazione |
| 3 | Corner-case sweep in `clarify` | Prima voce fra i miglioramenti veri e propri: nessun agente nuovo, nessun artefatto, nessuna riga di Python |
| 4 | `AGENTS.md` + `PROJECT-STATE.md` generato | Protezione da un rischio già presente: più strumenti e più persone sullo stesso repository |
| — | Costo degli agent-hop | Non misurabile senza il punto 1 |

Il dettaglio dei miglioramenti resta in `Miglioramenti/CLASSIFICA-MIGLIORAMENTI.md`; il referto tecnico completo con le riproduzioni in `COLLAUDO-ENGINE-v4.md`.
