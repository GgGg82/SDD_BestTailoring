# Come installare questo sistema nel tuo repo

## Prerequisiti

Questi file **non sostituiscono** Spec Kit — lo presuppongono già installato. Se non l'hai ancora fatto nel repo di destinazione:

```
uvx --from git+https://github.com/github/spec-kit specify init --here --ai claude
```

Questo crea la struttura `.specify/` (memory, templates, script) di cui i file qui sotto dipendono.

Se intendi usare anche l'estensione **Requirement Burn-up** (opzionale — vedi sezione dedicata sotto), serve inoltre:

```
python3 --version   # 3.10 o superiore
pip install pyyaml --break-system-packages   # oppure: uv pip install pyyaml
```

Se non ti interessa questa estensione, puoi ignorare questo prerequisito e semplicemente non copiare la cartella `requirement-burnup-tool/` — il resto del framework funziona comunque senza.

## Cosa copiare e dove

Copia questa struttura nella radice del tuo repository, mantenendo i percorsi esattamente così:

```
tuo-repo/
├── CLAUDE.md                              ← copia qui, radice del repo
├── .claude/
│   └── agents/
│       ├── solutions-architect.md
│       ├── product-manager.md
│       ├── tech-lead.md
│       ├── software-engineer.md
│       ├── business-analyst-qa.md
│       └── technical-auditor.md
├── .specify/
│   └── templates/
│       ├── progress-template.md
│       └── risk-register-template.md
├── pre-speckit/
│   ├── project-brief.md
│   └── user-journeys.md
└── requirement-burnup-tool/                (opzionale — vedi sotto)
    ├── README.md
    ├── requirement-burnup-config.template.yml
    ├── templates/
    └── engine/
```

`requirement-burnup-config.yml` **non** fa parte di questa copia: è l'istanza compilata insieme al Technical Auditor durante l'intervista di `burnup-init`, e vive alla radice del repo accanto a `CLAUDE.md`. Allo stesso modo, la cartella `requirement-burnup/` con gli artefatti generati non esiste finché non esegui `burnup-init` — non crearla a mano.

Se il tuo repo ha già una cartella `.claude/` o `.specify/` (creata da `specify init`), **unisci** il contenuto — non sovrascrivere l'intera cartella.

### Nota sulla cartella `pre-speckit/`

Questa cartella è **un'aggiunta di 123trading**, non parte nativa di Spec Kit — `specify init` non la crea e non la conosce. Contiene due file scritti e mantenuti dall'agente Product Manager: `project-brief.md` (visione di progetto, scritto una volta sola) e `user-journeys.md` (percorsi utente trasversali alle feature, documento vivo, aggiornato prima di ogni nuova feature). Il collegamento con Spec Kit è a senso unico — `user-journeys.md` può citare le feature Spec Kit, ma nessun file nativo di Spec Kit fa mai riferimento a `pre-speckit/`. Puoi copiare i due file così come sono: sono template pensati per essere compilati la prima volta che avvii il sistema su un progetto nuovo.

### Nota sulla cartella `requirement-burnup-tool/` (opzionale)

Anche questa è **un'aggiunta di 123trading**, non nativa di Spec Kit. A differenza di `pre-speckit/`, non è pensata per essere compilata a mano: contiene uno strumento Python di proprietà del Technical Auditor che, alla prima invocazione (`burnup-init`), conduce con te un'intervista di configurazione e scrive da solo `requirement-burnup-config.yml` alla radice del repo. Se il progetto non ha bisogno di tracciabilità requisiti/burn-up, ometti semplicemente questa cartella — nessun altro file del framework dipende da essa.

## Dopo la copia

1. **Riavvia completamente Claude Code** (non basta ricaricare la finestra): i subagent in `.claude/agents/` vengono caricati all'avvio della sessione, non rilevati a caldo.
2. Verifica che i 6 agenti siano visibili con il comando `/agents` in Claude Code.
3. Apri una nuova conversazione nel repo: la sessione principale caricherà automaticamente `CLAUDE.md` e saprà di essere l'Orchestratore (Project Manager).
4. Per iniziare la primissima feature di un progetto nuovo, di' semplicemente alla sessione principale cosa vuoi costruire — l'Orchestratore (guidato da `CLAUDE.md`) ti guiderà da lì, invocando prima `@product-manager` per il Project Brief (step -1.1), poi via via gli altri agenti.
5. Per una feature successiva su un progetto già avviato, l'Orchestratore invocherà `@product-manager` per l'aggiornamento delle user journeys (step -1.2) prima di procedere con `@solutions-architect`.
6. Se hai copiato `requirement-burnup-tool/` e vuoi attivare la tracciabilità requisiti/burn-up, invoca in qualunque momento `@technical-auditor` e chiedi lo step `burnup-init` — ti condurrà lui l'intervista di configurazione.

## Un avvertimento onesto

I permessi degli agenti (`tools:` nel frontmatter di ogni file) sono un limite a livello di *tipo di strumento* (es. "niente Write"), non a livello di *percorso specifico* (Claude Code non supporta nativamente "può scrivere solo dentro checklists/", né "può eseguire Bash solo per questo script"). Per il Business Analyst/QA, la restrizione "scrivi solo checklist, risk-register.md e report, mai spec.md/plan.md/tasks.md/codice" è imposta dal system prompt, non da un blocco tecnico — una garanzia comportamentale forte ma non impossibile da forzare con un prompt sufficientemente insistente.

Il **Technical Auditor** non ha `Write`/`Edit` — quella parte resta un limite tecnico reale. Ha però `Bash`, aggiunto per invocare lo strumento Requirement Burn-up: questo significa che, tecnicamente, potrebbe scrivere un file arbitrario tramite redirezione di shell, incluso uno nativo di Spec Kit. Non è più, quindi, una garanzia assoluta come lo era prima di questa estensione — resta comportamentale, rinforzata dal fatto che il suo file agente istruisce esplicitamente `Bash` a due soli usi. Se non installi `requirement-burnup-tool/`, puoi rimuovere `Bash` dai `tools:` di `technical-auditor.md` per tornare alla garanzia tecnica originale.

Se in futuro ti serve un'enforcement più rigida per uno di questi casi, valuta gli hook di permesso di Claude Code (fuori dallo scope di questi file base).
