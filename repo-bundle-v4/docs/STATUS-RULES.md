# STATUS-RULES — Ciclo di vita dei requisiti

**Versione:** 2.0 · **Stato:** normativo · **Implementato in:** `burnup/status.py`, `burnup/engine.py`

Questo documento è la fonte di verità sugli stati. Se il codice diverge da qui, è il codice ad avere un bug.

## Principio che governa tutto

> **L'evidenza vale solo se si riferisce al fingerprint corrente del requisito.**

Nella v3 l'evidenza era legata alla *chiave* (`001-demo/FR-001`), che non cambia mai quando si riscrive il testo. Conseguenza riprodotta in audit: un requisito trasformato da "autenticare l'utente" a "cancellare tutti i dati al logout", con `tasks.md` cancellato e marcatore rimosso dal codice, restava `tested` **con zero rilievi**.

## Fingerprint del requisito

```
requirement_fingerprint = SHA-256(
    normalize(requirement_id) ⋮ normalize(text) ⋮
    normalize(acceptance_criteria) ⋮ sorted(nfr_refs)
)
```

`normalize()` assorbe forma Unicode (NFC), spaziatura, enfasi Markdown (`*_\``), punteggiatura finale.

**Non abbassa il case**, deliberatamente: in un requisito la differenza fra "DEVE" e "dovrebbe" è semanticamente rilevante, e in RFC 2119 il maiuscolo è esattamente il portatore della normatività.

Conseguenza pratica: **riformattare una spec non invalida l'evidenza; riscriverne il significato sì.**

### Le tre evidenze non decadono allo stesso modo

| Evidenza | Origine | Come decade |
|---|---|---|
| `implemented-by` | `tasks.md` | ri-derivata dal file ad ogni refresh |
| `evidenced-by` | commenti nel codice | ri-derivata dai sorgenti ad ogni refresh |
| `verified-by` | `burnup test define` | **vincolata al fingerprint dichiarato** |

Le prime due sono ri-derivate da file che nominano il requisito con il suo ID,
mai con il suo testo: se il file cita ancora `FR-001`, la relazione si ricrea. È
difendibile — modificare `tasks.md` o il codice è già un atto umano.

La terza no. *"TEST-001 verifica FR-001"* è una decisione registrata, e riguarda
il requisito **com'era scritto in quel momento**. `TestDefinition` conserva
quindi il `requirement_fingerprint` di allora, e la relazione si ricrea solo se
combacia con quello corrente. Altrimenti decade e viene emesso
`test-definition-stale` (`medium`).

Per riportare il requisito a `tested` bisogna riaffermare la definizione con
`burnup test define --replace` e registrare una nuova esecuzione. È l'attrito
voluto: se il requisito è cambiato, ciò che era stato verificato non è più ciò
che c'è scritto.

> Chiude C-02, trovato nel collaudo del 2026-08-06. La relazione `verified-by`
> veniva ricostruita ad ogni refresh e **ristampata con il fingerprint
> corrente**, quindi non poteva mai risultare stantia. Riscrivendo un requisito
> da *"il sistema deve autenticare l'utente"* a *"il sistema deve cancellare
> tutti i dati al logout"*, e lasciando intatti `tasks.md` e il marcatore nel
> codice, il requisito **restava `tested`** — la forma residua del probe che ha
> motivato l'intera riscrittura v4. Il probe originale sembrava superato solo
> perché cancellava anche task e marcatore: la regressione veniva da quelli.

### Confronto fra revisioni

La revisione dichiarata dal sidecar e quella corrente possono avere forme
diverse: `git rev-parse HEAD` produce quaranta caratteri, `--short` sette. Il
confronto è **per prefisso**, con un minimo di sette caratteri — la stessa
regola con cui Git tratta le abbreviazioni. Un confronto per uguaglianza
esatta rendeva `current-revision` insoddisfabile con il sidecar più naturale, e
il rilievo mostrava lo stesso commit due volte dichiarandolo diverso.

