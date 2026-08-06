"""Phase gate: sequenza, criteri di ingresso, invalidazione, evidence package.

Chiude P1-26, P1-27 e P1-28 dell'audit. Nella v3 lo stato dei gate era una
checklist Markdown editata a mano: nessuna transizione controllata, nessuna
invalidazione, nessun evidence package.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from burnup.errors import ExitCode
from burnup.gates import GATE_NAMES, GateDecision, check_entry_criteria, evaluate_gates


def _plan(project: Path) -> None:
    (project / "specs" / "001-demo" / "plan.md").write_text("# Plan\n\nStack e struttura.\n", encoding="utf-8")


def _approve_through(cli, upto: int) -> None:
    actors = {1: "pm@team", 2: "arch@team", 3: "lead@team", 4: "cto@team"}
    for gate in range(1, upto + 1):
        cli("gate", "approve", "001-demo", str(gate), "--actor", actors[gate], "--reason", f"gate {gate} ok")


# --------------------------------------------------------------------------
# Sequenza e criteri di ingresso
# --------------------------------------------------------------------------

def test_gates_start_not_approved(project: Path, cli):
    cli("init")
    _, out, _ = cli("gate", "status", "001-demo", "--json")
    gates = json.loads(out)["gates"]
    assert all(g["status"] == "not-approved" for g in gates.values())


def test_cannot_skip_a_gate(project: Path, cli):
    """v3: nulla impediva di spuntare il Gate 3 senza che il Gate 2 esistesse."""
    cli("init")
    _plan(project)
    _, _, err = cli("gate", "approve", "001-demo", "3", "--actor", "lead", "--reason", "salto",
                    expect=ExitCode.QUALITY_GATE_FAILED)
    assert "Gate 2" in err and "not-approved" in err


def test_correct_sequence_is_accepted(project: Path, cli):
    cli("init")
    _plan(project)
    _approve_through(cli, 3)
    _, out, _ = cli("gate", "status", "001-demo", "--json")
    gates = json.loads(out)["gates"]
    assert [gates[str(g)]["status"] for g in (1, 2, 3)] == ["valid"] * 3
    assert gates["4"]["status"] == "not-approved"


def test_gate_requires_its_artifact(project: Path, cli):
    """Il Gate 2 mette sotto baseline `plan.md`: senza, non è approvabile."""
    cli("init")
    cli("gate", "approve", "001-demo", "1", "--actor", "pm", "--reason", "ok")
    _, _, err = cli("gate", "approve", "001-demo", "2", "--actor", "arch", "--reason", "ok",
                    expect=ExitCode.QUALITY_GATE_FAILED)
    assert "plan" in err


def test_gate_4_blocked_by_blocking_findings(project: Path, cli):
    """È il punto in cui il burn-up diventa davvero un quality gate (P0-10)."""
    cli("init")
    _plan(project)
    _approve_through(cli, 3)
    _, _, err = cli("gate", "approve", "001-demo", "4", "--actor", "cto", "--reason", "rilascio",
                    expect=ExitCode.QUALITY_GATE_FAILED)
    assert "finding bloccanti" in err


def test_gate_4_passes_once_evidence_is_complete(project: Path, cli):
    cli("init")
    _plan(project)
    for tid, rid in (("TEST-A", "001-demo/FR-001"), ("TEST-B", "001-demo/NFR-001")):
        cli("test", "define", tid, "--requirement", rid, "--definition", "d",
            "--mandatory", "--actor", "qa", "--reason", "cov")
        cli("test", "confirm-manual", tid, "--result", "pass", "--evidence", "e.pdf",
            "--actor", "qa", "--reason", "ok")
    (project / "specs" / "001-demo" / "tasks.md").write_text(
        "- [x] T001 [REQ:FR-001] auth\n- [x] T002 [REQ:NFR-001] latency\n", encoding="utf-8")
    (project / "src" / "auth.py").write_text(
        "# REQ: 001-demo/FR-001\n# REQ: 001-demo/NFR-001\ndef auth():\n    return True\n", encoding="utf-8")
    cli("refresh")
    _approve_through(cli, 4)
    _, out, _ = cli("gate", "status", "001-demo", "--json")
    assert json.loads(out)["gates"]["4"]["status"] == "valid"


# --------------------------------------------------------------------------
# Invalidazione automatica (P1-27)
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "artifact,expected_invalidated",
    [("spec", [1, 2, 3]), ("plan", [2, 3]), ("tasks", [3])],
)
def test_change_invalidates_downstream_gates(project: Path, cli, artifact, expected_invalidated):
    """v3: modificare spec.md dopo il Gate 1 non invalidava nulla."""
    cli("init")
    _plan(project)
    _approve_through(cli, 3)

    target = {
        "spec": project / "specs" / "001-demo" / "spec.md",
        "plan": project / "specs" / "001-demo" / "plan.md",
        "tasks": project / "specs" / "001-demo" / "tasks.md",
    }[artifact]
    target.write_text(target.read_text(encoding="utf-8") + "\n<!-- modifica sostanziale -->\n", encoding="utf-8")

    _, out, _ = cli("gate", "status", "001-demo", "--json")
    gates = json.loads(out)["gates"]
    for gate in (1, 2, 3):
        expected = "invalidated" if gate in expected_invalidated else "valid"
        assert gates[str(gate)]["status"] == expected, f"Gate {gate} atteso {expected}"
    for gate in expected_invalidated:
        assert artifact in gates[str(gate)]["invalidated_by"]


def test_reapproval_after_change_restores_validity(project: Path, cli):
    cli("init")
    _plan(project)
    _approve_through(cli, 1)
    spec = project / "specs" / "001-demo" / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n- **FR-002**: nuovo requisito\n", encoding="utf-8")

    _, out, _ = cli("gate", "status", "001-demo", "--json")
    assert json.loads(out)["gates"]["1"]["status"] == "invalidated"

    cli("gate", "approve", "001-demo", "1", "--actor", "pm", "--reason", "ri-approvato dopo modifica")
    _, out, _ = cli("gate", "status", "001-demo", "--json")
    assert json.loads(out)["gates"]["1"]["status"] == "valid"


def test_invalidation_is_computed_not_stored(project: Path, cli):
    """Lo stato non è mai memorizzato: si ricalcola dal confronto dei fingerprint.

    Memorizzarlo reintrodurrebbe il difetto della v3, cioè un valore che
    qualcuno deve ricordarsi di aggiornare.
    """
    cli("init")
    _plan(project)
    _approve_through(cli, 1)
    stored = (project / "requirement-burnup" / "state" / "gate-decisions.jsonl").read_text(encoding="utf-8")
    assert "invalidated" not in stored and '"status"' not in stored
    assert "artifact_fingerprints" in stored


# --------------------------------------------------------------------------
# Evidence package (P1-28)
# --------------------------------------------------------------------------

def test_decision_record_contains_evidence_package(project: Path, cli):
    """v3: il template registrava solo "approvato da" e una data."""
    cli("init")
    _, out, _ = cli("gate", "approve", "001-demo", "1", "--actor", "pm@team",
                    "--reason", "requisiti chiari e misurabili", "--json")
    d = json.loads(out)["decision"]

    assert d["decision_id"].startswith("GATE-1-001-demo-")
    assert d["approver"] == "pm@team"
    assert d["rationale"] == "requisiti chiari e misurabili"
    assert d["artifact_fingerprints"]["spec"], "la versione approvata deve essere registrata"
    assert "open_findings" in d and "waivers" in d
    assert d["burnup_counts"]["scope"] == 2
    assert d["outcome"] == "approved"


def test_conditional_approval_is_recorded_as_such(project: Path, cli):
    cli("init")
    _, out, _ = cli("gate", "approve", "001-demo", "1", "--actor", "pm", "--reason", "ok",
                    "--condition", "aggiungere metriche a NFR-001 entro il 15/08", "--json")
    d = json.loads(out)["decision"]
    assert d["outcome"] == "conditionally-approved"
    assert "aggiungere metriche" in d["conditions"][0]


def test_force_records_unmet_criteria_as_conditions(project: Path, cli):
    """`--force` non nasconde il problema: lo scrive nel record."""
    cli("init")
    _plan(project)
    _, out, _ = cli("gate", "approve", "001-demo", "3", "--actor", "lead",
                    "--reason", "deroga concordata", "--force", "--json")
    d = json.loads(out)["decision"]
    assert d["outcome"] == "conditionally-approved"
    assert any("criterio non soddisfatto" in c for c in d["conditions"])


def test_rejection_blocks_downstream(project: Path, cli):
    cli("init")
    cli("gate", "reject", "001-demo", "1", "--actor", "pm", "--reason", "requisiti troppo vaghi")
    _, out, _ = cli("gate", "status", "001-demo", "--json")
    assert json.loads(out)["gates"]["1"]["status"] == "rejected"
    _plan(project)
    cli("gate", "approve", "001-demo", "2", "--actor", "arch", "--reason", "x",
        expect=ExitCode.QUALITY_GATE_FAILED)


def test_decisions_are_append_only(project: Path, cli):
    """Una revisione produce un nuovo record: la storia non si riscrive."""
    cli("init")
    cli("gate", "approve", "001-demo", "1", "--actor", "pm", "--reason", "prima approvazione")
    cli("gate", "approve", "001-demo", "1", "--actor", "pm", "--reason", "seconda approvazione")
    rows = [l for l in (project / "requirement-burnup" / "state" / "gate-decisions.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 2
    assert "prima approvazione" in rows[0] and "seconda approvazione" in rows[1]


def test_unknown_feature_is_a_clear_error(project: Path, cli):
    cli("init")
    _, _, err = cli("gate", "status", "001-inesistente", expect=ExitCode.CONFIG_ERROR)
    assert "001-demo" in err, "l'errore deve elencare le feature disponibili"


# --------------------------------------------------------------------------
# Unità pure
# --------------------------------------------------------------------------

def test_evaluate_gates_uses_latest_decision():
    decisions = [
        GateDecision(decision_id="a", feature_id="f", gate=1, outcome="rejected",
                     approver="x", approved_at="2026-01-01T00:00:00Z", rationale="no",
                     artifact_fingerprints={"spec": "fp1"}),
        GateDecision(decision_id="b", feature_id="f", gate=1, outcome="approved",
                     approver="y", approved_at="2026-02-01T00:00:00Z", rationale="si",
                     artifact_fingerprints={"spec": "fp1"}),
    ]
    states = evaluate_gates("f", decisions, {"spec": "fp1"})
    assert states[1].status == "valid" and states[1].decision.approver == "y"


def test_evaluate_gates_ignores_other_features():
    decisions = [
        GateDecision(decision_id="a", feature_id="altra", gate=1, outcome="approved",
                     approver="x", approved_at="2026-01-01T00:00:00Z", rationale="ok",
                     artifact_fingerprints={"spec": "fp1"}),
    ]
    assert evaluate_gates("f", decisions, {"spec": "fp1"})[1].status == "not-approved"


def test_check_entry_criteria_rejects_unknown_gate():
    from burnup.errors import ConfigError
    with pytest.raises(ConfigError):
        check_entry_criteria(9, {}, {}, [])


def test_gate_names_cover_the_sequence():
    from burnup.gates import GATE_SEQUENCE
    assert set(GATE_NAMES) == set(GATE_SEQUENCE)
