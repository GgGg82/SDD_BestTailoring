# Requirement Burn-up Tool

Motore deterministico dell'estensione Requirement Burn-up del framework SDD multi-agente. Di proprietà del **Technical Auditor** — vedi `.claude/agents/technical-auditor.md` per il suo ruolo nel flusso, e `CLAUDE.md` alla radice del repo per come si inserisce nell'orchestrazione generale.

## Cosa fa e cosa non fa

Fa il lavoro **meccanico e deterministico**: estrae i requisiti da `spec.md`, li collega a task/codice/test solo quando c'è un riferimento esplicito, calcola lo stato del ciclo di vita, gestisce gli snapshot storici per il burn-up. Non interpreta mai nulla — se serve giudizio umano (confermare un legame plausibile ma non esplicito, decidere una rimozione, validare un test manuale), lo lascia come **Finding** per l'agente e per te.

## Prerequisiti

- Python 3.10+
- `pip install pyyaml --break-system-packages` (o `uv pip install pyyaml`)

## Comandi

Dalla radice del repo del progetto:

```bash
python requirement-burnup-tool/engine/cli.py init    --project-root .
python requirement-burnup-tool/engine/cli.py refresh  --project-root .
python requirement-burnup-tool/engine/cli.py refresh  --project-root . --force-snapshot
python requirement-burnup-tool/engine/cli.py status   --project-root .
```

`init` e `refresh` leggono `requirement-burnup-config.yml` alla radice del progetto (non incluso qui — è l'istanza compilata insieme a te durante l'intervista del Technical Auditor; il template è `requirement-burnup-config.template.yml` in questa cartella).

`status` è sempre e solo in lettura.

## Struttura

```text
requirement-burnup-tool/
├── README.md                              (questo file)
├── requirement-burnup-config.template.yml
├── templates/                             (scheletri dei 3 artefatti di output)
└── engine/                                (il motore Python)
```

## Confine non negoziabile

Lo strumento rifiuta di scrivere se la cartella di output configurata ricade dentro `specs/`, `.specify/specs/`, `.specify/templates/`, o `.specify/memory/`. Scrive solo dentro `output_dir` (default `requirement-burnup/`, generato nel repo del progetto — non in questa cartella).

## Estensione degli adapter di test

Sono inclusi adapter per report **JUnit XML** e un formato **JSON generico** documentato in `docs/TEST-REGISTER-SPEC.md` (se presente nel pacchetto di documentazione più ampio). Il matching test-report → Test ID catalogato è sempre letterale (il Test ID compare nel nome del test nel report) o esplicito (`traceability.test_id_mapping` in config) — mai indovinato.
