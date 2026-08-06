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

### `removed`

Solo per decisione esplicita registrata con `burnup requirement remove`, che richiede attore e motivo. Un requisito che scompare da `spec.md` **non** viene rimosso automaticamente: genera un finding `source-missing` di severità `high`. Sparire da un file non è una decisione.

## Regressioni

Lo stato è una **funzione pura dell'evidenza corrente**, ricalcolata da zero ad ogni refresh. Non è una macchina a stati che si muove solo in avanti. Quindi le regressioni sono automatiche e non richiedono logica dedicata:

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

## Invariante

```
tested ≤ implemented ≤ defined ≤ scope
```

Verificata ad ogni calcolo. Una violazione è **sempre** un bug dell'engine, mai un problema di dati: solleva `InvariantError` con exit code 3.

Non è un `assert`. La v3 usava `assert`, che sparisce sotto `python -O` proprio quando l'integrità conta di più, e produceva un traceback non intercettato indistinguibile da un errore di configurazione. La CI verifica che il controllo resti attivo sotto `-O`.
