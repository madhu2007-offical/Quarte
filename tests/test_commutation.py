"""Tests for Pass 2: Commutation rules, commutation-based rewriting, and rollback."""

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter
from qiskit.converters import circuit_to_dag

from metrics.metrics import get_metrics
from optimizer.cancellation import CancellationPass
from optimizer.commutation import CommutationPass
from optimizer.commutation_rules import commutes
from optimizer.equivalence import is_equivalent


# -----------------------------------------------------------------------------
# Positive Tests for Every Commutation Rule
# -----------------------------------------------------------------------------

def test_commute_disjoint_qubits():
    """R1: Gates acting on disjoint qubit supports commute."""
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.x(1)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is True


@pytest.mark.parametrize("diag_gate", ["z", "s", "sdg", "t", "tdg"])
def test_commute_diagonal_gate_on_cx_control(diag_gate):
    """R2: Standard diagonal single-qubit gates on CX control commute."""
    qc = QuantumCircuit(2)
    getattr(qc, diag_gate)(0)
    qc.cx(0, 1)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is True


def test_commute_rz_and_p_on_cx_control():
    """R2: RZ and Phase gates on CX control commute."""
    qc = QuantumCircuit(2)
    qc.rz(0.5, 0)
    qc.p(0.3, 0)
    qc.cx(0, 1)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[2]) is True  # RZ and CX
    assert commutes(nodes[1], nodes[2]) is True  # P and CX


@pytest.mark.parametrize("x_gate", ["x", "sx", "sxdg"])
def test_commute_x_type_gate_on_cx_target(x_gate):
    """R3: X-type single-qubit gates on CX target commute."""
    qc = QuantumCircuit(2)
    getattr(qc, x_gate)(1)
    qc.cx(0, 1)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is True


def test_commute_rx_on_cx_target():
    """R3: RX gate on CX target commutes."""
    qc = QuantumCircuit(2)
    qc.rx(0.7, 1)
    qc.cx(0, 1)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is True


def test_commute_diagonal_gate_on_cz_either_qubit():
    """R4: Diagonal gates commute with CZ on control or target qubit."""
    qc = QuantumCircuit(2)
    qc.rz(0.4, 0)
    qc.t(1)
    qc.cz(0, 1)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[2]) is True  # RZ(0) and CZ(0, 1)
    assert commutes(nodes[1], nodes[2]) is True  # T(1) and CZ(0, 1)


def test_commute_two_cx_shared_control():
    """R5: Two CX gates sharing only their control qubit commute."""
    qc = QuantumCircuit(3)
    qc.cx(0, 1)
    qc.cx(0, 2)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is True


def test_commute_two_cx_shared_target():
    """R6: Two CX gates sharing only their target qubit commute."""
    qc = QuantumCircuit(3)
    qc.cx(0, 2)
    qc.cx(1, 2)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is True


def test_commute_two_diagonal_gates_same_qubit():
    """R7: Two single-qubit diagonal gates on the same qubit commute."""
    qc = QuantumCircuit(1)
    qc.rz(0.4, 0)
    qc.s(0)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is True


# -----------------------------------------------------------------------------
# Negative Tests: Cases That Must NOT Commute
# -----------------------------------------------------------------------------

def test_negative_diagonal_on_cx_target():
    """RZ or Z on CX target does NOT commute."""
    qc = QuantumCircuit(2)
    qc.rz(0.5, 1)
    qc.cx(0, 1)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is False


def test_negative_x_type_on_cx_control():
    """X or RX on CX control does NOT commute."""
    qc = QuantumCircuit(2)
    qc.x(0)
    qc.cx(0, 1)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is False


def test_negative_cx_target_is_control_of_other():
    """Addition 1: CX(0, 1) and CX(1, 2) do NOT commute."""
    qc = QuantumCircuit(3)
    qc.cx(0, 1)
    qc.cx(1, 2)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is False


def test_negative_cx_swapped_control_target():
    """Addition 1: CX(0, 1) and CX(1, 0) do NOT commute."""
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    qc.cx(1, 0)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is False


def test_negative_non_commuting_single_qubit():
    """X and Z, or H and Z on the same qubit do NOT commute."""
    qc = QuantumCircuit(1)
    qc.x(0)
    qc.z(0)
    qc.h(0)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is False  # X and Z
    assert commutes(nodes[2], nodes[1]) is False  # H and Z


