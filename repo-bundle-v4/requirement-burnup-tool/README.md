# Requirement Burn-up

Tracciabilità dei requisiti e misurazione del burn-up per progetti Spec Kit.

## Principio

> Il canonical store è la verità. Il Markdown è una proiezione.
> Nessuna decisione umana viene mai registrata modificando un report generato.

```
requirement-burnup/
├── state/      ← fonte di verità, machine-readable, va versionata
└── reports/    ← Markdown generato, rigenerabile, mai modificato a mano
```

Cancellare `reports/` non perde nulla: si rigenera con un refresh.

## Comandi

```bash
burnup init --project-root .            # crea lo store e fa la prima scansione
burnup refresh --project-root .         # aggiorna stato e report
burnup refresh --strict                 # exit code 2 se ci sono findings bloccanti
burnup status --project-root .          # sola lettura, riporta anche la freschezza
```

### Decisioni umane

Ogni decisione produce un record permanente con attore, motivo e revisione:

```bash
burnup test define TEST-001 --requirement 001-feat/FR-001 \
    --definition "l'utente autenticato riceve un token valido" \
    --mandatory --command "pytest tests/test_auth.py" \
    --actor "qa@team" --reason "copertura obbligatoria di FR-001"

burnup test confirm-manual TEST-001 --result pass \
    --evidence "verbale-collaudo-2026-07-31.pdf" \
    --actor "qa@team" --reason "collaudo manuale superato"

burnup link confirm 001-feat/FR-001 T014 --type implemented-by \
    --actor "lead@team" --reason "il task non cita l'ID ma lo implementa"

burnup requirement remove 001-feat/FR-009 \
    --actor "pm@team" --reason "fuori scope, deciso in review del 30/07"

burnup finding waive FND-A1B2C3D4E5F6 \
    --actor "cto@team" --reason "accettato per la release 1.0" \
    --expires "2026-12-31T00:00:00Z"

burnup finding close FND-A1B2C3D4E5F6 --verified \
    --actor "auditor@team" --reason "verificato indipendentemente"
```

`--actor` e `--reason` sono **obbligatori**: una decisione senza autore e motivo non è auditabile.

## Exit code

| Codice | Significato |
|---:|---|
| 0 | successo |
| 1 | errore di configurazione |
| 2 | quality gate fallito (solo con `--strict`) |
| 3 | errore di engine — è un bug, va segnalato |

Una pipeline può decidere dal solo exit code, senza fare parsing dello stderr. Con `--json` ogni comando emette anche un payload machine-readable.

## Come un requisito raggiunge `tested`

```
defined      requisito attivo, ID valido, testo normativo, fingerprint corrente
   ↓
implemented  task obbligatori completi + evidenza di codice corrente,
             entrambi riferiti al fingerprint CORRENTE del requisito
   ↓
tested       implemented + test obbligatori collegati + ultima esecuzione pass,
             fresca secondo la policy, con evidenza verificabile
```

**L'evidenza è legata al fingerprint del contenuto, non alla chiave.** Se il testo di un requisito cambia in modo sostanziale, tutta l'evidenza precedente decade automaticamente e lo stato retrocede a `defined`, con un finding esplicito. È la correzione del difetto più grave della v3, dove un requisito riscritto da capo restava `tested` con zero rilievi.

## Contratto di tracciabilità

**Nei task** (proprietà del Tech Lead):

```
- [ ] T014 [P] [US2] [REQ:FR-003,NFR-002] Implementa la validazione in src/…
- [ ] T003 [NON-REQ: script di build] Configura la pipeline
```

**Nel codice** (proprietà del Software Engineer) — solo dentro un commento:

```python
# REQ: 001-feat/FR-001
def authenticate(...): ...
```

**Nei test** (proprietà del BA/QA o del Test Architect): via `burnup test define`.

## Freschezza dei test

| Policy | Quando un `pass` conta |
|---|---|
| `current-revision` | il test è girato sulla revisione corrente, con working tree pulito e revisione dichiarata dal report o da un sidecar |
| `manual-confirmation` | esiste una conferma registrata con attore, motivo ed evidenza |
| `latest-known` | l'ultimo esito noto vale sempre — nessun controllo |

Per `current-revision` serve un sidecar accanto al report:

```json
// test-results/junit.xml.meta.json
{"source_revision": "abc1234", "executed_at": "2026-07-31T09:00:00Z"}
```

Senza sidecar la revisione resta sconosciuta e il test non soddisfa la policy. È il comportamento corretto: la v3 timbrava i report con l'HEAD del momento del refresh, il che rendeva quella policy sempre vera e quindi priva di significato.

## Sviluppo

```bash
pip install -e ".[dev]"
pytest                        # 76 test
pytest --cov=burnup           # copertura, soglia 85%
python -O -m pytest           # i controlli di integrità devono restare attivi
```

`tests/test_audit_probes.py` contiene i 23 probe dell'audit della v3, `tests/test_added_findings.py` i 7 rilevati dalla revisione critica. Se uno torna rosso, un difetto chiuso si è riaperto.
