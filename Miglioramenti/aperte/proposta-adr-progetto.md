# Proposta: ADR di progetto (Architecture Decision Record) nel framework SDD

> ## ⚠️ PARZIALMENTE SUPERATA — richiede una decisione di sede prima di implementare
>
> **Baseline del documento:** v3 · **Baseline reale del repository:** v4.0.0-beta.1
> **Verificato il:** 2026-08-06 su `repo-bundle-v4/docs/DESIGN-DECISIONS.md`.
>
> La v4 contiene già `docs/DESIGN-DECISIONS.md`, dichiarato esplicitamente **"formato ADR abbreviato"**, con contesto, decisione, costo accettato e alternativa scartata per ogni voce (D-001, D-002, D-003, …). Copre però le decisioni **sull'engine** (canonical store, fingerprint, normalizzazione del case), non le decisioni **sul processo** che questa proposta vuole catturare (perché il Tech Lead resta separato, perché i due Checker non si accorpano).
>
> **Decisione da prendere prima di implementare:** cartella `docs/adr/` a file immutabili accanto a `DESIGN-DECISIONS.md`, oppure estensione di quest'ultimo con una sezione dedicata al processo. Due sedi senza un criterio esplicito di ripartizione divergono — è lo stesso tipo di fragilità che la sezione 4 di `proposta-sistema-memoria-progetto.md` evita deliberatamente per `AGENTS.md`.
>
> **Nota sull'owner:** la proposta assegna il registro a `@technical-auditor` motivandolo anche col fatto che "ha già permessi Bash". In v4 l'allowlist Bash dell'Auditor è stata allargata a lint, analisi statica, security e test runner, con un hook `PreToolUse` che blocca le scritture. La motivazione regge ancora, ma va riformulata: la scrittura di un file di documentazione non passa da Bash.
>
> Dettaglio in `ANALISI-CROSS-CHECK-MIGLIORAMENTI.md`.

---

**Stato originario dichiarato: PROPOSTA — non ancora implementata nel framework. Decisione di adozione presa dall'utente; implementazione tecnica da fare.**

**Destinatario di questo documento:** un'istanza AI (Claude Code o altro agente) incaricata in futuro di implementare questa modifica al framework di governance SDD a 6 agenti già esistente. Documento autosufficiente, non richiede la cronologia della conversazione che lo ha prodotto.

---

## 1. Cos'è un ADR e perché serve

Un **Architecture Decision Record (ADR)** è un documento breve e immutabile che cattura una singola decisione architetturale: il contesto che l'ha resa necessaria, la decisione presa, le conseguenze accettate. Concetto precedente a BMad, di uso comune nell'ingegneria del software (origine: Michael Nygard).

**Perché serve in questo framework:** già oggi, nel corso del suo sviluppo, sono state prese diverse decisioni architetturali consultive — cioè non decisioni prese dentro il ciclo Gate 1→4 di una feature, ma decisioni sulla struttura stessa del framework, discusse a voce con l'utente e chiuse con un esito netto. Oggi queste decisioni esistono solo nella cronologia delle conversazioni: non hanno una casa persistente e consultabile nel repository. Un domani, senza traccia scritta, si rischia di:
- rimettere in discussione da capo una decisione già analizzata a fondo, senza sapere che lo è già stata
- perdere il *perché* di una scelta, restando solo il *cosa*

## 2. Scope: SOLO livello progetto, non livello feature

Questa proposta riguarda **esclusivamente ADR di progetto** — decisioni durature sulla struttura del framework stesso (es. numero e ruolo degli agenti, criteri di routing, policy di modello/effort).

**Esplicitamente escluso da questa proposta:** ADR a livello di singola feature (per catturare scelte di design locali, es. "ricalcolo real-time invece che on-demand" in una feature specifica). È stata valutata e scartata: volume troppo alto, sovrapposizione con `plan.md`, nessun criterio chiaro su quale micro-decisione meriti un documento — andrebbe nella direzione opposta rispetto all'obiettivo di efficienza del framework. Se in futuro emergesse un bisogno reale non coperto da `plan.md`, va rivalutata da zero con un criterio di soglia esplicito, non recuperata automaticamente da questa proposta.

## 3. Owner: `@technical-auditor`

**Chi scrive e aggiorna il registro ADR: `@technical-auditor`.** Non un nuovo agente, non l'orchestratore, non l'agente coinvolto nella decisione.

Motivazioni:

- È l'agente con lo sguardo più ampio e cross-feature del progetto (già gestisce il Burn-up, anch'esso persistente e non legato a una singola feature) — lo scope di un ADR di progetto si allinea meglio al suo ruolo esistente che a qualunque altro agente.
- Ha già permessi Bash nel framework attuale, quindi è già l'agente a cui sono affidati compiti "amministrativi" sul repository oltre al puro giudizio tecnico.
- Scrivere un ADR è **registrare** una decisione già presa dall'utente (spesso fuori dal ciclo Gate 1→4), non **prenderla** — quindi non viola il principio Maker-Checker: il Technical Auditor resta nel suo ruolo di custode della coerenza, non diventa un Maker travestito.
- Effort alto necessario: tradurre una discussione in Contesto/Decisione/Conseguenze richiede distillare, non è copia-incolla meccanico — per questo non è compito adatto all'orchestratore, tenuto deliberatamente a effort basso e logica quasi meccanica di instradamento.

