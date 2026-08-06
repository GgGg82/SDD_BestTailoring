# BURNUP-CALCULATION — Conteggi e snapshot

**Versione:** 2.0 · **Stato:** normativo · **Implementato in:** `burnup/engine.py`

## Unità di misura

L'unità è il **requisito attivo**, non il task e non la feature. `scope` è l'insieme dei requisiti con `scope_state == "active"`.

Cosa conta come requisito è definito da `requirements.accepted_id_patterns` e `requirements.sections`. Di default: FR e NFR sotto le sezioni dei requisiti.

> **Limite dichiarato (P1-15 dell'audit).** Success Criteria, scenari di accettazione e vincoli non identificati come NFR **non** sono conteggiati. La metrica è quindi un "FR/NFR burn-up", non un "burn-up di ogni cosa scritta nella spec". Per includerli, assegna loro un ID che combaci con `accepted_id_patterns` e collocali in una sezione configurata. È una scelta consapevole, non una svista: allargare l'unità di misura senza ID espliciti riporterebbe il conteggio nel campo dell'interpretazione.

## Formule

```
scope        = |{ r : r.scope_state = active }|
defined      = |{ r ∈ scope : r.lifecycle ∈ {defined, implemented, tested} }|
implemented  = |{ r ∈ scope : r.lifecycle ∈ {implemented, tested} }|
tested       = |{ r ∈ scope : r.lifecycle = tested }|
removed_total= |{ r : r.scope_state = removed }|
done_percent = 100 × tested / scope        (N/A se scope = 0)
```

I conteggi sono **cumulativi verso il basso**: un requisito `tested` conta anche in `implemented` e in `defined`. È ciò che rende il grafico un burn-up leggibile: le curve non si incrociano mai.

## Invariante

```
tested ≤ implemented ≤ defined ≤ scope
```

Verificata ad ogni calcolo. Una violazione solleva `InvariantError` (exit code 3): è sempre un bug dell'engine, mai un problema di dati.

## Fingerprint dello scope

```
scope_fingerprint = SHA-256(⋮ sorted(chiavi dei requisiti attivi))
```

Serve a rilevare i cambiamenti di **composizione** a parità di numero.

> v3: rimuovere un requisito e aggiungerne un altro nello stesso refresh lasciava `scope` invariato, e la decisione sullo snapshot era `no-change`. Una modifica di scope sostanziale non lasciava alcuna traccia storica.

## Quando si registra uno snapshot

In ordine di valutazione:

1. `forced` — `refresh --force-snapshot`
2. `initial` — non esiste storia
3. `scope-composition-change` — il fingerprint dello scope è cambiato
4. `status-change` — uno fra `scope`, `defined`, `implemented`, `tested`, `removed_total` è cambiato
5. `no-change` — nessuno snapshot

Il criterio 3 prima del 4 è deliberato: una sostituzione a parità di conteggi è comunque un evento di scope, e va registrata con la sua ragione.

Non si registra uno snapshot ad ogni refresh **per principio**: gonfiare la storia con punti identici rende il grafico illeggibile e la storia inutile. Uno snapshot di controllo a conteggi invariati resta sempre possibile con `--force-snapshot`.

## Contenuto di uno snapshot

```json
{
  "snapshot_id": "SNP-0003",
  "timestamp": "2026-07-31T09:00:00Z",
  "source_revision": "abc1234",
  "worktree_dirty": false,
  "reason": "scope-composition-change",
  "scope": 12, "defined": 12, "implemented": 8, "tested": 5,
  "removed_total": 1,
  "scope_fingerprint": "…"
}
```

`worktree_dirty` è registrato perché una misurazione presa con modifiche non committate non descrive esattamente il codice misurato, e chi legge il grafico mesi dopo deve poterlo sapere.

## Grafico

`reports/governance-dashboard.md` contiene un blocco Mermaid `xychart-beta` con le ultime 20 rilevazioni e quattro serie: Scope, Defined, Implemented, Tested. La finestra è limitata perché un grafico con centinaia di punti non si legge; la storia completa resta in `state/snapshots.jsonl`.
