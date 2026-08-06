"""Identita' immutabile di requisiti, artefatti ed evidenze.

Chiude P0-06 e P1-17 dell'audit, ed e' il meccanismo che rende impossibile il
probe piu' grave riprodotto in fase di analisi:

    FR-001 "il sistema deve autenticare l'utente"  -> tested
    testo cambiato in "cancellare tutti i dati al logout"
    tasks.md cancellato, marker rimosso dal codice
    -> la v3 riportava ancora `tested` con ZERO findings

La causa non era un bug di calcolo: era che l'evidenza veniva legata alla
*chiave* del requisito (`001-demo/FR-001`), che non cambia mai, invece che al
suo *contenuto*. Qui l'evidenza e' legata al fingerprint del contenuto, quindi
al cambio di testo decade da sola.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

# Enfasi Markdown, backtick e bullet non cambiano il significato normativo di
# un requisito: riformattare una spec non deve invalidarne l'evidenza.
_MD_NOISE_RE = re.compile(r"[*_`]+")
_WS_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[\s.;,:]+$")

FINGERPRINT_DISPLAY_LEN = 16


def normalize_text(text: str) -> str:
    """Normalizza un testo normativo per il calcolo del fingerprint.

    Deliberatamente NON abbassa il case: in un requisito la differenza tra
    "DEVE" e "dovrebbe" e' semanticamente rilevante, e in molte convenzioni
    (RFC 2119) il maiuscolo e' esattamente il portatore della normativita'.

    Assorbe invece: forma Unicode, spaziatura, enfasi Markdown, punteggiatura
    finale. Sono variazioni tipografiche che non cambiano cosa il sistema deve
    fare.
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFC", str(text))
    t = t.replace(" ", " ")
    t = _MD_NOISE_RE.sub("", t)
    t = _WS_RE.sub(" ", t)
    t = t.strip()
    t = _TRAILING_PUNCT_RE.sub("", t)
    return t


def sha256_hex(*parts: str) -> str:
    """SHA-256 su piu' componenti, con separatore non ambiguo.

    Il separatore `\\x1f` (unit separator) non puo' comparire nel testo
    normalizzato, quindi ("ab", "c") e ("a", "bc") non collidono mai.
    """
    h = hashlib.sha256()
    for i, part in enumerate(parts):
        if i:
            h.update(b"\x1f")
        h.update(str(part).encode("utf-8"))
    return h.hexdigest()


def requirement_fingerprint(
    *,
    requirement_id: str,
    text: str,
    acceptance_criteria: str = "",
    nfr_refs: list[str] | None = None,
) -> str:
    """Fingerprint del contenuto normativo di un requisito.

    Include l'ID perche' due requisiti con lo stesso testo in punti diversi
    della spec restano entita' distinte; include i criteri di accettazione e i
    riferimenti NFR perche' cambiarli cambia cosa significa "fatto".
    """
    refs = ",".join(sorted(nfr_refs or []))
    return sha256_hex(
        normalize_text(requirement_id),
        normalize_text(text),
        normalize_text(acceptance_criteria),
        refs,
    )


def artifact_fingerprint(content: str) -> str:
    """Fingerprint di un artefatto testuale (spec.md, plan.md, tasks.md).

    Normalizza i newline in modo che lo stesso file con checkout CRLF su
    Windows e LF su Linux produca lo stesso fingerprint, altrimenti i gate si
    invaliderebbero al solo cambio di sistema operativo.
    """
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    return sha256_hex(normalized)


def file_fingerprint(path) -> str:
    """Fingerprint dei byte grezzi di un file, a blocchi.

    Usato per l'evidenza dei report di test (P1-17): li' conta l'identita'
    esatta del file prodotto dal test runner, non la sua forma logica, quindi
    NON si normalizza nulla.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def short(fp: str) -> str:
    """Forma abbreviata per i report leggibili. Lo store conserva sempre l'intero."""
    return (fp or "")[:FINGERPRINT_DISPLAY_LEN]


def scope_fingerprint(requirement_keys: list[str]) -> str:
    """Fingerprint della composizione dello scope attivo.

    Chiude P1-10: la v3 decideva se creare uno snapshot confrontando i
    *conteggi*, quindi rimuovere un requisito e aggiungerne un altro nello
    stesso refresh risultava "no-change" e non lasciava traccia storica.
    Confrontando l'insieme delle chiavi, una sostituzione a parita' di numero
    e' visibile.
    """
    return sha256_hex(*sorted(set(requirement_keys)))
