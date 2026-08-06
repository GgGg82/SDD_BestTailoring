# TEST-REGISTER-SPEC — Definizioni ed esecuzioni

**Versione:** 2.0 · **Stato:** normativo · **Implementato in:** `burnup/ingest.py`, `burnup/models.py`

## Due entità distinte

| | Definizione | Esecuzione |
|---|---|---|
| Cos'è | cosa si verifica e con quale criterio | cosa è successo lanciandolo |
| Dove | `state/test-definitions.json` | `state/test-runs.jsonl` |
| Chi scrive | umano, via `burnup test define` | l'engine, importando i report |
| Mutabile | sì, con `--replace` | **no**, append-only |

Tenerle separate è ciò che rende possibile l'append-only reale: le definizioni evolvono, la storia delle esecuzioni no.

## Definizione

```bash
burnup test define TEST-001 \
    --requirement 001-feat/FR-001 \
    --definition "l'utente autenticato riceve un token valido per 24h" \
    --mandatory \
    --kind integration \
    --command "pytest tests/test_auth.py::test_token_ttl" \
    --owner "qa@team" \
    --actor "qa@team" --reason "copertura obbligatoria di FR-001"
```

| Campo | Vincolo |
|---|---|
| `test_id` | univoco. Un duplicato è **errore**, non sovrascrittura silenziosa (P1-12) |
| `requirement_keys` | chiavi composite `feature/requisito`; devono esistere, salvo `--allow-unknown` |
| `kind` | enum: `unit`, `integration`, `e2e`, `manual`, `performance`, `security` |
| `mandatory` | booleano. Solo i test obbligatori determinano `tested` |
| `definition` | obbligatorio: cosa si verifica e qual è l'esito atteso |

> v3: il catalogo era costruito con una dict comprehension, quindi due definizioni con lo stesso ID si sovrascrivevano in silenzio e vinceva l'ultima letta. E non esisteva alcun comando: l'unico modo di definire un test era editare a mano la tabella Markdown generata, cioè proprio l'operazione che la documentazione vietava.

## Adapter di importazione

### JUnit XML

Nome per il matching: `classname.name` se `classname` esiste, altrimenti `name`.

Esito: `error` → `error`, `failure` → `fail`, `skipped` → `blocked`, altrimenti `pass`.

Ora di esecuzione, in ordine: `testcase@timestamp` → `testsuite@timestamp` → sidecar. **Il mtime del file non è un fallback accettabile**: basta un `touch` o un checkout per ringiovanire un report vecchio, e la v3 lo usava.

Se nessuna fonte fornisce un'ora, il risultato viene scartato con un rilievo: senza timestamp non è possibile stabilire quale sia il risultato più recente, e inventarne uno sarebbe peggio.

### JSON generico

```json
[
  {"id": "TEST-001", "result": "pass", "timestamp": "2026-07-31T09:00:00Z",
   "duration": "1.2s", "source_revision": "abc1234"}
]
```

### Sidecar

```json
// test-results/junit.xml.meta.json
{"source_revision": "abc1234", "executed_at": "2026-07-31T09:00:00Z"}
```

È il canale con cui una revisione **reale** entra nel sistema. Senza sidecar e senza campo nel report, la revisione resta `unknown` e la policy `current-revision` non può essere soddisfatta.

> v3: al report veniva assegnato l'HEAD **del momento del refresh**. Un test eseguito settimane prima risultava girato sulla revisione corrente, il che rendeva `current-revision` una tautologia sempre vera.

## Risoluzione del Test ID

In ordine:

1. `traceability.test_id_mapping` — mappatura esplicita, sempre prioritaria;
2. corrispondenza esatta;
3. corrispondenza su **token delimitati**: l'ID deve essere circondato da caratteri non alfanumerici.

`_`, `.`, `-`, `::` sono separatori validi, quindi `suite.TEST-10_login` risolve a `TEST-10`. Ma `TEST-1` non risolve dentro `TEST-10`, perché `0` è alfanumerico e il confine è violato.

**Se più Test ID combaciano, si rifiuta.** Un'attribuzione ambigua è peggio di nessuna attribuzione: produce un numero credibile e sbagliato.

> v3: il matching era `if test_id in nome_nel_report`, quindi `TEST-1` catturava il risultato di `suite.TEST-10_login`.

## Idempotenza

```
run_identity = SHA-256(report_hash ⋮ adapter ⋮ test_id ⋮ executed_at ⋮ result)
```

Una run la cui identità esiste già viene ignorata e contata fra gli `skipped_duplicates`.

`report_hash` è calcolato sui **byte** del file, non sul percorso: rinominare o spostare un report non lo fa reimportare, mentre sovrascriverlo con contenuto diverso lo fa correttamente entrare come esecuzione nuova.

> v3: nessuna chiave di ingestione. Tre refresh dello stesso report producevano tre righe identiche nella Execution History.

## Esito corrente

```
latest = argmax over runs of (executed_at, run_id)
```

Per **ora di esecuzione**, con l'ULID come tie-breaker deterministico. Mescolare l'ordine dei file in ingresso non cambia il risultato.

> v3: vinceva l'ultimo record processato nell'ordine di iterazione dei file. Un report vecchio elaborato dopo uno nuovo sovrascriveva un pass recente con un fail storico.

## Conferma manuale

```bash
burnup test confirm-manual TEST-001 --result pass \
    --evidence "verbale-collaudo-2026-07-31.pdf" \
    --actor "qa@team" --reason "collaudo manuale superato"
```

Produce una run con `revision_origin: "manual"` e un `Decision` permanente. `--actor`, `--reason` ed `--evidence` sono obbligatori: una conferma senza autore, motivo ed evidenza non è una conferma, è un'asserzione.
