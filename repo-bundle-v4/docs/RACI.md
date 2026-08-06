# RACI — Responsibility Assignment Matrix

**Versione:** 2.0 · **Stato:** normativo

Chiude P2-04 dell'audit: i ruoli erano descritti, ma nessun documento diceva chi è responsabile di cosa, chi approva, chi va consultato.

**R** = Responsible (esegue) · **A** = Accountable (risponde dell'esito, **uno solo per riga**) · **C** = Consulted (contribuisce prima) · **I** = Informed (viene informato dopo)

Legenda ruoli: **ORC** Orchestratore · **PM** Product Manager · **SA** Solutions Architect · **TL** Tech Lead · **SE** Software Engineer · **BA** Business Analyst/QA · **TA** Technical Auditor · **UMA** Utente umano

## Artefatti

| Deliverable | ORC | PM | SA | TL | SE | BA | TA | UMA |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `project-brief.md` | C | R | C | I | I | C | I | **A** |
| `user-journeys.md` | C | R | I | I | I | C | I | **A** |
| `constitution.md` | C | C | R | C | C | C | C | **A** |
| `spec.md` | C | R | I | I | I | C | I | **A** |
| `checklists/requirements.md` | I | C | I | I | I | R | I | **A** |
| `plan.md` | C | C | R | C | I | C | C | **A** |
| `checklists/plan.md` | I | I | C | C | I | R | C | **A** |
| `risk-register.md` | C | C | C | I | I | R | C | **A** |
| `tasks.md` | C | I | C | R | C | C | C | **A** |
| codice sorgente | I | I | C | C | R | I | C | **A** |
| test (codice) | I | I | I | C | R | C | C | **A** |
| definizioni dei test | C | C | I | C | C | R | C | **A** |
| `progress.md` | R | I | I | I | I | I | I | **A** |
| canonical store del burn-up | I | I | I | I | I | I | R | **A** |

## Decisioni

| Decisione | ORC | PM | SA | TL | SE | BA | TA | UMA |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| approvazione di un gate | R *(processo)* | C | C | C | C | C | C | **A** |
| rifiuto di un gate | R | I | C | C | I | C | C | **A** |
| rimozione di un requisito | C | R | I | I | I | C | C | **A** |
| conferma di un collegamento | I | C | I | R | C | I | C | **A** |
| waiver di un finding | C | C | C | C | I | C | R *(registra)* | **A** |
| chiusura di un finding | I | I | I | C | C | C | R | **A** |
| conferma manuale di un test | I | I | I | I | I | R | C | **A** |
| deroga alla constitution | C | C | R | C | I | C | C | **A** |
| classe di change (§ scale-adaptive) | R | C | C | C | I | C | C | **A** |

## Verifica

| Attività | ORC | PM | SA | TL | SE | BA | TA | UMA |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| `/speckit.clarify` | I | C | I | I | I | R | I | I |
| `/speckit.analyze` (step 3.2) | I | I | C | C | I | I | R | I |
| verifica indipendente del codice (4.2) | I | I | I | C | I | I | R | **A** |
| `/speckit.converge` (4.3) | I | I | I | C | C | I | R | I |
| revisione dei task da converge (4.3-review) | C | I | C | R | C | I | C | **A** |
| collaudo funzionale (4.5) | I | C | I | I | I | R | I | **A** |
| `burnup refresh --strict` | C | I | I | I | I | I | R | I |

## Regole di lettura

1. **Una sola A per riga.** Se due ruoli rispondono della stessa cosa, non risponde nessuno.
2. **L'Accountable è quasi sempre l'utente umano.** Gli agenti eseguono e raccomandano; la responsabilità di un artefatto o di una decisione non è delegabile a un modello.
3. **R e A possono coincidere** solo per le attività di processo dell'Orchestratore.
4. **Chi è R su un artefatto non può essere R sulla sua verifica.** È la regola Maker–Checker espressa in forma di matrice. Unica eccezione dichiarata: `/speckit.converge`, dove l'Auditor genera task che poi valuterà — mitigata dalla revisione del Tech Lead in 4.3-review.

## Verifica di coerenza

Nessun ruolo compare come **R** sia sulla produzione sia sulla verifica dello stesso artefatto:

- `spec.md` → PM produce, BA verifica ✓
- `plan.md` → SA produce, BA e TA verificano ✓
- `tasks.md` → TL produce, TA verifica ✓
- codice → SE produce, TA verifica ✓
- test → SE scrive il codice di test, BA definisce i criteri, TA li riesegue ✓
