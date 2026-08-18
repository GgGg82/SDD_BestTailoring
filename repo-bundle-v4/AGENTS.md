# AGENTS.md — istruzioni minime per qualunque agente su questo repository

Questo file esiste per gli strumenti che **non** leggono `CLAUDE.md`: Codex CLI e ogni altro agente che segue la convenzione `AGENTS.md`. Contiene le regole che valgono a prescindere dallo strumento, e **puntatori** al resto — mai copie.

> **Se stai usando Claude Code**, il tuo file è `CLAUDE.md`: contiene il flusso completo, i sei agenti e i loro step. Questo file non lo sostituisce e non lo riassume.

---

## Che cos'è questo repository

Un progetto governato da un processo **Spec-Driven Development** strutturato: architettura **Maker–Checker** e **quattro Gate** numerati, costruito sopra Spec Kit.

Il contenuto del progetto — cosa si sta costruendo e perché — non sta qui. Sta in `pre-speckit/project-brief.md`. Le convenzioni tecniche stanno in `.specify/memory/constitution.md`.

---

## Le regole che valgono per ogni strumento

Queste quattro regole non presuppongono alcun meccanismo di subagent. Valgono anche se lo strumento che stai usando fa tutto in un contesto solo.

**1. Una feature non è conclusa senza una verifica indipendente.** Se il tuo strumento non ha agenti Checker separati, la verifica va comunque eseguita — come passaggio distinto, con criteri dichiarati prima di guardarne l'esito. Chi ha scritto una cosa non è la persona adatta a certificare che sia giusta, e questo non dipende dallo strumento: dipende da chi guarda.

**2. Un Gate si supera solo con conferma esplicita dell'utente umano.** Mai dedurla, mai assumerla dal silenzio. Lo stato reale dei gate si legge con `burnup gate status <feature>` — non da un file di testo, che può essere vecchio.

**3. Leggi `PROJECT-STATE.md` a inizio sessione.** Ti dice quali feature esistono, a che punto sono, quali cicli non stanno convergendo e quali finding sono aperti. **Non aggiornarlo a mano:** è generato. Si rigenera con `burnup project-state`, ed è il modo corretto di aggiornarlo dopo un evento significativo.

**4. Registra le decisioni umane con attore e motivo.** Ogni decisione che cambia lo stato del progetto passa da un comando che ne conserva traccia — `burnup gate approve`, `burnup finding waive`, `burnup test define`. Una decisione presa a voce e non registrata, fra sei mesi, non è mai avvenuta.

---

## Dove sta cosa

| File | Cosa contiene |
|---|---|
| `CLAUDE.md` | Il flusso completo: fasi, step, i sei agenti, i gate. Specifico di Claude Code, ma **è la fonte normativa del processo** anche se usi un altro strumento |
| `PROJECT-STATE.md` | Stato corrente, generato. Non modificare a mano |
| `.specify/memory/constitution.md` | Principi e vincoli tecnici del progetto |
| `pre-speckit/project-brief.md` | Cosa si sta costruendo e perché |
| `pre-speckit/user-journeys.md` | I percorsi dell'utente e quali feature li coprono |
| `docs/` | Documentazione normativa: quando un requisito è `tested`, cosa conta come collegamento, come si chiude un finding |
| `specs/<NNN-feature>/progress.md` | Stato di dettaglio della singola feature |

---

## Cosa non fare

- **Non modificare i file generati.** `PROJECT-STATE.md` e tutto ciò che sta in `requirement-burnup/reports/` si rigenerano: una modifica manuale sparisce al primo rigenero, e nel frattempo qualcuno l'avrà creduta vera. Se ti serve cambiare un dato lì dentro, ti manca un comando — segnalalo, non aggirarlo.
- **Non ricalcolare a mente i numeri del burn-up.** Sono prodotti da uno strumento deterministico. Se un conteggio sembra sbagliato è un bug da segnalare, non un numero da correggere.
- **Non cancellare un file di lock di git.** Se un'operazione git fallisce per lock, fermati e segnala.
- **Non duplicare qui regole che stanno altrove.** Due copie divergono, e quando divergono nessuno sa quale valga.

---

## Nota sulle differenze fra strumenti

`CLAUDE.md` e i file in `.claude/agents/` sono meccanismi di Claude Code. Se usi Codex CLI o un altro strumento sullo stesso repository, il meccanismo di subagent isolato **non è detto sia equivalente**: verificalo invece di darlo per scontato.

Ciò che deve restare identico non è il meccanismo, sono le garanzie: separazione fra chi produce e chi verifica, conferma umana ai gate, decisioni registrate, misurazione deterministica. Se il tuo strumento non offre subagent isolati, le garanzie vanno ottenute in un altro modo — non abbandonate.

Anche l'invocazione dei comandi Spec Kit differisce fra strumenti: Claude Code li espone come `/speckit-<nome>`, Codex in modalità skills come `$speckit-<nome>`. Il nome canonico del comando resta con il punto (`speckit.tasks`) nei preset e nei percorsi.