def test_negative_directives_and_classical():
    """Barriers, measurements, and resets do NOT commute with anything."""
    qc = QuantumCircuit(1, 1)
    qc.h(0)
    qc.barrier(0)
    qc.measure(0, 0)
    qc.reset(0)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    h_node, barrier_node, measure_node, reset_node = nodes[0], nodes[1], nodes[2], nodes[3]

    assert commutes(h_node, barrier_node) is False
    assert commutes(h_node, measure_node) is False
    assert commutes(h_node, reset_node) is False


def test_negative_symbolic_parameters():
    """Gates with symbolic parameters do NOT commute."""
    theta = Parameter("theta")
    qc = QuantumCircuit(2)
    qc.rz(theta, 0)
    qc.cx(0, 1)
    dag = circuit_to_dag(qc)
    nodes = list(dag.topological_op_nodes())
    assert commutes(nodes[0], nodes[1]) is False


# -----------------------------------------------------------------------------
# CommutationPass Rewriting & Rollback Tests
# -----------------------------------------------------------------------------

def test_commutation_pass_reduces_circuit_pass1_cannot():
    """Pass 2 reduces a circuit that Pass 1 alone cannot.

    Circuit: RZ(a) on q0, CX(0, 1), RZ(b) on q0.
    In Pass 1, RZ(a) and RZ(b) are separated by CX, so Pass 1 achieves 0 reduction.
    Pass 2 slides RZ(a) past CX(0, 1) on its control qubit and merges with RZ(b).
    """
    qc = QuantumCircuit(2)
    qc.rz(0.4, 0)
    qc.cx(0, 1)
    qc.rz(0.6, 0)

    # Pass 1 alone cannot reduce this
    pass1_out = CancellationPass().run(qc)
    assert len(pass1_out.data) == 3

    # Pass 2 slides RZ past CX and merges
    pass2_out = CommutationPass().run(qc)
    assert len(pass2_out.data) == 2
    assert [inst.operation.name for inst in pass2_out.data] == ["cx", "rz"]
    assert np.isclose(float(pass2_out.data[1].operation.params[0]), 1.0, atol=1e-8)
    assert is_equivalent(qc, pass2_out)


def test_rollback_is_bit_for_bit_identical():
    """Addition 2: When a slide is rolled back, the circuit is bit-for-bit identical."""
    # Circuit where RZ commutes with CX on control, but has no partner to merge with downstream
    qc = QuantumCircuit(3)
    qc.rz(0.5, 0)
    qc.cx(0, 1)
    qc.h(2)  # disjoint wire

    # Extract exact original instruction sequence
    orig_seq = [
        (
            inst.operation.name,
            tuple(qc.find_bit(q).index for q in inst.qubits),
            tuple(float(p) for p in inst.operation.params),
        )
        for inst in qc.data
    ]

    # Run CommutationPass (will attempt slide, find no partner, and rollback)
    out_qc = CommutationPass().run(qc)

    out_seq = [
        (
            inst.operation.name,
            tuple(out_qc.find_bit(q).index for q in inst.qubits),
            tuple(float(p) for p in inst.operation.params),
        )
        for inst in out_qc.data
    ]

    assert out_seq == orig_seq, "Rollback failed to produce bit-for-bit identical circuit sequence!"


def test_commutation_cx_cancellation_across_shared_control():
    """Two identical CX gates separated by another CX sharing control cancel."""
    qc = QuantumCircuit(3)
    qc.cx(0, 1)
    qc.cx(0, 2)
    qc.cx(0, 1)

    # Pass 1 cannot cancel because CX(0, 2) intervenes on wire 0
    pass1_out = CancellationPass().run(qc)
    assert len(pass1_out.data) == 3

    # Pass 2 slides CX(0, 1) past CX(0, 2) and cancels
    pass2_out = CommutationPass().run(qc)
    assert len(pass2_out.data) == 1
    assert pass2_out.data[0].operation.name == "cx"
    assert tuple(pass2_out.find_bit(q).index for q in pass2_out.data[0].qubits) == (0, 2)
    assert is_equivalent(qc, pass2_out)