## 4. Trigger: al momento della chiusura, non a cadenza

Le decisioni architetturali di questo tipo non hanno un gate naturale a cui agganciarsi (non appartengono al ciclo di una feature). Serve un trigger nuovo, riconosciuto dall'orchestratore:

> Quando una discussione di natura consultiva sulla struttura del framework (non sul contenuto di una feature specifica) si chiude con una decisione esplicita dell'utente, l'orchestratore riconosce la chiusura e passa il testimone a `@technical-auditor` per la stesura dell'ADR, **immediatamente**, non a fine sessione o in un secondo momento.

**Motivo del "subito" e non "a cadenza":** il costo marginale di scrivere l'ADR è quasi nullo se fatto subito, perché il ragionamento (contesto, alternative valutate, motivazioni) è già stato prodotto ed è ancora fresco nel contesto della conversazione. Rimandarlo significa doverlo ricostruire più tardi, con più token spesi e rischio concreto di perdere sfumature — il tipo di costo che va contro l'obiettivo di efficienza che ha motivato l'intera famiglia di proposte di questa sessione.

**Segnali che l'orchestratore dovrebbe riconoscere come "decisione architetturale chiusa"** (indicativi, da raffinare in fase di implementazione):
- l'utente ha posto una domanda comparativa esplicita su una scelta strutturale (es. "conviene eliminare/accorpare X?", "conviene cambiare Y nel framework?")
- è stata fornita un'analisi vantaggi/svantaggi
- l'utente chiude con un esito netto ("si mantiene così", "si procede con X", "scartiamo questa idea")

Se manca uno di questi tre elementi (in particolare l'esito netto), l'orchestratore non genera un ADR — evita di produrne per discussioni ancora aperte o puramente esplorative.

## 5. Meccanica dei file: immutabilità e superseding

- Cartella: `docs/adr/` alla radice del progetto.
- Un file per decisione, mai modificato dopo la creazione. Naming: `NNNN-titolo-breve-in-kebab-case.md` (es. `0001-mantenere-tech-lead-separato.md`).
- Se una decisione viene ribaltata in futuro, **non si modifica l'ADR esistente**: si crea un nuovo ADR che dichiara esplicitamente di superare il precedente (campo `Supersedes: ADR-000X` nel frontmatter o nell'intestazione).

### Template ADR

```markdown
# ADR-NNNN: [Titolo della decisione in una riga]

**Data:** [YYYY-MM-DD]
**Stato:** Accettato | Superato da ADR-NNNN
**Decisore:** 123trading (utente) — discussione consultiva con Claude

## Contesto
[Perché questa decisione si è resa necessaria. Quali alternative erano sul tavolo.]

## Decisione
[Cosa è stato deciso, in modo netto e non ambiguo.]

## Conseguenze
[Cosa cambia. Cosa si accetta di perdere/rischiare. Eventuali trade-off espliciti.]

## Alternative considerate e scartate
[Breve elenco, con motivo dello scarto — utile per non ridiscuterle da zero in futuro.]
```

## 6. Cosa serve fare per implementare (checklist per l'AI incaricata)

1. **`CLAUDE.md`**: aggiungere la logica di riconoscimento del trigger descritto in sezione 4, e l'istruzione di invocare `@technical-auditor` in modalità "scrittura ADR" subito dopo la chiusura di una decisione architetturale consultiva.
2. **`.claude/agents/technical-auditor.md`**: aggiungere questa responsabilità (nuovo step, distinto da quelli già assegnati sul Burn-up), con il template della sezione 5 incluso o referenziato.
3. **Creare la cartella `docs/adr/`** con un `README.md` minimo che spiega la convenzione (immutabilità, superseding, naming).
4. **Retroattivo, opzionale ma consigliato**: valutare se scrivere ora, come primi ADR, le decisioni architetturali già prese in sessioni precedenti e ancora valide, per non partire con un registro vuoto che dà falsa impressione di "nessuna decisione presa finora". Candidate note, da verificare con l'utente prima di formalizzarle:
   - Mantenimento di `@tech-lead` come agente separato (non accorpato a `@solutions-architect` né a `@software-engineer`)
   - Non accorpamento dei due Checker (`@business-analyst-qa` e `@technical-auditor`)
   - Non accorpamento di `@product-manager` e `@business-analyst-qa`
   - Calibrazione modello/effort per agente (se e quando effettivamente applicata nei file)

**Prima di implementare**, l'AI incaricata dovrebbe confermare con l'utente che il criterio di trigger (sezione 4) è ancora quello desiderato, dato che è stato definito in modo indicativo e potrebbe richiedere raffinamento pratico dopo i primi utilizzi reali.

## 7. Nota di provenienza

Documento nato da una sessione di ragionamento congiunto tra l'utente (123trading) e un'istanza Claude. Si aggiunge a `regola-escalation-modello-effort.md` e `proposta-percorso-snello-routing.md`, entrambi prodotti nella stessa sessione, e al framework base (`sdd-agenti-orchestratore-v3.zip`).