> Chiude C-21, trovato in simulazione su progetto reale il 2026-08-09.

### Lavoro non salvato in Git

Ogni refresh su un albero con modifiche non committate a **specifiche, task o
codice** emette `uncommitted-changes` (`high`). Il Gate Decision Record congela
il fingerprint del codice approvato: con modifiche non salvate quel fingerprint
non descrive alcuna versione registrata, e il verbale dichiarerebbe congelato
uno stato che non lo è.

Il rilievo **nomina i file** che risultano modificati: senza, indica che
qualcosa non è committato e lascia indovinare cosa. In simulazione questo ha
portato a diagnosticare come bug dell'engine un `.pyc` tracciato per errore.

**Non contano i file scritti dall'engine stesso.** Seguendo la procedura di
`CLAUDE.md` — `refresh --strict` e poi approvazione del Gate 4 — sarebbe il
refresh ad aver appena riscritto `state/` e `reports/`, e la procedura
diventerebbe ineseguibile. L'esclusione è coerente con
`TRACEABILITY-RULES.md`, che esclude sempre la directory di output dalla
scansione dei sorgenti.

## Gli stati

### `defined`

Stato base di ogni requisito attivo. Condizioni:

- requisito presente in una delle sezioni configurate di `spec.md`;
- ID valido secondo `requirements.accepted_id_patterns`;
- testo normativo non vuoto;
- `scope_state == "active"`.

### `implemented`

- **tutti** i task collegati risultano completi (`- [x]`), **oppure** `require_tasks_for_implemented: false` e non esistono task collegati;
- esiste evidenza di codice corrente;
- **entrambe le evidenze si riferiscono al fingerprint corrente.**

> Il default `require_tasks_for_implemented: true` corregge P1-30. Nella v3 `tasks_ok` era vero quando non esisteva alcun task, quindi il solo marcatore nel codice bastava a dichiarare implementato un requisito che nessuno aveva pianificato.

### `tested`

- il requisito è `implemented`;
- almeno un test collegato è `mandatory`;
- **tutti** i test obbligatori hanno un'ultima esecuzione con esito `pass`;
- ogni esecuzione ha evidenza verificabile (`evidence_hash` non vuoto);
- ogni esecuzione è **fresca** secondo la policy configurata.

### Requisito attivo non verificato

Ogni requisito `active` che **non** raggiunge `tested` produce un finding
`requirement-not-verified` di severita' `high`.

E' il segnale **uniforme** su cui il Gate 4 si misura: gli altri finding —
`incomplete-tasks`, `missing-mandatory-test`, `failing-mandatory-test`,
`stale-evidence` — restano come spiegazione del *perche'*, ma il gate deve poter
dipendere da una sola condizione, indipendente dalla causa.

> Chiude C-01, trovato nel collaudo end-to-end del 2026-08-06. Tutti gli altri
> finding vivevano dentro un ramo: `incomplete-tasks` richiede evidenza di
> codice, `tasks-complete-without-code-evidence` richiede i task completi, e
> l'intero blocco `tested` — quindi anche `missing-mandatory-test` — era
> annidato dentro `implemented`. Restava scoperto il caso piu' elementare: il
> requisito su cui nessuno ha lavorato cadeva fuori da ogni ramo **in
> silenzio**. Verificato: una feature con meta' dei requisiti mai implementati
> superava tutti e quattro i gate con zero finding aperti, e il Gate Decision
> Record registrava `{'scope': 2, 'tested': 1}` approvando comunque.
>
> Non era una questione di soglia: senza alcun finding emesso, nessun valore di
> `strict_blocks_on` poteva intercettarlo.

La severita' e' `high` e non configurabile perche' deve bloccare in **tutte** le
classi di change, non solo in High-Risk.

**Rinviare un requisito resta possibile**, ma non in silenzio. Le due vie sono
quelle che il framework aveva gia':

