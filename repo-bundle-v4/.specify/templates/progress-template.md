# Stato Avanzamento — NNN-nome-feature

Creato: YYYY-MM-DD
Ultimo aggiornamento: YYYY-MM-DD HH:MM

**Classe di change:** _____ (Fast Track | Standard | High-Risk)
**Motivazione della classe:** _____
> Dichiarala anche all'engine: `burnup feature class <NNN-feature> <classe> --actor <chi> --reason <perché>`.
> Vedi `docs/SCALE-ADAPTIVE-FLOW.md`. Fast Track salta i Gate 2 e 3, ma NON riduce
> tracciabilità, test obbligatori né `refresh --strict` prima del Gate 4.
> La classe può essere promossa in corsa, mai retrocessa.

## Fase -1 — Pre-Spec Kit
> Step opzionali o modulati per classe di change. Uno step non eseguito si annota **`saltato (motivo, attore)`**: mai lasciato vuoto, mai spuntato. Un vuoto si legge come dimenticanza; una spunta mente.
- [ ] -1.0 Brainstorming — pre-speckit/brainstorming/AAAA-MM-GG-tema.md (Product Manager) — **opzionale**: raccomandato dall'Orchestratore, deciso dall'utente — esito: _____
- [ ] -1.1 Project Brief redatto — pre-speckit/project-brief.md (Product Manager) — una tantum per progetto: N/A nelle feature successive
- [ ] -1.2 User journeys verificate/aggiornate — pre-speckit/user-journeys.md (Product Manager) — Fast Track: verifica ridotta — esito: _____

## Fase 0 — Bootstrap (una tantum per progetto)
- [ ] 0.1 Progetto inizializzato — `specify init` (Solutions Architect) — N/A se il repo è già inizializzato
- [ ] 0.2 Constitution redatta/verificata (Solutions Architect) — N/A se già presente

## Fase 1 — Requisiti (COSA)
- [ ] 1.1 spec.md creata (Product Manager)
- [ ] 1.2 Chiarimenti completati (Business Analyst/QA ↔ Product Manager)
- [ ] 1.3 Checklist requisiti generata — checklists/requirements.md (Business Analyst/QA)
- [ ] **GATE 1 — Requirements Baseline**
      - approvato da: _____ il: _____
      - fingerprint spec.md: _____
      - findings aperti: _____ | waiver: _____

## Fase 2 — Piano Tecnico (COME)
- [ ] 2.1 plan.md creato (Solutions Architect)
- [ ] 2.2 Checklist tecnica generata — checklists/plan.md (Business Analyst/QA)
- [ ] 2.2-risk Risk register redatto e deciso con l'utente — risk-register.md (Business Analyst/QA)
- [ ] 2.1-loop plan.md aggiornato per le mitigazioni accettate (Solutions Architect) — N/A se nessuna richiedeva modifiche al piano
- [ ] **GATE 2 — Solution Baseline**
      - approvato da: _____ il: _____
      - fingerprint plan.md: _____
      - findings aperti: _____ | waiver: _____

> ⚠️ Nessun `/speckit.analyze` in questa fase: il comando richiede `tasks.md`, che non esiste ancora.
> ⚠️ Se una mitigazione decisa in 2.2-risk richiede modifiche a `spec.md` (il COSA), la feature torna a **Fase 1 / Gate 1**.

## Fase 3 — Task
- [ ] 3.1 tasks.md creato con Requirement Key in ogni task (Tech Lead)
- [ ] 3.2 Analyze eseguito — spec vs plan vs tasks vs constitution (Technical Auditor) — **unica invocazione valida di `/speckit.analyze`**
- [ ] **GATE 3 — Implementation Readiness**
      - approvato da: _____ il: _____
      - fingerprint tasks.md: _____
      - copertura requisiti→task: _____ % | findings aperti: _____

## Fase 4 — Codifica e Verifica
- [ ] 4.1 Implementazione completata, con marcatori `REQ:` nel codice (Software Engineer)
- [ ] 4.2 Verifica indipendente del codice — lint, analisi statica, security, test suite (Technical Auditor)
      - comandi eseguiti: _____
      - esito: _____
- [ ] 4.3 Converge eseguito — esito: _____ (Technical Auditor)
- [ ] 4.3-review Task aggiunti da converge approvati (Tech Lead) — N/A se converged al primo giro
- [ ] 4.4-loop Gap implementati (Software Engineer) — N/A se converged al primo giro
- [ ] 4.5 Collaudo funzionale sugli scenari di accettazione (Business Analyst/QA)
- [ ] **burnup refresh --strict eseguito** (Technical Auditor) — exit code: _____ — **PRIMA del Gate 4, non dopo**
- [ ] **GATE 4 — Release Readiness**
      - approvato da: _____ il: _____
      - burn-up: scope _____ | tested _____ | exit code _____
      - findings bloccanti: _____ | waiver approvati: _____
      - condizioni di approvazione: _____

> ⚠️ Il Gate 4 non è approvabile con `burnup refresh --strict` diverso da 0, salvo waiver formalmente registrati con `burnup finding waive`.

## Fase 5 — Rilascio
- [ ] 5.1 Merge (Utente Umano)

---
## Invalidazione dei gate

Se un artefatto cambia dopo l'approvazione, i gate a valle decadono e vanno ri-approvati:

| Cambia | Decadono |
|---|---|
| spec.md | Gate 1, 2, 3, 4 |
| plan.md | Gate 2, 3, 4 |
| tasks.md | Gate 3, 4 |
| codice / test | Gate 4 |

Questa tabella è una **vista**. La fonte di verità è il canonical store:

```
burnup gate status <feature>     # stato reale, con invalidazione calcolata
burnup status                    # freschezza della misurazione
```

---
## Cicli di ritorno e non-convergenza

> Il **secondo rigetto consecutivo sulla stessa causa** fa scattare la regola di non-convergenza (`CLAUDE.md`).
>
> **Per i rigetti di gate non tenere alcun conteggio:** lo deriva `burnup project-state` dai Gate Decision Record e lo riporta in `PROJECT-STATE.md`, sezione *Cicli che non convergono*. Un contatore tenuto a mano si dimentica, e una regola che non scatta è come se non ci fosse.
>
> Qui sotto vanno **solo** i cicli che non passano da un gate — per esempio il Business Analyst che rimanda `spec.md` al Product Manager durante l'1.2. Quelli non lasciano alcun record, e nessuno li deriva al posto tuo.

| Causa (requisito o task) | Maker | Checker | Rigetti consecutivi | Esito |
|---|---|---|:-:|---|
| | | | | |

**Escalation autorizzate** — una sola per causa.

| Data | Causa | Autorizzata da | Modello richiesto | Modello effettivo | Ha risolto? |
|---|---|---|---|---|:-:|
| | | | | | |

> La colonna **modello effettivo** non è burocrazia: `CLAUDE_CODE_SUBAGENT_MODEL` ha precedenza sul parametro per-invocazione, e l'allowlist dell'organizzazione può sostituire il modello. Senza questa colonna un'escalation mai avvenuta risulterebbe eseguita.

---
Note libere / blocchi in corso:
