# Regola di non-convergenza — diagnosi ed escalation su decisione dell'utente

**ID proposta:** B
**Framework di riferimento:** 4.0.0-rc.3
**Stato:** ✅ **ATTUATA in 4.0.0** — `CLAUDE.md`, sezione *Quando un ciclo non converge*
**Data:** 2026-08-18 · **Rev:** 2
**Sostituisce:** la stesura v3 «Escalation spot di modello/effort per Software Engineer», la cui premessa tecnica è stata verificata e in parte smentita.

---

## Il problema

Un Maker produce, un Checker rifiuta, il Maker riprova, il Checker rifiuta di nuovo per lo stesso motivo. Il ciclo non converge.

Oggi il framework non dice nulla su questa situazione. L'Orchestratore, in assenza di regola, fa l'unica cosa che sembra sensata: rimanda indietro un'altra volta. Il costo cresce in modo silenzioso — token, tempo, e soprattutto la fiducia che il processo stia progredendo mentre sta girando a vuoto.

**Il difetto peggiore non è lo spreco: è che nessuno si accorge che il ciclo è fermo.** Ogni singolo giro sembra un tentativo legittimo. Solo guardandoli insieme si vede che sono lo stesso tentativo ripetuto.

---

## Che cosa è stato verificato, e che cosa è cambiato rispetto alla stesura precedente

La stesura v3 poggiava su due fatti tecnici. Verificati sulla documentazione ufficiale di Claude Code e sul frontmatter reale dei sei agenti, uno regge e uno no.

**Regge: l'override del modello per singola invocazione esiste.** L'ordine di risoluzione è: variabile d'ambiente `CLAUDE_CODE_SUBAGENT_MODEL` → parametro `model` per-invocazione → `model` nel frontmatter dell'agente → modello della conversazione principale. Il file dell'agente non va toccato, e la calibrazione permanente resta quella che è.

**Non regge: l'`effort` non esiste come impostazione per-subagente.** La documentazione è esplicita — i subagent ereditano la configurazione di *extended thinking* della conversazione principale, e **non esiste alcuna impostazione di thinking per singolo subagent**. Non è un campo dimenticato nel frontmatter: non esiste il concetto.

> **Conseguenza sulla regola.** «Modello ed effort» non sono due leve dello stesso attore. Il modello lo può cambiare l'Orchestratore, per invocazione. Il thinking lo può cambiare **solo l'utente**, sulla propria sessione, e vale per tutti i subagent finché resta così. Una regola che promette entrambe come un gesto solo promette qualcosa che il sistema non sa fare.

**Due modi di fallire in silenzio, che la regola deve gestire:**

1. **La variabile d'ambiente ha la precedenza sul parametro.** Se `CLAUDE_CODE_SUBAGENT_MODEL` è impostata, il modello richiesto per invocazione viene ignorato. L'escalation non avviene, e nulla lo dichiara a chi l'ha chiesta.
2. **L'allowlist `availableModels` può sostituire il modello.** In sessione interattiva Claude Code mostra un avviso con il modello richiesto e quello effettivamente usato — ma è un avviso, non un errore, e in un flusso automatizzato passa inosservato.

**Dipendenze di versione da dichiarare:** il parametro per-invocazione sopravvive al resume del subagent solo da `v2.1.211`; da `v2.1.196` cambia il comportamento di `inherit` per la variabile d'ambiente; da `v2.1.222` cambia la sostituzione per alias di famiglia bloccati. Una regola che non le cita si comporta diversamente su installazioni diverse.

---

## Sei correzioni alla regola, indipendenti dalla versione

### 1 · L'identità della causa non è un giudizio, è un identificatore

La stesura v3 faceva scattare il trigger su «due rigetti consecutivi sulla **stessa causa di fondo**», lasciando all'Orchestratore stabilire se due cause coincidano. Ma l'Orchestratore è precisamente l'attore la cui capacità di giudizio la regola vuole supplire: fondare il trigger sul suo giudizio lo rende inaffidabile proprio quando serve.

