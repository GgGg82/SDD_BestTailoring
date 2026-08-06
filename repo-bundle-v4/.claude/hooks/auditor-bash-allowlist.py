#!/usr/bin/env python3
"""PreToolUse hook: allowlist dei comandi Bash per gli agenti Checker.

Chiude la parte implementabile di P2-05 dell'audit, e trasforma in enforcement
tecnico cio' che INSTALL.md dichiara onestamente essere solo comportamentale.

Il Technical Auditor non ha `Write`/`Edit` — quello e' un limite reale — ma ha
`Bash`, quindi potrebbe scrivere un file arbitrario per redirezione. Questo
hook blocca i comandi che modificano il filesystem al di fuori di cio' che a un
Checker serve davvero: eseguire linter, analizzatori statici, test runner e lo
strumento burn-up.

Installazione in `.claude/settings.json`:

    {
      "hooks": {
        "PreToolUse": [
          {
            "matcher": "Bash",
            "hooks": [
              {"type": "command",
               "command": "python3 .claude/hooks/auditor-bash-allowlist.py"}
            ]
          }
        ]
      }
    }

Nota onesta sui limiti: e' un filtro sintattico, non una sandbox. Copre gli usi
accidentali e le scorciatoie, non un aggiramento deliberato e creativo. Per una
garanzia forte serve isolamento a livello di processo o di filesystem.
"""
from __future__ import annotations

import json
import re
import sys

# Comandi consentiti: sola lettura, analisi, esecuzione di test, strumento burn-up.
ALLOWED_PREFIXES = (
    "burnup", "python -m burnup", "python3 -m burnup",
    "pytest", "python -m pytest", "python3 -m pytest", "tox", "nox",
    "ruff", "flake8", "pylint", "mypy", "pyright", "bandit", "semgrep",
    "black --check", "isort --check", "eslint", "tsc --noEmit", "npm test",
    "npm run lint", "npm run test", "go vet", "go test", "cargo clippy", "cargo test",
    "git status", "git diff", "git log", "git show", "git rev-parse", "git ls-files",
    "ls", "cat", "head", "tail", "wc", "find", "grep", "rg", "which", "echo", "pwd",
)

# Costrutti che modificano il filesystem o lo stato del repository.
FORBIDDEN_PATTERNS = (
    (r">>?\s*[^&|\s]", "redirezione su file"),
    (r"\btee\b", "tee scrive su file"),
    (r"\b(rm|mv|cp|touch|mkdir|rmdir|ln|chmod|chown|truncate|dd)\b", "comando che modifica il filesystem"),
    (r"\bsed\b[^|]*-i", "sed in-place"),
    (r"\bgit\s+(add|commit|push|checkout|reset|rebase|merge|restore|apply|clean|stash)\b",
     "comando git che modifica il repository"),
    (r"\b(curl|wget|nc|ssh|scp)\b", "accesso di rete"),
    (r"\b(sudo|su)\b", "escalation di privilegi"),
    (r"\bpip\s+install\b", "installazione di pacchetti"),
    (r"\b(python|python3)\s+-c\b", "esecuzione di codice inline: aggira l'allowlist"),
    (r"\beval\b", "eval"),
)

CHECKER_AGENTS = {"technical-auditor", "business-analyst-qa"}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # payload illeggibile: non e' compito dell'hook rompere la sessione

    agent = (payload.get("agent") or payload.get("subagent") or "").strip().lower()
    if agent and agent not in CHECKER_AGENTS:
        return 0  # l'allowlist vincola solo i Checker

    command = (payload.get("tool_input") or {}).get("command", "")
    if not command.strip():
        return 0

    for pattern, why in FORBIDDEN_PATTERNS:
        if re.search(pattern, command):
            print(
                json.dumps({
                    "decision": "block",
                    "reason": (
                        f"Comando bloccato per un agente Checker: {why}.\n"
                        f"  {command[:200]}\n"
                        "Un Checker verifica e riporta, non modifica. Se il fix e' ovvio, "
                        "segnalalo al Maker competente invece di applicarlo.\n"
                        "Eccezione prevista: requirement-burnup-config.yml, che va scritto "
                        "durante l'intervista di 'burnup-init'."
                    ),
                }),
                file=sys.stdout,
            )
            return 2  # exit code 2 = blocca l'esecuzione dello strumento

    first = command.strip().split("&&")[0].split("|")[0].strip()
    if not any(first.startswith(p) for p in ALLOWED_PREFIXES):
        print(
            json.dumps({
                "decision": "block",
                "reason": (
                    f"Comando non presente nell'allowlist dei Checker: '{first[:120]}'.\n"
                    "Consentiti: strumento burn-up, test runner, linter, analizzatori statici, "
                    "scanner di sicurezza, comandi git di sola lettura.\n"
                    "Se ti serve davvero, e' un gap dell'allowlist: segnalalo invece di aggirarlo."
                ),
            }),
            file=sys.stdout,
        )
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
