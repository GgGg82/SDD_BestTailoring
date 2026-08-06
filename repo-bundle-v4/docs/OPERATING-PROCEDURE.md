# OPERATING-PROCEDURE — Runbook

**Versione:** 2.0 · **Destinatario:** Technical Auditor e Orchestratore

## Attivazione, una tantum

1. Intervista di configurazione con l'utente: presenta ogni scelta con la tua raccomandazione **e il motivo**, e falla confermare. Non compilare in silenzio con i default — ogni voce di `requirement-burnup-config.yml` cambia cosa conta come "fatto".
2. Scrivi il file partendo dal template.
3. `burnup init --project-root .`
4. Verifica che `state/` e `reports/` siano stati creati e **commit dello stato iniziale**.

Scelte che meritano davvero una discussione, non un default:

| Voce | Perché discuterla |
|---|---|
| `source_globs` | troppo ampio rallenta e aumenta i falsi positivi; troppo stretto perde evidenza |
| `test_freshness_policy` | è la definizione operativa di "verificato". Senza pipeline, `manual-confirmation`; con CI, `current-revision` |
| `require_tasks_for_implemented` | `false` accetta il solo marcatore nel codice come prova di implementazione |
| `strict_blocks_on` | quali severità fermano un rilascio |
| `accepted_id_patterns` | deve combaciare con la convenzione reale della spec |

## Ciclo per feature

```bash
burnup refresh --project-root .            # durante il lavoro, quando serve
burnup refresh --strict                    # PRIMA dell'approvazione del Gate 4
burnup gate approve <feature> 4 --actor <chi> --reason <perché>
```

`--strict` prima del gate, non dopo. Nella v3 il refresh avveniva dopo la chiusura del Gate 4, e restituiva comunque 0: una feature poteva risultare conclusa prima che il sistema scoprisse un problema bloccante.

## Come si legge un esito

```bash
burnup refresh --strict --json
```

| Exit code | Cosa fare |
|---:|---|
| 0 | procedi |
| 1 | correggi `requirement-burnup-config.yml`; nessun file è stato scritto |
| 2 | ci sono finding bloccanti: risolvili o registra un waiver motivato |
| 3 | è un bug dell'engine: segnalalo, non aggirarlo |

## Findings ricorrenti e come si chiudono

| Tipo | Severità | Chiusura |
|---|---|---|
| `missing-mandatory-test` | high | `burnup test define … --mandatory` |
| `failing-mandatory-test` | high | correggi codice o test, poi rilancia |
| `source-missing` | high | `burnup requirement remove` se voluto, altrimenti ripristina l'ID |
| `duplicate-requirement-id` | high | rendi univoci gli ID nella feature |
| `requirement-changed` | medium | riesegui i test e riconferma i collegamenti |
| `incomplete-tasks` | medium | completa i task, o correggi collegamenti non pertinenti |
| `stale-evidence` | medium | rilancia sulla revisione corrente, o `burnup test confirm-manual` |
| `unreadable-report` | medium | correggi il formato, o escludilo da `test_report_globs` |
| `marker-outside-comment` | low | sposta il marcatore dentro un commento |
| `reference-outside-requirements` | low | informativo: l'ID è citato fuori dalle sezioni dei requisiti |
| `test-orphan` | low | correggi `requirement_keys` del test |

Un finding scompare da solo quando la condizione che lo genera sparisce: viene chiuso come `resolved`. Non serve chiuderlo a mano.

## Cosa NON fare

- **Non modificare i file in `reports/`.** Vengono sovrascritti al prossimo refresh. Se ti trovi a volerlo fare, ti manca un comando: segnalalo.
- **Non ricalcolare i numeri a mente.** Un conteggio che sembra sbagliato è un bug da segnalare, non qualcosa da correggere ragionandoci sopra.
- **Non usare `--force` sui gate come scorciatoia.** Registra la decisione come `conditionally-approved` e scrive nel record quali criteri non erano soddisfatti: è tracciato, e si vede.
- **Non cancellare `state/`.** È la storia del progetto. `reports/` invece è usa e getta.

## Recovery

| Sintomo | Rimedio |
|---|---|
| `store-error: file non leggibile` | ripristina il file da Git: è versionato apposta |
| `lock-error` | un altro processo sta scrivendo. Se è morto, rimuovi `state/.lock` |
| report cancellati o corrotti | `burnup refresh` li rigenera dallo stato |
| store irrecuperabile | `burnup init --reset` — **la storia va persa**, ultima risorsa |
| `status` dice `stale` | esegui un refresh: gli input sono cambiati dopo l'ultima misurazione |

## Integrazione con CI

```yaml
- name: Quality gate sui requisiti
  run: burnup refresh --project-root . --strict --json > burnup.json
```

Exit code 2 fa fallire lo step. `burnup.json` contiene i finding bloccanti in forma machine-readable, pronti per essere pubblicati come commento su una pull request.
