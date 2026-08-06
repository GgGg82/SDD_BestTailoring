# SCALE-ADAPTIVE-FLOW — Classi di change

**Versione:** 2.0 · **Stato:** normativo

Chiude P2-03 dell'audit: nella v3 ogni modifica, anche minima, attraversava l'intero processo a quattro gate. Un processo che costa più del lavoro che governa non viene seguito — viene aggirato, e a quel punto non governa più nulla.

## Il vincolo che non scala

> **I controlli P0 non si riducono mai.** Tracciabilità, evidenza fingerprinted, test obbligatori, path confinement e strict gate valgono identici in tutte le classi.

Ciò che scala è il **numero di artefatti e di revisioni**, non il rigore della misurazione. Una classe più leggera significa meno documenti da produrre, non meno verità sui numeri.

## Le tre classi

| | **Fast Track** | **Standard** | **High-Risk** |
|---|---|---|---|
| Quando | correzione di difetto, testo, configurazione, refactoring senza cambio di comportamento | tutto il resto — **default** | sicurezza, dati personali, denaro, irreversibilità, integrazioni esterne critiche, vincoli regolatori |
| Requisiti toccati | ≤ 2, nessuno nuovo | qualunque | qualunque |
| `spec.md` | modifica del requisito esistente | completa | completa + scenari negativi espliciti |
| `plan.md` | non richiesto | richiesto | richiesto + revisione architetturale indipendente |
| `risk-register.md` | non richiesto | richiesto | richiesto + contingency e rischio residuo per ogni voce |
| `checklists/` | solo requisiti | requisiti + piano | requisiti + piano + sicurezza |
| Gate | **1 e 4** | 1, 2, 3, 4 | 1, 2, 3, 4 + revisione di sicurezza prima del 4 |
| `/speckit.analyze` | opzionale | richiesto | richiesto |
| Verifica indipendente | test suite | test suite + lint + analisi statica | + security scan + revisione manuale del diff |
| Test obbligatori | **sì** | **sì** | **sì**, con scenari negativi e casi limite |
| `refresh --strict` | **sì** | **sì** | **sì**, `strict_blocks_on: [high, medium]` |
| Approvatore del Gate 4 | Tech Lead | Tech Lead | utente umano, esplicitamente |

## Come si sceglie

La classe è **dichiarata dall'Orchestratore all'inizio della feature** e registrata in `progress.md`. La scelta è motivata, non implicita.

Domande, in ordine. **Una sola risposta affermativa promuove alla classe superiore:**

1. Tocca autenticazione, autorizzazione, crittografia o segreti? → High-Risk
2. Tratta dati personali o soggetti a vincoli regolatori? → High-Risk
3. Muove denaro, o produce effetti non reversibili? → High-Risk
4. Cambia un contratto verso l'esterno (API pubblica, formato di scambio, schema dati persistito)? → High-Risk
5. Introduce requisiti nuovi? → almeno Standard
6. Cambia il comportamento osservabile dal punto di vista dell'utente? → almeno Standard
7. Tocca più di due requisiti esistenti? → almeno Standard

Nessuna affermativa → Fast Track.

**In caso di dubbio si sale, non si scende.** Il costo di una classe sovrastimata è qualche documento in più; il costo di una sottostimata è un difetto che attraversa i gate senza incontrare il controllo che lo avrebbe fermato.

## Promozione in corsa

Una feature può essere promossa in qualunque momento, mai retrocessa. Se durante l'implementazione emerge che una Fast Track tocca l'autenticazione:

1. l'Orchestratore promuove la classe e lo annota in `progress.md` con il motivo;
2. i gate saltati diventano **richiesti** e vanno approvati prima di procedere;
3. gli artefatti mancanti vanno prodotti.

La retrocessione non è ammessa: significherebbe rimuovere un controllo dopo aver visto cosa avrebbe trovato.

## Cosa resta identico in tutte le classi

- ogni task funzionale dichiara i requisiti che implementa, o si marca `[NON-REQ:]`;
- ogni requisito attivo ha almeno un test obbligatorio prima del Gate 4;
- l'evidenza è legata al fingerprint del requisito;
- `burnup refresh --strict` precede l'approvazione del Gate 4;
- ogni decisione umana è registrata con attore, motivo e revisione;
- i gate a valle decadono automaticamente quando cambia un artefatto a monte.

Se una di queste diventa negoziabile per "andare più veloci", la misurazione smette di dire la verità — e a quel punto il framework non sta più governando niente, sta solo producendo documenti.
