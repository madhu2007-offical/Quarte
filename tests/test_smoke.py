"""Smoke tests for Day 0 scaffold verification."""

from qiskit import QuantumCircuit

from benchmarks.generators import bell, ghz
from metrics.metrics import get_metrics
from optimizer.base import IdentityPass
from optimizer.equivalence import is_equivalent
from optimizer.pipeline import optimize
from simulation.noisy_sim import run_noisy


def test_identity_pass_returns_equivalent():
    """1. IdentityPass returns an equivalent circuit."""
    circuit = bell()
    pass_obj = IdentityPass()
    output = pass_obj.run(circuit)
    assert is_equivalent(circuit, output)


def test_optimize_ghz3_default_passes_equivalent():
    """2. optimize() on ghz(3) with the default passes returns equivalent == True."""
    circuit = ghz(3)
    result = optimize(circuit)
    assert result.equivalent is True
    assert is_equivalent(circuit, result.optimized_circuit)


def test_get_metrics_hand_built_circuit():
    """3. get_metrics on a tiny hand-built circuit (H, CX, H on 2 qubits) returns total_gates=3, two_qubit_gates=1, depth=3."""
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.h(0)

    metrics = get_metrics(qc)
    assert metrics["total_gates"] == 3
    assert metrics["two_qubit_gates"] == 1
    assert metrics["depth"] == 3


def test_is_equivalent_positive_and_negative():
    """4. is_equivalent returns True for identical circuits and False for a circuit with one extra X gate."""
    # Positive test: identical circuits
    qc_base = bell()
    qc_identical = bell()
    assert is_equivalent(qc_base, qc_identical) is True

    # Negative test: circuit with one extra X gate
    qc_modified = bell()
    qc_modified.x(0)
    assert is_equivalent(qc_base, qc_modified) is False


def test_run_noisy_bell_circuit():
    """5. run_noisy on a Bell circuit with measurements returns counts whose keys are subset of {"00","01","10","11"} and shots sum correctly."""
    qc = bell(measure=True)
    shots = 4096
    counts = run_noisy(qc, backend_name="FakeSherbrooke", shots=shots, seed=42)

    assert set(counts.keys()).issubset({"00", "01", "10", "11"})
    assert sum(counts.values()) == shots
