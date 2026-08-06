# Hook di permesso

Enforcement tecnico che integra le restrizioni comportamentali dichiarate nei prompt degli agenti.

## `auditor-bash-allowlist.py`

Blocca i comandi Bash che modificano il filesystem quando l'agente in esecuzione è un Checker (`technical-auditor`, `business-analyst-qa`).

### Perché

`INSTALL.md` dichiara onestamente che i permessi di Claude Code agiscono a livello di **tipo di strumento**, non di **percorso**: il Technical Auditor non ha `Write`/`Edit`, ma ha `Bash`, quindi potrebbe scrivere un file arbitrario per redirezione. La restrizione è comportamentale.

Questo hook la rende tecnica per i casi che contano.

### Installazione

In `.claude/settings.json`:

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

### Limiti, dichiarati

È un **filtro sintattico**, non una sandbox. Copre gli usi accidentali e le scorciatoie — un `sed -i` per sistemare al volo, un `>` per salvare un output — non un aggiramento deliberato e creativo. Per una garanzia forte serve isolamento a livello di processo o di filesystem, che è fuori dallo scope di questi file base.

Preferisco dichiararlo che lasciare credere a una protezione che non c'è: la v3 aveva già il problema opposto, cioè documenti che promettevano garanzie non implementate.

### Prima di adottarlo

Verifica l'allowlist contro i comandi che il tuo progetto usa davvero. Se manca qualcosa di legittimo, aggiungilo qui: un'allowlist che blocca il lavoro normale viene disattivata, e a quel punto non protegge più nulla.