Il framework offre già un ancoraggio deterministico. La decisione `D-008` definisce i finding con **ID derivato dal contenuto** — `FND-{hash(tipo, feature, subject)}` — deliberatamente **escludendo la descrizione**, perché riformulare un messaggio non deve cambiare l'identità del problema.

| Da dove arriva il rigetto | Identità della causa |
|---|---|
| `@technical-auditor`, con finding registrato | il **finding ID**: stesso ID = stessa causa, senza interpretazione |
| `@business-analyst-qa`, o rigetto senza finding | l'**ID del requisito o del task** su cui il rigetto insiste |
| Nessuno dei due è stabile | l'Orchestratore **dichiara che non può stabilire l'identità** e non fa scattare il trigger |

L'ultima riga conta quanto le altre: una regola che scatta su un'identità inventata è peggio di una che non scatta.

### 2 · Vale per ogni coppia Maker–Checker, non solo per il Software Engineer

La restrizione a `@software-engineer` veniva dal contesto della v3, dove il caso d'uso era la scrittura di codice MQL5. Ma il fenomeno è di processo, non di dominio: un ciclo `@product-manager` ↔ `@business-analyst-qa` che non converge allo step 1.2 è lo stesso identico problema, e blocca il Gate 1 esattamente come l'altro blocca il Gate 4.

### 3 · Si escala una volta sola

Se dopo l'escalation il ciclo fallisce ancora sulla stessa causa, **la regola si ferma e non propone una seconda escalation.**

Il terzo fallimento consecutivo non è un'informazione sul modello: è un'informazione su ciò che gli è stato chiesto. Un requisito ambiguo, un piano che non regge, o un criterio di accettazione impossibile non diventano soddisfacibili con un modello più capace. Continuare a spendere è la risposta sbagliata a una diagnosi corretta.

A quel punto l'Orchestratore riporta all'utente che il problema è **a monte** e propone di tornare all'artefatto che lo genera — non di riprovare.

### 4 · Il contatore vive in `progress.md`, non nella sessione

Un contatore che esiste solo nella memoria di lavoro dell'Orchestratore si azzera alla chiusura della sessione. In un processo che dura giorni, la regola non scatterebbe mai: ogni ripresa ricomincerebbe da zero, e i cicli a vuoto attraverserebbero le sessioni senza mai sommarsi.

Il conteggio va annotato in `progress.md`, con la causa a cui si riferisce, perché sopravviva alla sessione.

### 5 · L'escalation è una decisione, e le decisioni si registrano

Il framework prescrive che *«ogni decisione umana è registrata con attore, motivo e revisione»*. Un'escalation è una decisione di spesa presa dall'utente: va annotata in `progress.md` con chi l'ha autorizzata, su quale causa, e con quale esito.

Senza registrazione non è possibile la sola domanda che dà valore alla regola a posteriori: **quando l'escalation ha funzionato davvero?** Se la risposta fosse «quasi mai», la regola andrebbe ritirata, non rifinita.

### 6 · Le ipotesi sono due, non una

È la correzione che cambia la natura della regola. Due rigetti sulla stessa causa ammettono due letture:

- **il Maker non ce la fa** — allora un modello più capace può aiutare;
- **il Checker sta chiedendo qualcosa di sbagliato, impossibile o fuori scope** — allora l'escalation peggiora le cose: si paga di più per soddisfare una richiesta che non andava soddisfatta, e la si soddisfa meglio.

L'Orchestratore non può stabilire quale delle due sia vera — è esattamente il tipo di giudizio che il framework riserva all'utente. Deve quindi **presentarle entrambe**, non solo la prima.

Da qui il cambio di nome: non è una regola di escalation, è una **regola di non-convergenza**. L'escalation è una delle risposte possibili, non la conclusione automatica.

---

## La regola, in forma implementabile

### Trigger

Il **secondo rigetto consecutivo** dello stesso Checker sulla **stessa causa**, dove l'identità della causa è stabilita secondo la tabella del punto 1. Se la causa cambia, il contatore si azzera: due bug diversi in sequenza non sono un ciclo che non converge.

