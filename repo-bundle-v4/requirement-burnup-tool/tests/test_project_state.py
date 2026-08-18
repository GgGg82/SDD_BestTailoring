"""PROJECT-STATE.md e la derivazione della non-convergenza.

Il punto che questi test proteggono non e' la formattazione del Markdown: e' che
il conteggio dei rigetti consecutivi sia **derivato** e non tenuto a mano. Un
contatore che qualcuno deve ricordarsi di incrementare non fa scattare nessuna
regola, e nessuno se ne accorge — e' il difetto che questa funzione esiste per
chiudere.
"""

from burnup.gates import GateDecision
from burnup.projectstate import SOGLIA_NON_CONVERGENZA, render, streak_non_convergenza


def _dec(gate, esito, quando, findings, feature="001-f", chi="tizio", motivo="perche'"):
    return GateDecision(
        decision_id=f"D{quando}",
        feature_id=feature,
        gate=gate,
        outcome=esito,
        approver=chi,
        approved_at=quando,
        rationale=motivo,
        open_findings=list(findings),
    )


class TestStreak:
    def test_nessun_rigetto_nessuna_streak(self):
        d = [_dec(1, "approved", "2026-01-01", ["FND-a"])]
        assert streak_non_convergenza(d) == []

    def test_un_solo_rigetto_non_basta(self):
        """La soglia e' due: un rigetto isolato e' un rigetto, non un ciclo."""
        d = [_dec(1, "rejected", "2026-01-01", ["FND-a"])]
        assert streak_non_convergenza(d) == []

    def test_due_rigetti_sulla_stessa_causa_fanno_scattare(self):
        d = [
            _dec(1, "rejected", "2026-01-01", ["FND-a"]),
            _dec(1, "rejected", "2026-01-02", ["FND-a"]),
        ]
        out = streak_non_convergenza(d)
        assert len(out) == 1
        assert out[0]["finding_id"] == "FND-a"
        assert out[0]["rigetti_consecutivi"] == 2
        assert out[0]["ultimo_rigetto"] == "2026-01-02"

    def test_cause_diverse_non_sommano(self):
        """Due bug diversi in sequenza non sono un ciclo che non converge."""
        d = [
            _dec(1, "rejected", "2026-01-01", ["FND-a"]),
            _dec(1, "rejected", "2026-01-02", ["FND-b"]),
        ]
        assert streak_non_convergenza(d) == []

    def test_causa_condivisa_solo_dagli_ultimi_due(self):
        """L'intersezione sull'intera coda sarebbe vuota, ma la regola deve
        scattare lo stesso: si conta per causa, non per serie."""
        d = [
            _dec(1, "rejected", "2026-01-01", ["FND-a"]),
            _dec(1, "rejected", "2026-01-02", ["FND-a", "FND-b"]),
            _dec(1, "rejected", "2026-01-03", ["FND-b"]),
        ]
        out = {r["finding_id"]: r["rigetti_consecutivi"] for r in streak_non_convergenza(d)}
        assert out == {"FND-b": 2}

    def test_una_approvazione_interrompe_la_serie(self):
        """Il contatore si azzera: la coda considera solo i rigetti finali."""
        d = [
            _dec(1, "rejected", "2026-01-01", ["FND-a"]),
            _dec(1, "approved", "2026-01-02", []),
            _dec(1, "rejected", "2026-01-03", ["FND-a"]),
        ]
        assert streak_non_convergenza(d) == []

    def test_gate_diversi_sono_conteggi_diversi(self):
        d = [
            _dec(1, "rejected", "2026-01-01", ["FND-a"]),
            _dec(4, "rejected", "2026-01-02", ["FND-a"]),
        ]
        assert streak_non_convergenza(d) == []

    def test_feature_diverse_sono_conteggi_diversi(self):
        d = [
            _dec(1, "rejected", "2026-01-01", ["FND-a"], feature="001-a"),
            _dec(1, "rejected", "2026-01-02", ["FND-a"], feature="002-b"),
        ]
        assert streak_non_convergenza(d) == []

    def test_ordine_di_inserimento_irrilevante(self):
        """I record arrivano dallo store senza garanzia d'ordine: la funzione
        ordina per approved_at prima di contare."""
        d = [
            _dec(1, "rejected", "2026-01-03", ["FND-a"]),
            _dec(1, "approved", "2026-01-01", []),
            _dec(1, "rejected", "2026-01-02", ["FND-a"]),
        ]
        out = streak_non_convergenza(d)
        assert len(out) == 1 and out[0]["rigetti_consecutivi"] == 2

    def test_tre_rigetti_contano_tre(self):
        d = [_dec(1, "rejected", f"2026-01-0{i}", ["FND-a"]) for i in (1, 2, 3)]
        assert streak_non_convergenza(d)[0]["rigetti_consecutivi"] == 3

    def test_open_findings_vuoto_non_esplode(self):
        d = [
            _dec(1, "rejected", "2026-01-01", []),
            _dec(1, "rejected", "2026-01-02", []),
        ]
        assert streak_non_convergenza(d) == []

    def test_soglia_configurabile(self):
        d = [_dec(1, "rejected", "2026-01-01", ["FND-a"])]
        assert streak_non_convergenza(d, soglia=1)[0]["rigetti_consecutivi"] == 1
        assert SOGLIA_NON_CONVERGENZA == 2


class TestRender:
    def _render(self, **kw):
        base = dict(
            generato_il="2026-08-18T10:00:00Z",
            versione_engine="test",
            features=[],
            findings_aperti=[],
            streaks=[],
            freschezza="fresh",
        )
        base.update(kw)
        return render(**base)

    def test_dichiara_di_essere_generato(self):
        """Se non lo dichiara, qualcuno lo modifichera' a mano e perdera' il lavoro."""
        out = self._render()
        assert "Non modificarlo a mano" in out
        assert "burnup project-state" in out

    def test_senza_streak_lo_dice_esplicitamente(self):
        out = self._render()
        assert "non e' scattata" in out

    def test_con_streak_rimanda_alla_regola(self):
        out = self._render(streaks=[{
            "feature_id": "001-f", "gate": 4, "finding_id": "FND-a",
            "rigetti_consecutivi": 2, "ultimo_rigetto": "2026-01-02",
            "ultimo_attore": "tizio", "ultima_motivazione": "no",
        }])
        assert "regola di non-convergenza e' scattata" in out
        assert "FND-a" in out
        assert "CLAUDE.md" in out

    def test_dichiara_il_proprio_limite(self):
        """I cicli intra-fase non sono coperti: tacerlo darebbe falsa sicurezza."""
        assert "burnup gate reject" in self._render()

    def test_feature_senza_dati(self):
        assert "Nessuna feature nel canonical store." in self._render()

    def test_feature_con_dati(self):
        out = self._render(features=[{
            "feature_id": "001-f", "change_class": "standard",
            "gates": {1: "valid", 4: "not-approved"},
            "scope": 7, "tested": 3, "progress_path": "specs/001-f/progress.md",
        }])
        assert "001-f" in out and "1:valid" in out and "4:not-approved" in out
