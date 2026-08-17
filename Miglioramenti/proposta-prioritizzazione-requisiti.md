# Proposta: Prioritizzazione dei requisiti a doppio asse

> ## ⚠️ VALIDA — ma con due correzioni obbligatorie prima di implementare
>
> **Baseline del documento:** v3 · **Baseline reale del repository:** v4.0.0-beta.1
> **Verificato il:** 2026-08-06 su `burnup/fingerprint.py` e `burnup/risk_link.py`.
>
> **1. Il tag non può stare dentro la frase normativa del requisito.** La sezione 3, Asse 2, prescrive il tag `essenziale/rimandabile` *inline in `spec.md`, accanto a ciascun requisito*. In v4 l'evidenza di ogni requisito è legata al `requirement_fingerprint`, cioè all'hash del testo normalizzato; `normalize_text()` assorbe spaziatura, Unicode, enfasi Markdown e punteggiatura finale — **non** parole aggiuntive. Se il tag finisce nel testo del requisito, **cambiare la priorità ne invalida tutta l'evidenza** e lo fa retrocedere da `tested`. Va progettato come colonna/attributo strutturale fuori dalla frase normativa, oppure escluso esplicitamente in `normalize_text()` con test dedicato.
>
> **2. L'Asse 1 va derivato dalla severità, non dalla criticità.** La sezione 3 fa ereditare al requisito "la criticità più alta tra i rischi che lo referenziano". Ma la criticità in un risk register è probabilità × impatto, mentre per decidere cosa è essenziale conta l'**impatto**. Un requisito a bassa probabilità e impatto catastrofico risulterebbe non critico — cioè esattamente il caso R2 di RiskGuard che la sezione 5 cita come motivazione della proposta.
>
> **3. Lo step 2.3 non esiste più.** Le sezioni 5, 7 e 8 assegnano la rilevazione dei conflitti fra assi al `@technical-auditor` "allo step 2.3, che già esegue `/speckit.analyze`". In v4 quello step è stato rimosso (P0-01): `analyze` ha un'unica invocazione valida, allo **step 3.2**, dopo `tasks.md`. Il controllo va spostato lì. Il ragionamento della proposta regge — è ancora lo stesso agente, lo stesso comando e la stessa natura di verifica — ma cade dopo il Gate 2 invece che prima, quindi un conflitto scoperto lì fa decadere il Gate 2 anziché precederlo.
>
> **Nota di costo:** `risk_link.py` oggi calcola solo "rischio aperto sì/no" per requisito. La derivazione della criticità è un'estensione reale dell'engine, non la lettura gratuita che la sezione 3 lascia intendere.
>
> Dettaglio in `ANALISI-CROSS-CHECK-MIGLIORAMENTI.md`.

---

**Stato originario dichiarato: PROPOSTA — non ancora implementata nel framework.**

**Destinatario di questo documento:** un'istanza AI (Claude Code o altro agente) incaricata in futuro di valutare e/o implementare questa modifica al framework di governance SDD a 6 agenti. Documento autosufficiente, non richiede la cronologia della conversazione che lo ha prodotto.

**Documento collegato:** `proposta-burnup-forecast.md` — questa proposta ne è il complemento naturale. Senza prioritizzazione, le stime di forecast rispondono solo a "quando finisce tutto"; con essa rispondono anche a "quando è pronto ciò che conta". Le due proposte sono implementabili separatamente, ma il valore combinato è superiore alla somma.

---

## 1. Contesto e problema

Il framework attuale tratta ogni requisito con lo stesso peso: nessun meccanismo distingue ciò che è indispensabile da ciò che è rimandabile. Questo ha due conseguenze:

- Le stime di completamento (vedi `proposta-burnup-forecast.md`) proiettano solo il 100% del totale — una data spesso meno utile di "quando è pronto il nucleo indispensabile".
- Il routing del Percorso Snello (vedi `proposta-percorso-snello-routing.md`) non dispone di un segnale di priorità, che sarebbe naturale come criterio aggiuntivo.

## 2. Perché NON si chiama MVP — decisione terminologica deliberata

L'idea è nata dalla domanda "manca il concetto di MVP?". La risposta, dopo analisi, è: **serve il bisogno sottostante, non l'etichetta MVP**. Motivi, da non riaprire in fase di implementazione:

- **MVP è indissolubile dal Lean Startup**, cioè da un ciclo build-measure-learn con iterazione rapida e feedback dall'uso reale. Questo framework non ha nessuno di quegli elementi strutturali: il Maker-Checker è deliberatamente lento e accurato, e non esiste uno step formalizzato di "rilascia, osserva, rientra con quello che hai imparato". Adottare l'etichetta importerebbe un paradigma estraneo — stessa ragione per cui il termine "backlog" è già stato scartato altrove a favore di "portfolio di feature".
- **Genera aspettative errate:** "MVP" suggerisce "si può spedire imperfetto". Qui è falso: anche un requisito essenziale attraversa comunque l'intero ciclo Gate 1→4 con lo stesso rigore. Si guadagna perimetro ridotto, non velocità o minor rigore — sono cose diverse e vanno chiamate diversamente.
- **Rischio specifico del dominio:** in un EA di trading, "minimo vitale" applicato con leggerezza può significare "casi limite non gestiti" — vedi rischio R2 di RiskGuard (SL a distanza zero → divisione per zero). Escludere dal perimetro essenziale un requisito che è in realtà un rischio è pericoloso.