### Che cosa fa l'Orchestratore

1. **Si ferma.** Non rilancia il Maker con la stessa configurazione. Un terzo tentativo identico è, per definizione, lo stesso tentativo.
2. **Annota in `progress.md`** il conteggio e la causa, perché sopravviva alla sessione.
3. **Presenta all'utente le due ipotesi**, dichiarando quale gli sembra più probabile **e perché** — senza nascondersi dietro una scelta neutra.
4. **Propone le opzioni**, senza sceglierne una:

| Opzione | Chi la esegue | Quando ha senso |
|---|---|---|
| Rilancio con modello superiore, **solo per quella invocazione** | Orchestratore | Il Maker sembra non farcela, e il compito è chiaro |
| Aumento del thinking | **Utente**, sulla propria sessione | Come sopra, ma il limite sembra di ragionamento più che di capacità |
| Revisione del rigetto del Checker | Utente, con il Checker | Il rilievo sembra sbagliato, impossibile o fuori scope |
| Ritorno all'artefatto a monte | Orchestratore, verso il Maker competente | La causa è un'ambiguità di `spec.md` o `plan.md`, non un errore di esecuzione |

5. **Se l'utente autorizza l'escalation**, l'Orchestratore invoca il subagent con il parametro `model` per quella sola chiamata, e **verifica che sia stata applicata**: se il modello effettivo differisce da quello richiesto — per variabile d'ambiente o per allowlist — lo dichiara invece di procedere come se nulla fosse.
6. **Registra l'esito** in `progress.md`: escalation autorizzata da chi, su quale causa, con quale risultato.

### Che cosa la regola non fa

- Non cambia mai il `model` nel frontmatter di un agente: la calibrazione permanente resta quella che è.
- Non escala due volte sulla stessa causa.
- Non decide la spesa al posto dell'utente.
- Non tocca alcun controllo P0: nessun gate diventa approvabile per effetto di un'escalation.

---

## Rischi

**La regola non scatta perché nessuno tiene il conto.** È il modo più probabile in cui muore: il conteggio in `progress.md` va aggiornato ogni volta, e chi lo dimentica non se ne accorge. Nessuna mitigazione tecnica è possibile con gli strumenti attuali; resta una disciplina, e va detto invece che fingere il contrario.

**L'escalation diventa il riflesso.** Se ogni non-convergenza si chiude aumentando il modello, la regola smette di essere una diagnosi e diventa un modo per non guardare la spec. Il tetto del punto 3 esiste per questo, ma è una barriera al terzo giro, non al primo.

**Il costo diventa invisibile.** La registrazione in `progress.md` serve anche a rendere sommabile una spesa che altrimenti si disperde in decisioni singole, ciascuna difendibile.

---

## Punti aperti

| # | Punto | Nota |
|---|---|---|
| B1 | Quale modello per l'escalation | `opus` è il candidato ovvio, ma due dei sei agenti ci girano già: per loro l'escalation non ha una destinazione, e va detto cosa succede |
| B2 | Verifica dell'applicazione | Claude Code mostra un avviso in sessione interattiva, ma l'Orchestratore non ha un modo programmatico di leggere il modello effettivo. La verifica resta osservativa |
| B3 | Registrazione nel canonical store | Oggi la decisione vive solo in `progress.md`, che è una vista. Un comando `burnup` la renderebbe una decisione di prima classe, ma è un'estensione dell'engine e non è richiesta per adottare la regola |

---

## Impatto

- **Ampiezza:** `CLAUDE.md` (nuova regola di orchestrazione), `progress-template.md` (dove si annota il contatore), `docs/RACI.md` (chi decide).
- **Profondità:** aggiunge una regola di processo. Non tocca agenti, artefatti, gate né engine.
- **Controlli P0:** nessun impatto.
- **Rischio:** basso in sé; il rischio vero è che non venga applicata.

---

## Fonti

- [Create custom subagents — Claude Code Docs](https://code.claude.com/docs/en/sub-agents)
- [Model configuration — Claude Code Docs](https://code.claude.com/docs/en/model-config)
