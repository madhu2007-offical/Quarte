"""Tests for circuit structural metrics calculation."""

from qiskit import QuantumCircuit
from metrics.metrics import get_metrics


def test_get_metrics_hand_built_manual_counts():
    """Verify metrics on a hand-built circuit against exact manual counts.

    Circuit layout:
        q0: ---[H]---[X]---[barrier]---[measure]
        q1: ---------[CX]--[barrier]---[measure]
                     |
        q0: ---------[CX]--
    Manual counts:
        - Total gates: 3 (H, X, CX)
        - Two-qubit gates: 1 (CX)
        - Depth: 3 (Layer 1: H on q0; Layer 2: X on q0; Layer 3: CX on q0, q1)
        - Barriers and measurements are ignored.
    """
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.x(0)
    qc.cx(0, 1)
    qc.barrier()
    qc.measure([0, 1], [0, 1])

    m = get_metrics(qc)
    assert m["total_gates"] == 3
    assert m["two_qubit_gates"] == 1
    assert m["depth"] == 3


def test_get_metrics_single_qubit_only():
    """Verify metrics on purely 1-qubit circuits."""
    qc = QuantumCircuit(1)
    qc.x(0)
    qc.y(0)
    qc.z(0)
    qc.barrier()

    m = get_metrics(qc)
    assert m["total_gates"] == 3
    assert m["two_qubit_gates"] == 0
    assert m["depth"] == 3


def test_get_metrics_empty_circuit():
    """Empty circuit must yield 0 for all metrics."""
    qc = QuantumCircuit(3)
    m = get_metrics(qc)
    assert m["total_gates"] == 0
    assert m["two_qubit_gates"] == 0
    assert m["depth"] == 0


def test_get_metrics_ignores_intermediate_and_final_barriers():
    """Interleaved barriers and measurements must not affect depth or gate count."""
    qc1 = QuantumCircuit(2)
    qc1.h(0)
    qc1.cx(0, 1)

    qc2 = QuantumCircuit(2, 2)
    qc2.barrier()
    qc2.h(0)
    qc2.barrier()
    qc2.cx(0, 1)
    qc2.barrier()
    qc2.measure([0, 1], [0, 1])

    m1 = get_metrics(qc1)
    m2 = get_metrics(qc2)

    assert m1 == m2
