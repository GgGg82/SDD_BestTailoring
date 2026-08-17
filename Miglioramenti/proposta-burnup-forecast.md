# Proposta: Stime di completamento (forecast) per il Requirement Burn-up

> ## ✅ VALIDA — resa più facile dalla v4, con una correzione di metodo
>
> **Baseline del documento:** v3 · **Baseline reale del repository:** v4.0.0-beta.1
> **Verificato il:** 2026-08-06 su `burnup/gates.py` e `burnup/cli.py`.
>
> **Il punto 2 della checklist (sezione 5) è già risolto.** La v4 registra un **Gate Decision Record** a ogni approvazione, con decision ID, approvatore, data e fingerprint degli artefatti. La data di superamento del Gate 2 per feature — che la proposta indicava come lavoro da fare per la Linea A — è quindi già disponibile.
>
> **Correzione di metodo raccomandata.** La proposta parla di "fit di trend". Con poche feature e pochi snapshot una regressione è rumore, e la sezione 3 lascia indefinita proprio la soglia minima da cui dipende se il comando è utile o dannoso. Alternativa più onesta: esporre il **throughput osservato** (requisiti passati a `implemented`/`tested` per unità di tempo) con intervallo min–max storico e numero di punti su cui è calcolato, invece di una data proiettata. Comunica la stessa informazione senza promettere una precisione che i dati non hanno.
>
> Il nome del comando va allineato alla CLI v4: `burnup forecast`, non `python .../cli.py forecast`.
>
> Dettaglio in `ANALISI-CROSS-CHECK-MIGLIORAMENTI.md`.

---

**Stato originario dichiarato: PROPOSTA — non ancora implementata nel framework. In stand-by su decisione esplicita dell'utente riguardo a priorità/tempistica di implementazione.**

**Destinatario di questo documento:** un'istanza AI (Claude Code o altro agente) incaricata in futuro di valutare e/o implementare questa modifica all'estensione Requirement Burn-up già esistente nel framework di governance SDD a 6 agenti. Documento autosufficiente, non richiede la cronologia della conversazione che lo ha prodotto.

---

## 1. Contesto e problema che questa proposta risolve

L'estensione Requirement Burn-up, così com'è oggi, fotografa correttamente **lo stato attuale** (quanti requisiti sono `defined`, `implemented`, `tested`), calcolato via script Python deterministico su snapshot presi a ogni cambiamento reale (tipicamente ad ogni chiusura di Gate 4).

Quello che manca è la componente di **proiezione**: un burn-up chart, nella sua accezione classica (metodologie agili in generale, non specifica a questo framework), è pensato anche per rispondere a "quando finisce", non solo "a che punto siamo". Oggi questa componente non esiste: il dashboard mostra conteggi, non tendenze nel tempo.

**Nota su una proposta scartata in fase di analisi:** era stata inizialmente valutata l'idea di segnalare nel refresh automatico i requisiti fermi da troppi cicli consecutivi in stato `implemented` (per intercettare test dimenticati). È stata **declassata a idea minore, non prioritaria**: il dato che rileverebbe è già visibile a chi consulta il dashboard con normale regolarità dopo ogni Gate 4, quindi il beneficio incrementale è basso rispetto al costo di implementazione. Non è oggetto di questo documento.

## 2. Le tre linee di stima — non equivalenti tra loro

Punto centrale della proposta: "fine del progetto" non è una domanda sola, sono **tre domande diverse**, che rispondono a bisogni diversi e vanno calcolate separatamente. Tutte e tre sono calcolabili dallo storico degli snapshot già esistente (nessuna nuova raccolta dati richiesta), applicando un fit di trend sulle serie temporali già presenti.

### Linea A — Stima "pronto per implementare" (soglia: **Gate 2**)

Risponde a: *quando finiamo di documentare/pianificare abbastanza da poter iniziare a scrivere codice su tutte le feature del progetto?*

**Punto tecnico importante, chiarito in fase di analisi:** questa linea **non** si basa sullo stato `defined` del requisito (che indica solo superamento di Gate 1, cioè che il requisito è scritto e tracciato in `spec.md`). Un requisito `defined` non è ancora pronto per l'implementazione: manca che il piano lo indirizzi, che sia scomposto in task, e che **Gate 2** sia superato (l'analisi di coerenza spec↔plan↔constitution del Technical Auditor).

Quindi: un requisito è "pronto per implementare" solo se appartiene a una feature la cui `plan.md`/`tasks.md` ha già superato Gate 2 — non basta che sia scritto in una spec.

**Calcolo:** per ciascuna delle feature del progetto, registrare la data di superamento di Gate 2. Il conteggio "requisiti pronti" a un dato momento è la somma dei requisiti appartenenti alle feature che hanno già superato quella soglia. Proiettare il trend di questa somma nel tempo per stimare quando copre il totale dei requisiti del progetto.

