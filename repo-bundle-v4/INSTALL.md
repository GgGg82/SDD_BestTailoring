# Installazione

## 1. Spec Kit — con release pinnata

Questi file **non sostituiscono** Spec Kit: lo presuppongono installato.

```bash
# Sostituisci <TAG> con la release verificata nella matrice di compatibilità qui sotto.
uvx --from git+https://github.com/github/spec-kit@<TAG> specify init --here --integration claude
specify version   # verifica che la versione corrisponda
```

> **Due correzioni rispetto alla v3.**
>
> Il comando documentato nella v3 era `uvx --from git+https://github.com/github/spec-kit specify init --here --ai claude`, e oggi **non funziona**: il flag `--ai` è stato rimosso in Spec Kit v0.10.0, non semplicemente deprecato. Va usato `--integration`.
>
> Inoltre l'installazione puntava a `main` senza pin. Questo framework dipende dalla semantica esatta di `analyze`, `converge`, `checklist` e dal formato dei template dei task: senza pin, un aggiornamento a monte può cambiare quella semantica sotto i piedi, in silenzio.

### Matrice di compatibilità

| Framework | Spec Kit testato | Note |
|---|---|---|
| 4.0.0-rc.2 | *da fissare al momento del bootstrap* | Registra qui il tag verificato ed eseguito con successo end-to-end. |

Prima di aggiornare Spec Kit: esegui la suite di test del framework, poi una feature demo end-to-end, e solo dopo aggiorna questa tabella.

## 2. Copia dei file

```
tuo-repo/
├── CLAUDE.md
├── docs/                      ← documentazione normativa (9 file)
├── .claude/
│   ├── agents/                ← i 6 agenti
│   └── hooks/                 ← allowlist Bash dei Checker (opzionale, vedi §6)
├── .specify/templates/        ← progress-template.md, risk-register-template.md
├── pre-speckit/               ← project-brief.md, user-journeys.md
├── sdd-traceability-preset/   ← preset Spec Kit (opzionale, vedi §3b)
└── requirement-burnup-tool/   ← opzionale, vedi §3
```

`docs/` non è decorativo: `CLAUDE.md` e gli agenti vi rimandano per le regole che non vanno dedotte — quando un requisito è `tested`, cosa conta come collegamento, come si chiude un finding. Copiarlo è parte dell'installazione, non un extra.

Se il repo ha già `.claude/` o `.specify/` create da `specify init`, **unisci** il contenuto: non sovrascrivere le cartelle intere.

`requirement-burnup-config.yml` e la cartella `requirement-burnup/` **non** fanno parte della copia: nascono con `burnup init`.

## 3. Estensione Requirement Burn-up (opzionale)

Richiede Python 3.10+.

```bash
# Consigliato: installazione isolata, senza toccare il Python di sistema
uv tool install ./requirement-burnup-tool

# In alternativa, un virtualenv del progetto
python -m venv .venv
.venv/bin/pip install ./requirement-burnup-tool     # Windows: .venv\Scripts\pip
```

> La v3 documentava `pip install pyyaml --break-system-packages` come istruzione primaria. Quel flag scavalca la protezione delle distribuzioni Linux moderne e può danneggiare il Python di sistema. Non è necessario: il pacchetto dichiara le proprie dipendenze.

Verifica:

```bash
burnup --version
```

Se il progetto non ha bisogno di tracciabilità dei requisiti, ometti semplicemente questa cartella: nessun altro file del framework dipende da essa.

### Cosa versionare

```
requirement-burnup/state/      ← VERSIONA: è la fonte di verità e la storia del progetto
requirement-burnup/reports/    ← versiona se vuoi leggerli su GitHub; sono rigenerabili
requirement-burnup/state/.lock ← NON versionare (transitorio)
```

## 3b. Preset `sdd-traceability` (consigliato)

Impone i Requirement Key nei task generati da `/speckit.tasks`. Senza, il burn-up misura l'assenza di metadata invece dell'assenza di implementazione — è il difetto P0-02 della v3.

```bash
specify preset add --dev ./sdd-traceability-preset --priority 5
specify preset resolve speckit.tasks    # verifica che vinca questo layer
```

Allinea `requires.speckit_version` in `sdd-traceability-preset/preset.yml` al tag fissato al §1.

## 4. Dopo la copia

1. **Riavvia completamente Claude Code.** I subagent in `.claude/agents/` vengono caricati all'avvio della sessione, non rilevati a caldo.
2. Verifica che i 6 agenti siano visibili con `/agents`.
3. Apri una nuova conversazione nel repo: la sessione principale caricherà `CLAUDE.md` e saprà di essere l'Orchestratore.
4. Per attivare il burn-up, invoca `@technical-auditor` e chiedi lo step `burnup-init`: condurrà lui l'intervista di configurazione.

## 5. Verifica dell'installazione

```bash
cd requirement-burnup-tool && pytest        # la suite deve essere verde
burnup --version
burnup status --project-root .              # deve dire che manca lo store, non andare in errore
```

## 6. Limiti di enforcement — avvertimento onesto

I permessi degli agenti (`tools:` nel frontmatter) operano a livello di **tipo di strumento**, non di **percorso**. Claude Code non supporta nativamente "può scrivere solo dentro `checklists/`".

- Per il **Business Analyst/QA** la restrizione sugli artefatti è imposta dal system prompt: garanzia comportamentale forte, non un blocco tecnico.
- Il **Technical Auditor** non ha `Write`/`Edit` — quello resta un limite tecnico reale. Ha però `Bash`, quindi potrebbe scrivere per redirezione. La sua allowlist è quindi comportamentale, e in v4 è deliberatamente **più ampia** che in v3: senza la possibilità di eseguire linter e test, un Checker non può generare evidenza indipendente e la separazione Maker–Checker resta solo nominale.

### Hook di allowlist (opzionale, consigliato)

`.claude/hooks/auditor-bash-allowlist.py` trasforma parte di questa restrizione in enforcement tecnico: blocca redirezioni, `sed -i`, comandi git che modificano il repository e installazioni di pacchetti quando l'agente in esecuzione è un Checker.

Attivalo aggiungendo a `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {"type": "command", "command": "python3 .claude/hooks/auditor-bash-allowlist.py"}
        ]
      }
    ]
  }
}
```

**È un filtro sintattico, non una sandbox.** Copre le scorciatoie — un `sed -i` per sistemare al volo, un `>` per salvare un output — non un aggiramento deliberato. Per una garanzia forte serve isolamento a livello di processo o di filesystem.

Prima di adottarlo, verifica l'allowlist in `.claude/hooks/README.md` contro i comandi che il tuo progetto usa davvero: un hook che blocca il lavoro normale viene disattivato, e a quel punto non protegge più nulla.

## 7. Il framework è generico

Non contiene assunzioni su dominio, linguaggio, piattaforma o azienda. Il contesto specifico del progetto va in `.specify/memory/constitution.md`, che è il posto previsto per convenzioni, stack e vincoli particolari — non nei prompt degli agenti.
