"""Tassonomia degli errori ed exit code deterministici.

Chiude N-01 e P1-32 dell'audit.

La v3 usava `assert` per l'invariante di burn-up (che sparisce sotto `python -O`)
e intercettava solo due tipi di eccezione, lasciando propagare tutto il resto
come traceback grezzo con exit code 1 — indistinguibile da un errore di
configurazione. Qui ogni classe di errore ha un exit code proprio, così una
pipeline puo' decidere cosa fare senza fare parsing dello stderr.
"""
from __future__ import annotations


class ExitCode:
    """Exit code stabili. Fanno parte del contratto pubblico della CLI."""

    OK = 0
    CONFIG_ERROR = 1
    QUALITY_GATE_FAILED = 2
    ENGINE_ERROR = 3
    USAGE_ERROR = 4


class BurnupError(Exception):
    """Base di tutti gli errori dell'engine. Ogni sottoclasse dichiara un exit code."""

    exit_code = ExitCode.ENGINE_ERROR
    kind = "engine-error"

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def as_dict(self) -> dict:
        return {
            "error": self.kind,
            "message": self.message,
            "hint": self.hint,
            "exit_code": self.exit_code,
        }


class ConfigError(BurnupError):
    """File di configurazione mancante, malformato, o con valori non validi."""

    exit_code = ExitCode.CONFIG_ERROR
    kind = "config-error"


class PathConfinementError(ConfigError):
    """Un percorso configurato esce dalla radice del progetto.

    E' un ConfigError e non un errore di sicurezza a se' stante perche' la
    causa e' sempre una configurazione: l'engine non costruisce mai path da
    solo. Mantiene pero' un `kind` distinto per essere filtrabile nei log.
    """

    kind = "path-confinement-error"


class SpecsLayoutError(ConfigError):
    """Nessun layout Spec Kit riconoscibile, o piu' layout in conflitto."""

    kind = "specs-layout-error"


class StoreError(BurnupError):
    """Il canonical store e' illeggibile, corrotto, o di uno schema incompatibile."""

    kind = "store-error"


class LockError(BurnupError):
    """Un altro processo sta gia' scrivendo sul canonical store."""

    kind = "lock-error"


class InvariantError(BurnupError):
    """Un'invariante interna e' stata violata: e' sempre un bug dell'engine.

    Sostituisce l'`assert` della v3 (N-01): non viene mai rimossa
    dall'ottimizzatore e produce un exit code distinguibile.
    """

    kind = "invariant-error"


class QualityGateFailed(BurnupError):
    """Findings bloccanti presenti in modalita' --strict.

    Non e' un errore dell'engine: e' l'esito negativo di un controllo che ha
    funzionato correttamente. Exit code dedicato per permettere a una pipeline
    di distinguerlo da un crash (P0-10).
    """

    exit_code = ExitCode.QUALITY_GATE_FAILED
    kind = "quality-gate-failed"

    def __init__(self, message: str, *, blocking: list | None = None, hint: str = "") -> None:
        super().__init__(message, hint=hint)
        self.blocking = blocking or []

    def as_dict(self) -> dict:
        d = super().as_dict()
        d["blocking_findings"] = list(self.blocking)
        return d
