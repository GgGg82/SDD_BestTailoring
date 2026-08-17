# Analisi critica della cartella `Miglioramenti`

**Data analisi:** 2026-08-06
**Perimetro:** 10 file in `Miglioramenti/`, confrontati con `REMEDIATION-PLAN-v4.md` e `repo-bundle-v4/` presenti nello stesso repository.
**Metodo:** ogni affermazione sullo stato attuale è stata verificata leggendo i file reali di `repo-bundle-v4/` (CLAUDE.md, `.claude/agents/*`, `docs/*`, codice dell'engine), non assunta dai documenti di proposta.

---

## 1. Il problema di fondo: le proposte parlano della v3, il repository è già alla v4

Tutti e sette i documenti di proposta dichiarano come baseline `sdd-agenti-orchestratore-v3.zip`. I tre HTML sono datati 3 agosto 2026 e si presentano come "stato attuale confermato".

Ma nello stesso repository esiste `repo-bundle-v4/` (v4.0.0-beta.1, 31 luglio 2026), che ha già chiuso i 12 P0 dell'audit e ha già implementato — in forma diversa e in genere più forte — parte di ciò che le proposte chiedono.

**Conseguenza pratica:** la cartella `Miglioramenti` è oggi documentazione parzialmente falsa sullo stato del sistema. È esattamente il difetto che l'audit ha punito nell'engine (P1-22: sette documenti citati come fonte di verità che non esistevano). Prima di implementare qualunque proposta va rifatta la fotografia della baseline.

### Disallineamenti verificati

| Cosa dicono i documenti `Miglioramenti` | Cosa c'è realmente in v4 |
|---|---|
| "Ogni task attraversa lo stesso ciclo completo" (roadmap, blocco A) | `docs/SCALE-ADAPTIVE-FLOW.md`: classi Fast Track / Standard / High-Risk, 7 criteri, promozione in corsa, retrocessione vietata |
| "Nessuna calibrazione esplicita di modello scritta nei file agente" (blocco B) | I 6 file agente hanno `model:` esplicito — `opus` per Solutions Architect e Technical Auditor, `sonnet` per gli altri |
| Step 2.3 e 4.2 = `/speckit.analyze` (diagramma HTML, FMEA §9) | v4 ha rimosso `analyze` da 2.3 e 4.2 (P0-01). Resta solo a 3.2; 4.2 è verifica indipendente via lint/test |
| Collaudo funzionale = step 4.4 | In v4 è **4.5**. Anche 4.3-loop è diventato 4.4-loop e 4.3-review |
| Risk register da arricchire con owner/trigger/residual risk (FMEA §14) | Già fatto: "Risk register PMI completo" (chiude P1-05) |
| Nessun registro di decisioni architetturali (blocco C) | `docs/DESIGN-DECISIONS.md` esiste già, dichiarato "formato ADR abbreviato" |
| Gate come criteri testuali da scrivere in `CLAUDE.md` | v4 ha una state machine deterministica: `burnup gate status\|approve\|reject`, Gate Decision Record, invalidazione a valle per fingerprint |

---

## 2. Stato reale proposta per proposta

| # | Documento | Verdetto | Nota |
|---|---|---|---|
| 1 | `proposta-percorso-snello-routing.md` | **Superata** | SCALE-ADAPTIVE-FLOW fa la stessa cosa meglio: 3 classi invece di 2, criteri più operativi, promozione in corsa (che la proposta non prevedeva). **Da non buttare:** il Criterio 3 raffinato ("quante cose devono restare coerenti dopo la modifica", non "il file è importante") è più preciso della domanda 7 di v4 ("tocca più di due requisiti") e vale come chiarimento da innestare lì. |
| 2 | `proposta-sistema-memoria-progetto.md` | **Valida e intatta** | Né `AGENTS.md` né `PROJECT-STATE.md` esistono in v4. È l'unica proposta interamente non coperta. Vedi §4 per un miglioramento sostanziale reso possibile dalla v4. |
| 3 | `regola-escalation-modello-effort.md` | **Valida ma da riformulare** | Premessa errata su due punti: dice "Sonnet, effort alto" mentre nei file v4 non esiste alcun campo `effort` (il frontmatter degli agenti Claude Code espone `model`, non `effort`). La regola va riscritta su ciò che è realmente configurabile, o va verificato tecnicamente cosa si può cambiare per singola invocazione. |
| 4 | `proposta-prioritizzazione-requisiti.md` | **Valida, con un difetto tecnico grave** | Vedi §3. |
| 5 | `proposta-burnup-forecast.md` | **Valida e resa più facile dalla v4** | Il punto 2 della sua checklist ("tracciare la data di superamento Gate 2") è già risolto: il Gate Decision Record registra approvatore, data e fingerprint. Resta però debole la statistica — vedi §5. |
| 6 | `proposta-adr-progetto.md` | **Parzialmente superata** | `DESIGN-DECISIONS.md` copre le decisioni sull'engine; la proposta copre le decisioni sul processo. Possono convivere, ma serve un criterio esplicito di ripartizione, altrimenti divergono. Va scelta una sola sede o una regola netta. |
| 7 | `CHANGE_PROPOSAL_FMEA_INTEGRATION...md` | **Da ridiscutere sulla baseline v4** | Vedi §6. È l'unico documento marcato "pronto per implementazione" invece che "in stand-by", ed è quello con più conflitti. |

---

## 3. Prioritizzazione requisiti — collisione con il fingerprint

La proposta chiede il tag `essenziale/rimandabile` **inline in `spec.md`, accanto a ciascun requisito**, motivandolo con "il parser già legge quella riga".

In v4 l'evidenza di ogni requisito è legata al `requirement_fingerprint`, cioè all'hash del testo normalizzato del requisito. `normalize_text()` assorbe spaziatura, Unicode, enfasi Markdown e punteggiatura finale — **non** parole aggiuntive.

Conseguenza: se il tag finisce dentro il testo del requisito, **cambiare la priorità di un requisito ne invalida tutta l'evidenza** e lo fa retrocedere da `tested`. È il comportamento voluto (P0-06) applicato a un cambiamento che non ha nulla di normativo.

Rimedi possibili, da decidere esplicitamente:
- tag come colonna/attributo strutturale fuori dalla frase normativa;
- oppure esclusione esplicita del pattern del tag in `normalize_text()`, con test dedicato.

Secondo punto, metodologico: la proposta fa ereditare al requisito "la criticità più alta tra i rischi che lo referenziano". Ma la criticità in un risk register è probabilità × impatto, mentre per decidere cosa è essenziale conta l'**impatto**. Un requisito a bassa probabilità e impatto catastrofico risulterebbe non critico — esattamente il caso R2 di RiskGuard che la proposta cita come motivazione. L'Asse 1 va derivato dalla severità, non dall'esposizione.

Terzo, la rilevazione dei conflitti fra assi è assegnata al Technical Auditor "allo step 2.3" (sezioni 5, 7 e 8). **Quello step non esiste più**: in v4 `/speckit.analyze` ha un'unica invocazione valida, allo step 3.2, dopo `tasks.md`. Il controllo va spostato lì. La conseguenza non è solo redazionale: cade dopo il Gate 2 invece che prima, quindi un conflitto scoperto lo fa decadere anziché precederlo.

Quarto: `risk_link.py` oggi calcola solo "rischio aperto sì/no" per requisito. La derivazione della criticità è un'estensione reale, non gratuita come la proposta lascia intendere.

---

## 4. Memoria di progetto — l'occasione mancata resa possibile dalla v4

La proposta prevede `PROJECT-STATE.md` **scritto** dall'orchestratore ai Gate, e riconosce onestamente il rischio principale: un file di stato non aggiornato è peggio che assente.

La v4 offre una soluzione migliore che la proposta non poteva conoscere: `burnup gate status` è già la fonte di verità deterministica sullo stato dei gate, con invalidazione automatica a valle. E il principio architetturale della v4 è "il Markdown è una proiezione generata, mai un database".

**Raccomandazione:** `PROJECT-STATE.md` va **generato** dall'engine, non scritto da un agente. Le sezioni "feature attiva / fase / gate" diventano output di `burnup gate status`; restano scritte a mano solo "ultimo evento" e "decisioni in attesa dell'utente". Questo elimina alla radice il rischio di staleness sulla parte che conta, ed è coerente con la scelta architetturale già fatta.

`AGENTS.md` resta invece esattamente come proposto: è il pezzo tool-agnostico, non ha equivalenti in v4, e la nota "Nota su Codex CLI" in `CLAUDE.md` è ancora lì come avvertimento passivo.

---

## 5. Forecast — la statistica è il punto debole, non l'infrastruttura

La proposta parla di "fit di trend". Con 3-6 feature e pochi snapshot una regressione è rumore, e la proposta stessa lascia indefinita la soglia minima — cioè lascia aperto proprio il parametro da cui dipende se il comando è utile o dannoso.

Alternativa più onesta con pochi dati: esporre il **throughput osservato** (requisiti passati a `implemented`/`tested` per unità di tempo) con intervallo min–max storico e conteggio dei punti su cui è calcolato, invece di una data proiettata. Comunica la stessa informazione senza dare una precisione che i dati non hanno.

La Linea A (soglia Gate 2) è la più preziosa delle tre e ora è quasi gratuita grazie al Gate Decision Record.

---

## 6. FMEA — cinque conflitti con la v4

Il documento è il più rigoroso della cartella per metodo (distinzione Risk Register / FMEA / clarify, Pass A e Pass B, divieto di false traceability, severity override, non-obiettivi espliciti). Ma è calibrato sulla v3 e collide con la v4 in cinque punti.

1. **Settimo agente.** `REMEDIATION-PLAN-v4.md` §1.1 registra una decisione esplicita dell'utente: *"Nessun settimo agente"*, con P0-11 risolto allargando l'allowlist Bash del Technical Auditor. La FMEA propone `@risk-quality-analyst`. È una decisione già presa che va riaperta consapevolmente, non aggirata.
2. **`fmea.md` come database Markdown.** La FMEA propone un file tabellare scritto da un agente e riletto dallo script Burn-up (§13). La v4 ha appena stabilito il principio opposto per chiudere P0-05/06/07: canonical store come fonte di verità, Markdown generato e mai riletto. Implementare `fmea.md` così reintrodurrebbe i difetti appena chiusi.
3. **Gate come prosa.** I criteri Gate 1-4 della FMEA sono scritti in linguaggio naturale in `CLAUDE.md`. In v4 i gate sono una state machine con exit code e finding bloccanti. Un criterio che vive solo in prosa non è enforceable — è il difetto P0-10 già chiuso.
4. **Numerazione step obsoleta.** Tutti i riferimenti a 2.3, 4.2, 4.4 e a `/speckit.analyze` seguono la v3. Vanno rimappati.
5. **Tailoring duplicato.** L'AC-17 (FMEA mandatory / lite / waived) è un secondo meccanismo di classificazione parallelo alle classi di change già esistenti. Vanno unificati: Fast Track → nessuna FMEA; Standard → FMEA lite; High-Risk → FMEA completa. Una sola decisione di tailoring, presa una volta, all'apertura della feature.

### Due osservazioni di merito, indipendenti dalla v4

- **RPN è deprecato.** AIAG-VDA 2019 ha sostituito il Risk Priority Number con la tabella Action Priority proprio perché il prodotto S×O×D è aritmeticamente instabile e induce ad ancorarsi al numero. Il documento tiene entrambi e definisce solo RPN, lasciando le soglie AP tra le decisioni aperte (§21). Meglio eliminare RPN e definire la tabella AP.
- **Occurrence e Detection senza dati sono il punto fragile.** Il documento lo mitiga con il marcatore `ASSUMPTION`, che è corretto, ma il valore reale della FMEA qui viene dalla *scoperta* dei failure mode, non dai numeri. Considerare un Pass A puramente qualitativo (solo Severity + Action Priority), rinviando O e D a quando esiste evidenza reale.

### Il pezzo da estrarre subito

Il **corner-case sweep obbligatorio in `/speckit.clarify`** (§4.3 e §9 step 1.2) è l'elemento a più alto rapporto valore/costo dell'intera cartella: nessun agente nuovo, nessun artefatto nuovo, nessuna modifica all'engine, e si aggancia direttamente a ciò che la classe High-Risk già richiede ("scenari negativi espliciti"). Oggi è sepolto dentro un change proposal da 1.100 righe che ne blocca l'adozione. Va scorporato in una micro-modifica autonoma.

---

## 7. Cosa manca del tutto

- **Il costo degli agent-hop.** È il tema esplicitamente in coda nella memoria di progetto ("agent-hop token cost problem"), ed è il costo principale riconosciuto del framework. Nessuno dei sette documenti lo affronta: `proposta-sistema-memoria-progetto.md` nasce da lì (l'idea del "digest condiviso" tra agenti) ma è stata generalizzata verso la continuità cross-sessione, lasciando il problema originale orfano.
- **Stima del costo di implementazione.** La tabella di priorità della roadmap ordina per impatto e dipendenze, mai per costo. Per un framework il cui problema aperto è il costo, è la colonna mancante.
- **Migrazione.** Solo la FMEA cita una migration strategy (§21.10). Nessun documento affronta cosa succede alle feature già avviate in v3 al passaggio a v4.

---

## 8. Sequenza raccomandata

0. **Riallineare la baseline.** Aggiornare i tre HTML su v4 e marcare esplicitamente ogni proposta con la versione a cui si riferisce. Senza questo, ogni implementazione parte da una fotografia sbagliata.
1. **Corner-case sweep in `clarify`** — scorporato dalla FMEA. Costo minimo, valore immediato.
2. **`AGENTS.md` + `PROJECT-STATE.md`**, con la parte di stato *generata* da `burnup gate status`.
3. **Prioritizzazione Asse 2**, con il tag progettato fuori dal fingerprint e l'Asse 1 derivato dalla severità.
4. **Forecast**, su throughput osservato invece che regressione, partendo dalla Linea A.
5. **Sede unica per gli ADR di processo**, decidendo il rapporto con `DESIGN-DECISIONS.md`.
6. **FMEA**, riscritta sulla baseline v4: senza settimo agente, agganciata alle classi di change, con lo stato nel canonical store e i criteri Gate espressi come finding bloccanti.

La regola di escalation modello/effort resta fuori sequenza finché non è verificato cosa sia realmente configurabile per singola invocazione.
