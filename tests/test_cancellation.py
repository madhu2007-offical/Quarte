"""Tests for CancellationPass (Pass 1: Gate cancellation and rotation merging)."""

import numpy as np
import pytest
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter

from optimizer.cancellation import CancellationPass
from optimizer.equivalence import is_equivalent


# -----------------------------------------------------------------------------
# Rule 1a: Inverse Gate Pair Cancellation Tests
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("gate_name", ["h", "x", "y", "z"])
def test_cancel_single_qubit_self_inverse(gate_name):
    """Adjacent identical self-inverse gates (H, X, Y, Z) must cancel to identity."""
    qc = QuantumCircuit(1)
    getattr(qc, gate_name)(0)
    getattr(qc, gate_name)(0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 0
    assert is_equivalent(qc, opt)


def test_cancel_cx_cx():
    """Adjacent identical CX gates on identical control and target must cancel."""
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    qc.cx(0, 1)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 0
    assert is_equivalent(qc, opt)


def test_cancel_cz_cz():
    """Adjacent CZ gates must cancel regardless of control/target argument ordering."""
    qc = QuantumCircuit(2)
    qc.cz(0, 1)
    qc.cz(1, 0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 0
    assert is_equivalent(qc, opt)


def test_cancel_swap_swap():
    """Adjacent SWAP gates must cancel regardless of qubit argument ordering."""
    qc = QuantumCircuit(2)
    qc.swap(0, 1)
    qc.swap(1, 0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 0
    assert is_equivalent(qc, opt)


@pytest.mark.parametrize(
    "first_gate,second_gate",
    [
        ("s", "sdg"),
        ("sdg", "s"),
        ("t", "tdg"),
        ("tdg", "t"),
        ("sx", "sxdg"),
        ("sxdg", "sx"),
    ],
)
def test_cancel_adjoint_pairs(first_gate, second_gate):
    """Adjacent adjoint pairs (S-Sdg, Sdg-S, T-Tdg, Tdg-T, SX-SXdg, SXdg-SX) must cancel to identity."""
    qc = QuantumCircuit(1)
    getattr(qc, first_gate)(0)
    getattr(qc, second_gate)(0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 0
    assert is_equivalent(qc, opt)


def test_merge_sx_sx_to_x():
    """Adjacent SX gates on the same qubit must merge to an X gate."""
    qc = QuantumCircuit(1)
    qc.sx(0)
    qc.sx(0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 1
    assert opt.data[0].operation.name == "x"
    assert is_equivalent(qc, opt)


# -----------------------------------------------------------------------------
# Rule 1b: Rotation Merging and Identity Elimination Tests
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "gate_name,theta1,theta2,expected",
    [
        ("rz", 0.4, 0.6, 1.0),
        ("rx", 0.2, 0.3, 0.5),
        ("ry", 0.5, 0.7, 1.2),
        ("p", 0.1, 0.4, 0.5),
    ],
)
def test_merge_rotations_same_axis(gate_name, theta1, theta2, expected):
    """Adjacent rotations on the same axis must merge by summing angles."""
    qc = QuantumCircuit(1)
    getattr(qc, gate_name)(theta1, 0)
    getattr(qc, gate_name)(theta2, 0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 1
    assert opt.data[0].operation.name == gate_name
    assert np.isclose(float(opt.data[0].operation.params[0]), expected, atol=1e-8)
    assert is_equivalent(qc, opt)


def test_merge_rotation_cancels_to_identity():
    """Merging rotations summing to 0 mod 2*pi must remove both gates."""
    qc = QuantumCircuit(1)
    qc.rz(0.7, 0)
    qc.rz(-0.7, 0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 0
    assert is_equivalent(qc, opt)


def test_standalone_zero_rotation_eliminated():
    """Standalone rotations with angles congruent to 0 mod 2*pi must be eliminated."""
    qc = QuantumCircuit(1)
    qc.rz(0.0, 0)
    qc.rx(2 * np.pi, 0)
    qc.h(0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 1
    assert opt.data[0].operation.name == "h"
    assert is_equivalent(qc, opt)


# -----------------------------------------------------------------------------
# Multi-Pass Chain Cases
# -----------------------------------------------------------------------------

def test_chain_h_x_x_h_cancels_to_empty():
    """Cascading cancellations: H X X H -> H H -> empty."""
    qc = QuantumCircuit(1)
    qc.h(0)
    qc.x(0)
    qc.x(0)
    qc.h(0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 0
    assert is_equivalent(qc, opt)


def test_cascading_merges_and_cancellations():
    """Cascading rotation cancellation exposing outer Hadamard cancellation."""
    qc = QuantumCircuit(1)
    qc.h(0)
    qc.rz(0.3, 0)
    qc.rz(-0.3, 0)
    qc.h(0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 0
    assert is_equivalent(qc, opt)


# -----------------------------------------------------------------------------
# Safety Rules: Cases That Must NOT Be Reduced
# -----------------------------------------------------------------------------

def test_safety_cx_reversed_not_cancelled():
    """CX(0, 1) followed by CX(1, 0) are not inverses and must NOT cancel."""
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    qc.cx(1, 0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 2
    assert is_equivalent(qc, opt)


def test_safety_barrier_prevents_cancellation():
    """Barriers must prevent gate cancellation across them."""
    qc = QuantumCircuit(1)
    qc.h(0)
    qc.barrier(0)
    qc.h(0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 3
    assert [inst.operation.name for inst in opt.data] == ["h", "barrier", "h"]


def test_safety_measure_prevents_cancellation():
    """Measurements must prevent gate cancellation across them."""
    qc = QuantumCircuit(1, 1)
    qc.h(0)
    qc.measure(0, 0)
    qc.h(0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 3
    assert [inst.operation.name for inst in opt.data] == ["h", "measure", "h"]


def test_safety_reset_prevents_cancellation():
    """Reset operations must prevent gate cancellation across them."""
    qc = QuantumCircuit(1)
    qc.h(0)
    qc.reset(0)
    qc.h(0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 3
    assert [inst.operation.name for inst in opt.data] == ["h", "reset", "h"]


def test_safety_interleaved_qubit_prevents_cx_cancellation():
    """An intervening operation on one of the wires must prevent two CX gates from cancelling."""
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    qc.h(0)  # touches wire 0, so CX gates are not adjacent
    qc.cx(0, 1)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 3
    assert is_equivalent(qc, opt)


def test_safety_different_rotation_axes_do_not_merge():
    """Rotations along different axes (e.g. RZ and RX) must NOT merge."""
    qc = QuantumCircuit(1)
    qc.rz(0.5, 0)
    qc.rx(0.5, 0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 2
    assert [inst.operation.name for inst in opt.data] == ["rz", "rx"]
    assert is_equivalent(qc, opt)


def test_safety_symbolic_parameter_not_merged():
    """Gates with symbolic Parameter angles must be skipped and NOT merged."""
    theta = Parameter("theta")
    qc = QuantumCircuit(1)
    qc.rz(theta, 0)
    qc.rz(0.5, 0)

    opt = CancellationPass().run(qc)
    assert len(opt.data) == 2
    assert opt.data[0].operation.name == "rz"
    assert opt.data[1].operation.name == "rz"