| Via | Comando | Significato |
|---|---|---|
| Rinvio | `burnup finding waive` | il requisito resta nel perimetro, la sua mancata verifica e' accettata con attore, motivo ed eventuale scadenza |
| Uscita dal perimetro | `burnup requirement remove` | il requisito non fa piu' parte di questa release |

Un'approvazione ottenuta per waiver lo cita nel Gate Decision Record.

### `removed`

Solo per decisione esplicita registrata con `burnup requirement remove`, che richiede attore e motivo. Un requisito che scompare da `spec.md` **non** viene rimosso automaticamente: genera un finding `source-missing` di severità `high`. Sparire da un file non è una decisione.

## Regressioni

Lo stato è una **funzione pura dell'evidenza corrente**, ricalcolata da zero ad ogni refresh. Non è una macchina a stati che si muove solo in avanti. Quindi le regressioni sono automatiche e non richiedono logica dedicata:

Qualunque uscita da `tested` produce **anche** `requirement-not-verified`, che
resta aperto finche' il requisito non e' di nuovo verificato. E' la differenza
con `requirement-changed`, che si chiude al refresh successivo appena il
fingerprint e' riallineato: quello segnala un *evento*, questo uno *stato*.

| Evento | Effetto |
|---|---|
| testo del requisito riscritto | → `defined`, finding `requirement-changed` |
| marcatore `REQ:` rimosso dal codice | → `defined` |
| task riaperto (`- [ ]`) | → `defined`, finding `incomplete-tasks` |
| test obbligatorio passa a `fail` | → `implemented`, finding `failing-mandatory-test` |
| definizione del test rimossa | → `implemented`, finding `missing-mandatory-test` |
| evidenza diventa stantia | → `implemented`, finding `stale-evidence` |

## Freschezza

| Policy | Un `pass` conta quando |
|---|---|
| `current-revision` | la revisione dichiarata dal report o dal sidecar coincide con `HEAD`, l'origine è verificabile, **e il working tree è pulito** |
| `manual-confirmation` | esiste una conferma registrata con attore, motivo ed evidenza, oppure il report dichiara una revisione |
| `latest-known` | sempre — nessun controllo |

> `manual-confirmation` nella v3 ritornava incondizionatamente vero: si chiamava "conferma manuale" senza contenere alcuna conferma, alcun attore, alcuna data. Era `latest-known` con un nome che prometteva un controllo umano inesistente.

Il working tree sporco invalida `current-revision` perché la revisione non descrive il codice realmente misurato.

## Ciclo di vita dei finding

Anche lo stato di un finding è una funzione dell'evidenza corrente, non una
casella che qualcuno spunta.

| Stato precedente | Se la condizione è ancora vera al refresh |
|---|---|
| `open` | resta `open` |
| `resolved` / `verified` | **torna `open`** |
| `waived` / `accepted` | resta tale, finché il waiver non scade |

`burnup finding close` chiude un rilievo, ma non lo mette a tacere: se la
condizione persiste, il refresh successivo lo riapre. Solo un waiver — che ha
attore, motivo e scadenza — sopravvive, e alla scadenza si riapre da solo.

> Chiude C-04. La `FindingFactory` ereditava `status=prior.status`, quindi un
> finding chiuso veniva ri-emesso già chiuso e non tornava mai visibile: `close`
> era un waiver permanente travestito. La CLI annunciava già il comportamento
> corretto — *"Se la condizione che lo ha generato persiste, il prossimo refresh
> lo riaprirà"* — senza implementarlo.

## Invariante

```
tested ≤ implemented ≤ defined ≤ scope
```

Verificata ad ogni calcolo. Una violazione è **sempre** un bug dell'engine, mai un problema di dati: solleva `InvariantError` con exit code 3.

Non è un `assert`. La v3 usava `assert`, che sparisce sotto `python -O` proprio quando l'integrità conta di più, e produceva un traceback non intercettato indistinguibile da un errore di configurazione. La CI verifica che il controllo resti attivo sotto `-O`.
