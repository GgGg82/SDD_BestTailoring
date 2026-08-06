# Stato Avanzamento — NNN-nome-feature

Creato: YYYY-MM-DD
Ultimo aggiornamento: YYYY-MM-DD HH:MM

## Fase Meno Uno — Pre-Spec Kit
- [ ] -1.1 Project Brief redatto — pre-speckit/project-brief.md (Product Manager) — una tantum: spunta solo alla primissima feature del progetto, segna N/A nelle feature successive
- [ ] -1.2 User journeys verificate/aggiornate per questa feature — pre-speckit/user-journeys.md (Product Manager)

## Fase 0 — Setup
- [ ] 0.1 Repo/branch inizializzato (Solutions Architect)
- [ ] 0.2 Constitution redatta/verificata (Solutions Architect)

## Fase 1 — Requisiti (COSA)
- [ ] 1.1 spec.md creata (Product Manager)
- [ ] 1.2 Chiarimenti completati (Business Analyst/QA ↔ Product Manager)
- [ ] 1.3 Checklist requisiti generata — checklists/requirements.md (Business Analyst/QA)
- [ ] **GATE 1** — approvato da: _____ il: _____

## Fase 2 — Piano Tecnico (COME)
- [ ] 2.1 plan.md creato (Solutions Architect)
- [ ] 2.2 Checklist tecnica generata — checklists/plan.md (Business Analyst/QA)
- [ ] 2.2-risk Risk register redatto e deciso con l'utente — risk-register.md (Business Analyst/QA)
- [ ] 2.1-loop plan.md aggiornato in risposta a rischi mitigati (Solutions Architect) — N/A se nessuna mitigazione richiedeva modifiche al piano
- [ ] 2.3 Analyze eseguito: spec vs plan vs constitution (Technical Auditor)
- [ ] **GATE 2** — approvato da: _____ il: _____

⚠️ Se una mitigazione decisa in 2.2-risk richiede modifiche a `spec.md` (il COSA), questa feature torna a **Fase 1 / Gate 1** — non resta in Fase 2. Annotalo qui sotto in "Note libere" se succede.

## Fase 3 — Task
- [ ] 3.1 tasks.md creato (Tech Lead)
- [ ] 3.2 Analyze eseguito: plan vs tasks (Technical Auditor)
- [ ] **GATE 3** — approvato da: _____ il: _____

## Fase 4 — Codifica e Collaudo
- [ ] 4.1 Implementazione completata (Software Engineer)
- [ ] 4.2 Analyze eseguito: compliance codice (Technical Auditor)
- [ ] 4.3 Converge eseguito — esito: _____ (Technical Auditor)
- [ ] 4.3-loop Eventuali gap risolti (Software Engineer) — N/A se converged al primo giro
- [ ] 4.4 Collaudo funzionale completato (Business Analyst/QA)
- [ ] **GATE 4** — approvato da: _____ il: _____
- [ ] burnup-refresh eseguito (Technical Auditor) — N/A se l'estensione Requirement Burn-up non è attiva in questo repo (nessun `requirement-burnup-config.yml` alla radice)

## Fase 5 — Release
- [ ] 5.1 Merge su main (Utente Umano)

---
Note libere / blocchi in corso:
