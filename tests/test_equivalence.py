"""Tests for circuit equivalence checking."""

import numpy as np
import pytest
from qiskit import QuantumCircuit

from benchmarks.generators import bell, ghz
from optimizer.equivalence import (
    equivalent_up_to_permutation,
    is_equivalent,
    strip_measurements,
)


def test_identical_circuits_pass():
    """Identical circuits must evaluate as equivalent."""
    qc1 = bell()
    qc2 = bell()
    assert is_equivalent(qc1, qc2) is True


def test_circuit_plus_extra_x_fails():
    """Adding an extra non-identity gate must cause equivalence to return False."""
    qc1 = bell()
    qc2 = bell()
    qc2.x(0)
    assert is_equivalent(qc1, qc2) is False


def test_global_phase_only_difference_passes():
    """Circuits differing solely by a global phase must evaluate as equivalent."""
    qc1 = QuantumCircuit(2)
    qc1.h(0)
    qc1.cx(0, 1)

    qc2 = QuantumCircuit(2)
    qc2.h(0)
    qc2.cx(0, 1)
    qc2.global_phase = np.pi / 3

    assert is_equivalent(qc1, qc2) is True


def test_different_qubit_counts_fail():
    """Circuits with differing numbers of qubits must return False without crashing."""
    qc1 = QuantumCircuit(2)
    qc1.h(0)
    qc2 = QuantumCircuit(3)
    qc2.h(0)

    assert is_equivalent(qc1, qc2) is False


def test_measurements_and_barriers_ignored():
    """Final measurements and barriers must be stripped so pure unitaries are compared."""
    qc1 = QuantumCircuit(2)
    qc1.h(0)
    qc1.cx(0, 1)

    qc2 = QuantumCircuit(2, 2)
    qc2.h(0)
    qc2.barrier()
    qc2.cx(0, 1)
    qc2.barrier()
    qc2.measure([0, 1], [0, 1])

    assert is_equivalent(qc1, qc2) is True


def test_num_qubits_exceeding_ten_raises_value_error():
    """Checking equivalence for circuits with > 10 qubits must raise ValueError."""
    qc1 = QuantumCircuit(11)
    qc2 = QuantumCircuit(11)

    with pytest.raises(ValueError, match="Equivalence checking is limited to circuits with <= 10 qubits"):
        is_equivalent(qc1, qc2)


def test_strip_measurements():
    """strip_measurements must remove final measurements and barriers."""
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.barrier()
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])

    stripped = strip_measurements(qc)
    op_names = [inst.operation.name for inst in stripped.data]
    assert "barrier" not in op_names
    assert "measure" not in op_names
    assert op_names == ["h", "cx"]


def test_equivalent_up_to_permutation_stub():
    """Stub function equivalent_up_to_permutation raises NotImplementedError."""
    qc1 = QuantumCircuit(2)
    qc2 = QuantumCircuit(2)
    with pytest.raises(NotImplementedError):
        equivalent_up_to_permutation(qc1, qc2, perm=[1, 0])
