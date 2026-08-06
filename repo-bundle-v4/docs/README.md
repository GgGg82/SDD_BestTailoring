# Documentazione normativa

Se il codice diverge da questi documenti, è il codice ad avere un bug. Sono versionati insieme all'engine e cambiano solo per decisione esplicita.

| Documento | Risponde a |
|---|---|
| [ARCHITECTURE](ARCHITECTURE.md) | com'è fatto il sistema e perché il Markdown non è il database |
| [STATUS-RULES](STATUS-RULES.md) | quando un requisito è `defined`, `implemented`, `tested`, `removed` |
| [TRACEABILITY-RULES](TRACEABILITY-RULES.md) | cosa conta come collegamento e cosa viene rifiutato |
| [BURNUP-CALCULATION](BURNUP-CALCULATION.md) | come si calcolano i conteggi e quando si registra uno snapshot |
| [TEST-REGISTER-SPEC](TEST-REGISTER-SPEC.md) | definizioni, adapter, idempotenza, risoluzione dei Test ID |
| [OPERATING-PROCEDURE](OPERATING-PROCEDURE.md) | runbook: attivazione, ciclo per feature, findings, recovery |
| [DESIGN-DECISIONS](DESIGN-DECISIONS.md) | perché le cose sono così, e cosa si è accettato di perdere |
| [RACI](RACI.md) | chi esegue, chi risponde, chi va consultato |
| [SCALE-ADAPTIVE-FLOW](SCALE-ADAPTIVE-FLOW.md) | Fast Track / Standard / High-Risk, e cosa non scala mai |

## Diagramma di flusso

`sdd-workflow-v4.html` alla radice del repository: documento self-contained (Mermaid inlinato, funziona offline) con il flusso completo, la state machine dei gate, il ciclo di vita dei requisiti e l'elenco delle correzioni rispetto alla v3.

Sostituisce `sdd_workflow_diagramma-1.html`, che descrive il flusso della v3 — ora sbagliato in tre punti: `analyze` invocato prima che `tasks.md` esistesse, `analyze` usato per verificare il codice, e il burn-up eseguito dopo la chiusura del Gate 4.

## Nota sull'origine

Questi documenti erano **citati dal codice della v3 come fonte di verità, senza esistere**: `DESIGN-DECISIONS.md`, `TRACEABILITY-RULES.md`, `OPERATING-PROCEDURE.md`, `STATUS-RULES.md`, `BURNUP-CALCULATION.md`, `ARCHITECTURE.md`, `TEST-REGISTER-SPEC.md` erano tutti riferimenti a file assenti (P1-22 dell'audit).

Un codice che cita una fonte di verità inesistente è peggio di un codice che non ne cita nessuna: promette una giustificazione che nessuno può leggere, e chi legge il commento smette di cercarla.
