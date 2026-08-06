"""Generazione di identificatori stabili e non collidenti.

Chiude P1-11 e P1-16 dell'audit.

La v3 generava i Run ID con `f"RUN-{data}-{len(righe_stesso_giorno)+1:03d}"`.
Verificato: con storico `RUN-...-001` e `RUN-...-003`, il successivo era di
nuovo `003`. Il conteggio non e' una sequenza. E i Finding ID erano
riassegnati da zero ad ogni refresh, quindi lo stesso problema cambiava
identita' ad ogni giro.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from .fingerprint import sha256_hex

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # senza I, L, O, U: niente ambiguita' visiva


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _encode(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def ulid(timestamp_ms: int | None = None, randomness: bytes | None = None) -> str:
    """ULID: ordinabile lessicograficamente per tempo, univoco per costruzione.

    Scelto al posto di un contatore perche' rimuove la classe di bug alla
    radice: non serve leggere lo storico per sapere quale sia il prossimo ID,
    quindi non esiste piu' un modo di sbagliare il calcolo.
    """
    ts = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    rnd = os.urandom(10) if randomness is None else randomness
    return _encode(ts, 10) + _encode(int.from_bytes(rnd, "big"), 16)


def run_id() -> str:
    return f"RUN-{ulid()}"


def decision_id(kind: str, subject: str, decided_at: str) -> str:
    return f"DEC-{sha256_hex(kind, subject, decided_at)[:12].upper()}"


def finding_id(finding_type: str, subject: str, feature_id: str) -> str:
    """ID derivato dal contenuto: stabile finche' il problema esiste.

    Deliberatamente NON include la descrizione: se il testo del messaggio
    cambia in una versione futura dell'engine, lo stesso problema deve
    conservare lo stesso ID, altrimenti si perde l'aging e i waiver
    approvati smetterebbero di applicarsi.
    """
    return f"FND-{sha256_hex(finding_type, feature_id, subject)[:12].upper()}"


def snapshot_id(sequence: int) -> str:
    return f"SNP-{sequence:04d}"


def run_identity(
    *,
    report_hash: str,
    adapter: str,
    test_id: str,
    executed_at: str,
    result: str,
) -> str:
    """Chiave di deduplica di un'esecuzione di test.

    Chiude P0-07: la v3 non aveva alcuna chiave di ingestione, quindi lo stesso
    report JUnit veniva reimportato ad ogni refresh. Verificato: tre refresh
    producevano tre righe identiche nella Execution History.

    Include il risultato perche' un report puo' essere rigenerato con lo stesso
    nome e timestamp ma esito diverso; include l'hash del report perche' e'
    l'unica cosa che identifica davvero il file, essendo il percorso mutabile.
    """
    return sha256_hex(report_hash, adapter, test_id, executed_at, result)
