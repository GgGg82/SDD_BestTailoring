# DESIGN-DECISIONS — Registro delle decisioni architetturali

**Versione:** 2.0 · Formato ADR abbreviato. Ogni decisione riporta il contesto, la scelta, e cosa si è accettato di perdere.

---

## D-001 — Canonical store separato dai report

**Contesto.** La v3 usava tre file Markdown come report e come database insieme.
**Decisione.** JSON/JSONL come fonte di verità; Markdown generato e mai riletto.
**Costo accettato.** Due rappresentazioni da tenere allineate, e il canonical store non è leggibile a occhio nudo con la stessa immediatezza.
**Alternativa scartata.** SQLite: più robusto per query e transazioni, ma i diff Git diventano opachi e la storia del progetto smette di essere ispezionabile in code review. Per un artefatto di governance la leggibilità del diff vale più della potenza di query.

---

## D-002 — Evidenza legata al fingerprint, non alla chiave

**Contesto.** Il difetto più grave della v3: un requisito riscritto da capo restava `tested`.
**Decisione.** Ogni relazione porta il `requirement_fingerprint`; l'evidenza che non combacia non è corrente.
**Costo accettato.** Una riformulazione sostanziale invalida l'evidenza e obbliga a riconfermare. È voluto: se il requisito è cambiato, ciò che era stato verificato non è più ciò che c'è scritto.
**Mitigazione.** La normalizzazione assorbe le variazioni tipografiche, così riformattare non costa nulla.

---

## D-003 — Il case non viene normalizzato nel fingerprint

**Contesto.** Normalizzare tutto ridurrebbe i falsi cambiamenti.
**Decisione.** Si normalizza spaziatura, Unicode, enfasi Markdown e punteggiatura finale, ma **non** il case.
**Motivo.** In RFC 2119 il maiuscolo è il portatore della normatività: "DEVE" e "dovrebbe" non sono la stessa frase. Trattarli come equivalenti significherebbe non accorgersi di un indebolimento di un requisito.

---

## D-004 — Nessun matching semantico, mai

**Contesto.** Un LLM saprebbe collegare task e requisiti senza marcatori espliciti.
**Decisione.** Solo corrispondenze letterali dichiarate da un umano o da un agente responsabile.
**Costo accettato.** Serve disciplina: senza `[REQ:...]` nei task e `REQ:` nei commenti, i numeri restano bassi.
**Motivo.** Un collegamento indovinato è peggio di un collegamento assente, perché nessuno lo mette in discussione. Il preset `sdd-traceability` esiste per rendere sostenibile la disciplina.

---

## D-005 — Il marcatore vale solo dentro un commento

**Contesto.** La v3 accettava `REQ:` ovunque, incluse le stringhe.
**Decisione.** Il marcatore vale se la riga è un commento o se compare dopo un delimitatore di commento.
**Costo accettato.** L'euristica sui commenti non è un parser AST: un caso limite esotico può sfuggire.
**Alternativa scartata.** Parser AST per linguaggio — corretto ma richiede un adapter per ogni linguaggio, e il framework deve restare neutro rispetto allo stack.

---

## D-006 — I confini di token li impone l'engine

**Contesto.** `XFR-001Y` veniva collegato a FR-001.
**Decisione.** L'utente configura il pattern dell'ID; l'engine ci avvolge i confini.
**Motivo.** È un vincolo di correttezza, non una preferenza. Lasciarlo alla regex dell'utente significa che prima o poi qualcuno lo dimenticherà, e il difetto tornerà silenzioso.

---

## D-007 — ULID al posto dei contatori

**Contesto.** La v3 generava i Run ID contando le righe dello stesso giorno: con storico `001, 003` rigenerava `003`.
**Decisione.** ULID — ordinabile per tempo, univoco per costruzione.
**Motivo.** Non serve leggere lo storico per generare un ID, quindi la classe di bug sparisce alla radice invece di essere corretta.
**Costo accettato.** ID lunghi e poco memorabili. Gli snapshot restano numerati progressivamente perché lì la leggibilità serve davvero.

---

## D-008 — Finding con ID derivato dal contenuto

**Contesto.** Nella v3 i Finding ID erano riassegnati da zero ad ogni refresh.
**Decisione.** `FND-{hash(tipo, feature, subject)}`, che non include la descrizione.
**Motivo.** Escludere la descrizione fa sì che riformulare un messaggio in una versione futura non cambi l'identità del problema — altrimenti si perderebbe l'aging e i waiver approvati smetterebbero di applicarsi.

---

## D-009 — I waiver scadono

**Contesto.** Un'eccezione permanente è indistinguibile da una regola che non esiste.
**Decisione.** `--expires` opzionale; alla scadenza il finding torna `open` da solo, con nota.
**Costo accettato.** Un waiver senza scadenza resta possibile. La CLI lo segnala, ma non lo impedisce: ci sono eccezioni legittimamente permanenti.

---

## D-010 — Lo stato dei gate è calcolato, non memorizzato

**Contesto.** Nella v3 lo stato viveva in una checklist Markdown editata a mano.
**Decisione.** Si memorizza solo la decisione, con i fingerprint degli artefatti approvati. Lo stato è il confronto con quelli correnti.
**Motivo.** Un valore memorizzato è un valore che qualcuno deve ricordarsi di aggiornare, ed è esattamente il difetto che si vuole eliminare.

---

## D-011 — L'allowlist Bash dell'Auditor è più larga che in v3

**Contesto.** L'audit chiedeva un settimo agente Test Architect.
**Decisione.** Allargare l'allowlist dell'Auditor esistente a lint, analisi statica, security e test runner.
**Motivo.** L'Auditor ha già Bash e non ha `Write`/`Edit`. Un Checker che non può eseguire nulla può solo leggere i report del Maker: la separazione resta nominale. Un settimo agente otterrebbe lo stesso risultato con più superficie da mantenere.
**Costo accettato.** La restrizione è comportamentale. Un `PreToolUse` hook con allowlist dei comandi è il complemento naturale, fuori dallo scope dei file base.

---

## D-012 — Il framework è neutro; il contesto sta nella constitution

**Contesto.** La v3 aveva dominio e tecnologie cuciti dentro i prompt degli agenti.
**Decisione.** Zero riferimenti a progetti, domini o stack. Il contesto specifico vive in `.specify/memory/constitution.md`.
**Motivo.** Un framework riusabile su più progetti non può portarsi dietro le assunzioni del primo. La constitution è già il posto previsto da Spec Kit per queste informazioni, ed è per-progetto per costruzione.
