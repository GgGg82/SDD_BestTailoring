# Miglioramenti — indice

**Aggiornato:** 2026-08-18 · **Framework:** 4.0.1

Le proposte sono ordinate per **stato reale verificato sul bundle**, non per stato dichiarato dal documento. È una distinzione che è servita: fino a questa riorganizzazione cinque proposte dichiaravano «non implementata» pur essendo attuate, e tre schemi HTML mostravano una roadmap superata dai fatti.

```
Miglioramenti/
├── attuate/    → implementate nel framework. Conservate come storia del ragionamento
├── aperte/     → da fare, o da riscrivere prima di farle
└── obsolete/   → analisi datate e diagrammi anteriori alla 4.0.0
```

---

## Attuate

| Proposta | Dove vive ora | Versione |
|---|---|---|
| `proposta-percorso-snello-routing.md` | `docs/SCALE-ADAPTIVE-FLOW.md` — tre classi, sette criteri, promozione senza retrocessione | pre-4.0.0, criterio di coerenza in **4.0.0** |
| `proposta-sistema-memoria-progetto.md` | `AGENTS.md` + `PROJECT-STATE.md` **generato** da `burnup project-state` | **4.0.0** |
| `regola-escalation-modello-effort.md` | `CLAUDE.md`, *Quando un ciclo non converge* | **4.0.0** |
| `proposta-brainstorming-fase-meno-uno.md` | step `-1.0`, template di sessione, righe nella tabella delle classi | **4.0.0** |
| `proposta-visibilita-step-agente.md` | `docs/OUTPUT-ANNOTATION.md` + i sei prompt agente | **4.0.1** |

**Senza documento proprio**, perché estratti da altri:

- **Corner-case sweep** nello step 1.2 — dodici categorie modulate per classe. Estratto dal change proposal FMEA, che resta non implementato: era il suo pezzo migliore, sepolto sotto 1.100 righe che ne bloccavano l'adozione. → **4.0.0**
- **Criterio di coerenza multi-punto** nella domanda 7 delle classi — sopravvissuto alla proposta sul percorso snello. → **4.0.0**

---

## Aperte

| Proposta | Cosa manca prima di poterla fare |
|---|---|
| `proposta-adr-progetto.md` | Una **decisione di sede**: `docs/adr/` a file immutabili, oppure una sezione di `DESIGN-DECISIONS.md`. Quest'ultimo esiste già in formato ADR abbreviato (`D-001…D-011`) ma documenta l'**engine**, non il **processo** — che è ciò che la proposta vuole catturare. Due sedi senza criterio di ripartizione divergono |
| `proposta-prioritizzazione-requisiti.md` | Tre correzioni obbligatorie: il tag di priorità **fuori** dalla frase normativa del requisito (dentro, invaliderebbe tutta l'evidenza a ogni cambio di priorità); l'Asse 1 derivato dalla **severità** e non dalla criticità; il controllo dei conflitti spostato allo step **3.2**, perché il 2.3 non esiste più |
| `proposta-burnup-forecast.md` | Un cambio di metodo: **throughput osservato** con intervallo storico, invece di un fit di trend che su pochi punti è rumore. La data di superamento del Gate 2, che la proposta indicava come lavoro da fare, è già disponibile nei Gate Decision Record |
| `CHANGE_PROPOSAL_FMEA_INTEGRATION_SDD_FRAMEWORK.md` | **Riscrittura sulla baseline 4.0.x.** Cinque conflitti: settimo agente (decisione già chiusa in senso contrario), `fmea.md` come database Markdown (contraddice il canonical store), criteri Gate in prosa anziché enforceable, numerazione step della v3, e un secondo meccanismo di tailoring parallelo alle classi di change. Più due osservazioni di merito: RPN è deprecato da AIAG-VDA 2019 a favore della tabella Action Priority, e Occurrence/Detection senza dati sono il punto fragile |

---

## Cosa manca del tutto — nessun documento lo copre

Rilevato dall'analisi cross-check e ancora vero:

- **Il costo degli agent-hop.** È il costo principale riconosciuto del framework. `proposta-sistema-memoria-progetto.md` nasceva da lì — l'idea di un digest condiviso fra agenti — ma è stata generalizzata verso la continuità cross-sessione, lasciando il problema originale orfano. Oggi è attuata, e il problema resta scoperto.
- **La colonna del costo di implementazione.** Le prioritizzazioni ordinano per impatto e dipendenze, mai per costo. Per un framework il cui problema aperto è il costo, è la colonna mancante.
- **La migrazione delle feature v3 → v4.** Solo la FMEA la cita. Serve soltanto se esistono feature v3 ancora aperte.

---

## Obsolete

`ANALISI-CROSS-CHECK-MIGLIORAMENTI.md` e `CLASSIFICA-MIGLIORAMENTI.md` sono l'analisi del 2026-08-06 sulla baseline `4.0.0-beta.1`. Il loro **metodo** regge — è da lì che vengono le correzioni applicate alle proposte — ma i loro **stati** sono superati: dicono 🟡 e 🔴 di cose ora fatte.

I tre HTML sono anteriori alla 4.0.0 e non riflettono né lo step `-1.0`, né la memoria di progetto, né la convenzione di annotazione. Il punto 0 della sequenza raccomandata da quell'analisi era proprio *«aggiornare i tre HTML, senza questo ogni implementazione parte da una fotografia sbagliata»*. Non sono stati aggiornati: sono stati **spostati qui**, perché uno schema sbagliato è peggio di uno assente.

> La presentazione corrente e aggiornata è `repo-bundle-v4/sdd-workflow-v4.html`, dentro il bundle.