**È stato valutato e parzialmente scartato anche MoSCoW** (Must/Should/Could/Won't): il vantaggio è reale ma il metodo è notoriamente soggetto a inflazione delle categorie (tutto diventa Must). Nel metodo originario DSDM esisteva un tetto esplicito sullo sforzo dei Must proprio per questo. Si è scelto di conservare il tetto ma ridurre le categorie a due (vedi Asse 2), perché il valore decisionale di MoSCoW sta quasi interamente nella prima distinzione, e ogni categoria in più aumenta l'indecisione senza aumentare il potere decisionale.

## 3. Il meccanismo: due assi indipendenti

I due assi rispondono a domande diverse e **non vanno collassati in uno solo**: collassarli perde informazione, ed è proprio la loro divergenza a produrre il segnale più utile (vedi sezione 5).

### Asse 1 — Criticità derivata dal rischio ("cosa non può sbagliare")

**Non dichiarata da nessun agente: calcolata.** La fonte è `risk-register.md`, già esistente, già di proprietà di `@business-analyst-qa` allo step 2.2-risk, e già dotato della colonna "Requisiti collegati".

- **Regola:** un requisito eredita la criticità più alta tra i rischi che lo referenziano. Un requisito non collegato ad alcun rischio è semplicemente "non critico" — il che indica assenza di rischio, **non** basso valore.
- **Quando:** al Gate 2, contestualmente alla scrittura/aggiornamento del risk register. Nessun nuovo momento nel ciclo.
- **Dove vive il dato:** in nessun artefatto nuovo. È una derivazione che lo script del Burn-up calcola leggendo `risk-register.md`. Zero duplicazione, zero sincronizzazione da mantenere.

**Perché questo asse è forte:** non è inflazionabile come una dichiarazione soggettiva — non si può marcare tutto ad alto rischio senza che diventi visibilmente insostenibile nel registro, che è già passato sotto contraddittorio Maker-Checker.

### Asse 2 — Priorità dichiarativa ("cosa non può mancare")

Due sole categorie: **essenziale** / **rimandabile**.

- **Chi:** `@product-manager` — è una decisione di prodotto pura, non tecnica.
- **Quando:** durante lo step 1.1 (`/speckit.specify`), contestualmente alla scrittura dei requisiti, **prima della chiusura di Gate 1**. Il timing non è arbitrario: mettendolo prima di Gate 1, `@business-analyst-qa` lo verifica nella checklist requisiti dello step 1.3 che già esegue. La classificazione entra così sotto Maker-Checker senza inventare un nuovo controllo.
- **Dove:** **inline in `spec.md`**, accanto a ciascun requisito, non in un file separato. Motivo: lo script del Burn-up già fa parsing di `spec.md` per estrarre i requisiti, quindi legge il tag nello stesso passaggio. Un file separato creerebbe due fonti che possono divergere — fragilità evitata ovunque altrove nel framework.

**Tetto contro l'inflazione:** `@business-analyst-qa` verifica in checklist che gli "essenziali" non superino una soglia indicativa (~60% dei requisiti della feature). Se superata, **non blocca automaticamente**, ma solleva un rilievo da giustificare. Il Checker non decide cosa è essenziale — verifica che la classificazione sia stata fatta con discriminazione reale e non a timbro.

## 4. Regola per i cicli di ritorno (caso emerso in stress test)

Un requisito può nascere **dopo** Gate 1, in un ciclo di ritorno dal Gate 2 — è già successo nella simulazione RiskGuard con REQ-007 (comportamento di arrotondamento emerso solo in fase di piano, aggiunto a `spec.md` dal PM tornando indietro).

**Regola:** quando `@product-manager` aggiunge o modifica un requisito in un ciclo di ritorno, assegna il tag di Asse 2 contestualmente, e la ri-verifica di `@business-analyst-qa` sul delta **include il ricalcolo del tetto** sull'intera feature, non solo sul nuovo requisito. Questo si aggancia a un comportamento già esistente (nella simulazione la checklist è stata rieseguita sul delta, 7/7), non ne introduce uno nuovo.

## 5. Conflitti tra i due assi — il vero valore aggiunto

**Chi li rileva:** `@technical-auditor` allo step 2.3, che già esegue `/speckit.analyze` su coerenza spec↔plan↔constitution. Aggiungere "coerenza tra priorità dichiarata e criticità derivata" è nella stessa natura del controllo esistente, non un ruolo nuovo.

### Caso A — "rimandabile" ma collegato a rischio Alto → SEGNALAZIONE

Il caso che da solo giustifica il doppio asse. Esempio reale dallo stress test su RiskGuard: REQ-002 (gestione SL a distanza zero) potrebbe essere marcato "rimandabile" dal PM con un ragionamento plausibile ("è un caso limite"), ma è collegato a RR2 (Media/Alto, divisione per zero). Senza l'asse rischio, un caso limite pericoloso sarebbe scivolato fuori dal perimetro essenziale per un giudizio soggettivo sbagliato.

**Non si risolve automaticamente.** Va portato all'utente umano: o il requisito non va rimandato, o il rischio va rivisto perché sovrastimato. Entrambe le uscite sono legittime; la decisione è dell'utente.

### Caso B — "essenziale" senza rischi collegati → NESSUNA SEGNALAZIONE

Perfettamente normale. Esempio: REQ-001 di RiskGuard sarebbe essenziale anche senza rischi, perché il calcolo del lotto *è* la funzione del prodotto, non un rischio. L'assenza di rischio non è un'anomalia.

### Altri casi validati in stress test
- REQ-001 (essenziale + RR1 Alta/Alto): doppia conferma, caso pulito, nessuna azione.
- REQ-004 (supporto CFD indici, rimandabile, solo RR3 Media/Medio): nessun conflitto, il sistema correttamente non ha nulla da dire.

## 6. Valore concreto atteso (tre benefici verificabili)

1. **Stime di forecast azionabili:** il comando `burnup-forecast` può filtrare sul solo sottoinsieme essenziale, producendo "quando è pronto ciò che conta" oltre a "quando finisce tutto".
2. **Segnale aggiuntivo per il Percorso Snello:** un requisito rimandabile, non critico, che non tocca altri componenti è candidato quasi ideale al percorso leggero — la priorità diventa un quarto criterio di routing, non solo metadato descrittivo.
3. **Copertura dei rischi misurabile nel tempo:** oggi `risk-register.md` è una foto statica; correlato al Burn-up diventa una serie storica ("quanti requisiti ad alta criticità sono già tested").

## 7. Distribuzione delle responsabilità

| Cosa | Chi | Quando | Artefatto |
|---|---|---|---|
| Tag essenziale/rimandabile | `@product-manager` | Step 1.1, pre-Gate 1 | Inline in `spec.md` |
| Verifica tetto e discriminazione | `@business-analyst-qa` | Step 1.3 (checklist requisiti) | Nessuno nuovo |
| Criticità da rischio | derivata, nessun agente | Gate 2 | Calcolata da `risk-register.md` |
| Rilevazione conflitti tra assi | `@technical-auditor` | Step 2.3 (`/speckit.analyze`) | Output esistente |
| Uso nelle stime | script Burn-up | comando `forecast` | Output esistente |

**Nessun agente nuovo, nessun artefatto nuovo, un solo campo aggiunto a `spec.md`.**

## 8. Cosa serve fare per implementare (checklist per l'AI incaricata)

1. **`.specify/templates/`**: aggiungere il campo priorità al template di `spec.md`, con sintassi parsabile dallo script (formato esatto da concordare con il parser esistente).
2. **`.claude/agents/product-manager.md`**: aggiungere l'assegnazione del tag allo step 1.1 e la regola sui cicli di ritorno (sezione 4).
3. **`.claude/agents/business-analyst-qa.md`**: aggiungere la verifica del tetto alla checklist requisiti dello step 1.3, incluso il ricalcolo sul delta nei cicli di ritorno.
4. **`.claude/agents/technical-auditor.md`**: aggiungere la rilevazione conflitti tra assi allo step 2.3.
5. **`requirement-burnup-tool/`**: estendere il parser di `spec.md` per leggere il tag; aggiungere la derivazione della criticità da `risk-register.md`; esporre entrambi nei filtri del comando `forecast`.
6. **Soglia del tetto:** il valore ~60% è indicativo, da validare empiricamente sui primi progetti reali, non da fissare rigidamente in fase di prima implementazione.

**Prima di implementare**, confermare con l'utente che le due proposte collegate (`proposta-burnup-forecast.md` e `proposta-percorso-snello-routing.md`) sono ancora valide, dato che il valore di questa dipende in parte da esse.

## 9. Nota di provenienza

Documento nato da una sessione di ragionamento congiunto tra l'utente (123trading) e un'istanza Claude, incluso uno stress test su casi concreti del progetto di esempio RiskGuard che ha portato all'aggiunta della regola sui cicli di ritorno (sezione 4). Si aggiunge a `regola-escalation-modello-effort.md`, `proposta-percorso-snello-routing.md`, `proposta-adr-progetto.md` e `proposta-burnup-forecast.md`.