**Terminologia:** l'insieme delle feature pianificate del progetto va chiamato **"portfolio di feature"** o **"insieme delle feature pianificate"**, non "backlog" — quest'ultimo termine implica un paradigma Agile (Scrum/Kanban) con ri-prioritizzazione continua e iterazioni, che non corrisponde al modello di questo framework, dove ogni feature attraversa un ciclo Gate 1→4 strutturato e sequenziale al proprio interno.

### Linea B — Stima completamento implementazione (soglia: `implemented`)

Risponde a: *quando tutti i requisiti risultano implementati?* È la linea più vicina alla definizione classica di burn-up forecast: dato il ritmo storico con cui i requisiti passano a `implemented`, proietta quando la copertura arriva al 100%. È la più stabile da calcolare delle tre.

### Linea C — Stima completamento test/done (soglia: `tested`)

Risponde a: *quando il progetto è davvero finito e sicuro da usare, non solo scritto?* Tipicamente la linea più lenta delle tre, perché il test ha un ritardo fisiologico rispetto all'implementazione (visto concretamente nella simulazione RiskGuard: 6/6 `implemented` ma solo 4/6 `tested` allo stesso snapshot).

## 3. Cautela comune a tutte e tre le linee

Ogni proiezione va presentata come **stima probabilistica dinamica**, mai come promessa o traguardo fisso, per due motivi distinti:

- **Affidabilità statistica.** Con pochi punti storici (2-3 snapshot, tipico di un progetto piccolo appena iniziato), un fit di trend è rumoroso e può oscillare parecchio da un refresh all'altro. Serve una soglia minima di snapshot sotto la quale il comando dichiara esplicitamente "dati insufficienti per una stima affidabile" invece di restituire comunque un numero.
- **Scope non fisso.** Il denominatore stesso (numero totale di requisiti) può crescere nel tempo se emergono requisiti impliciti non previsti all'inizio — è già successo nella simulazione RiskGuard con REQ-007, scoperto solo in fase di piano. Una proiezione che ignora questo rischia di creare un falso senso di sicurezza sul processo, analogo al rischio di prodotto R4 già identificato per RiskGuard, qui applicato al processo di sviluppo invece che al prodotto finale.

## 4. Comando opzionale, non incluso nel refresh automatico

**Decisione di design:** le tre stime vanno esposte tramite un comando distinto ed esplicito (es. `burnup-forecast`), **non** calcolate automaticamente a ogni `burnup-refresh` (quello agganciato a ogni chiusura di Gate 4).

**Motivo — non è il costo di calcolo.** Va chiarito esplicitamente: il costo computazionale di un fit di trend su dati già presenti è trascurabile, lo script è già deterministico e gira su Python, non su un modello. Non è un problema di token o di performance.

**Motivo reale — separare due domande diverse.** Il refresh automatico risponde a "dove siamo adesso" — è l'output che gli agenti (in particolare Technical Auditor) consultano di continuo nel flusso ordinario. La proiezione risponde a "quando finiamo" — una domanda che interessa l'utente in momenti specifici (fine sessione, checkpoint, reporting), non ad ogni singolo Gate 4. Includerla sempre appesantirebbe l'output più consultato con un dato utile solo occasionalmente, e rischierebbe di mostrare proiezioni instabili (vedi sezione 3) proprio nei momenti in cui i dati storici non bastano ancora a sostenerle.

## 5. Cosa serve fare per implementare (checklist per l'AI incaricata)

1. **Verificare l'infrastruttura esistente** in `requirement-burnup-tool/`: confermare che lo storico degli snapshot (già presente per il principio "snapshot solo su cambiamento reale") sia sufficiente per un fit di trend senza modifiche strutturali al formato di storage.
2. **Aggiungere il tracciamento della data di superamento Gate 2 per feature**, se non già presente in questa forma aggregata — necessario per la Linea A.
3. **Implementare il nuovo comando** (es. `python requirement-burnup-tool/engine/cli.py forecast`), separato da `refresh`/`status`/`init`, che calcola e restituisce le tre linee A/B/C.
4. **Soglia minima di snapshot** sotto la quale il comando avvisa esplicitamente invece di restituire una proiezione — valore esatto da definire empiricamente, non fissato in questa proposta.
5. **`.claude/agents/technical-auditor.md`**: documentare il nuovo comando tra gli usi consentiti di Bash per questo agente (già ne ha due: init e refresh; questo sarebbe un terzo, on-demand, sullo stesso modello di `burnup-status`).
6. **Verificare se serve rollup a livello di intero progetto** (oltre le singole feature) nella struttura di output esistente in `requirement-burnup/` — la Linea A in particolare richiede una vista cross-feature.

## 6. Nota di provenienza

Documento nato da una sessione di ragionamento congiunto tra l'utente (123trading) e un'istanza Claude, come evoluzione di un'idea inizialmente più debole (segnalazione di requisiti fermi in `implemented`) poi sostituita da questa proposta di valore più alto. Si aggiunge a `regola-escalation-modello-effort.md`, `proposta-percorso-snello-routing.md` e `proposta-adr-progetto.md`, tutti prodotti nella stessa sessione, e al framework base (`sdd-agenti-orchestratore-v3.zip`).
