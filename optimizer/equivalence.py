"""Equivalence checking between quantum circuits."""

from typing import Dict, List, Union
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator


def strip_measurements(circuit: QuantumCircuit) -> QuantumCircuit:
    """Remove final measurements and barriers from a quantum circuit.

    Args:
        circuit: Input QuantumCircuit.

    Returns:
        New QuantumCircuit with final measurements and barriers removed.
    """
    qc = circuit.copy()
    qc.remove_final_measurements(inplace=True)

    # Filter out any remaining barrier or measurement instructions
    stripped = QuantumCircuit(*qc.qregs)
    for inst in qc.data:
        if inst.operation.name not in ("barrier", "measure"):
            stripped.append(inst)
    return stripped


def is_equivalent(a: QuantumCircuit, b: QuantumCircuit, atol: float = 1e-8) -> bool:
    """Check whether two circuits are unitarily equivalent up to global phase.

    Strips final measurements and barriers, verifies qubit count consistency,
    and compares Operator(a) and Operator(b) using Operator.equiv.

    Args:
        a: First QuantumCircuit.
        b: Second QuantumCircuit.
        atol: Absolute tolerance for equivalence comparison. Defaults to 1e-8.

    Returns:
        True if equivalent up to global phase, False otherwise.

    Raises:
        ValueError: If either circuit has more than 10 qubits.
    """
    stripped_a = strip_measurements(a)
    stripped_b = strip_measurements(b)

    if stripped_a.num_qubits > 10 or stripped_b.num_qubits > 10:
        raise ValueError(
            f"Equivalence checking is limited to circuits with <= 10 qubits "
            f"(got {stripped_a.num_qubits} and {stripped_b.num_qubits})."
        )

    if stripped_a.num_qubits != stripped_b.num_qubits:
        return False

    op_a = Operator(stripped_a)
    op_b = Operator(stripped_b)
    return op_a.equiv(op_b, atol=atol)


def equivalent_up_to_permutation(
    a: QuantumCircuit,
    b: QuantumCircuit,
    perm: Union[List[int], Dict[int, int]],
    atol: float = 1e-8,
) -> bool:
    """Check whether circuit b is equivalent to circuit a up to an output qubit permutation.

    Used for validating routing passes that introduce SWAP operations or map virtual
    qubits to physical qubits according to a final permutation map.

    Args:
        a: Original logical QuantumCircuit.
        b: Routed physical QuantumCircuit.
        perm: Permutation mapping logical qubit indices to final physical qubit positions.
        atol: Tolerance for unitary equivalence. Defaults to 1e-8.

    Returns:
        True if circuit b under the given qubit permutation matches circuit a up to global phase.

    Raises:
        NotImplementedError: Stub awaiting Pass 3 routing implementation.
    """
    # TODO: Implement permutation-aware equivalence checking for Pass 3 routing
    raise NotImplementedError("equivalent_up_to_permutation is not yet implemented.")
