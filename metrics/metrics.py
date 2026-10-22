"""Circuit structural metrics calculation."""

from typing import Dict
from qiskit import QuantumCircuit


def get_metrics(circuit: QuantumCircuit) -> Dict[str, int]:
    """Compute structural metrics for a quantum circuit.

    Consistently ignores barriers and measurements across all metrics.
    Barriers and measurement operations do not represent unitary gate operations,
    so excluding them ensures fair, consistent comparisons of gate complexity,
    two-qubit overhead, and critical path depth.

    Args:
        circuit: Input QuantumCircuit.

    Returns:
        dict with keys:
            - "total_gates": Total number of quantum gates (excluding barrier and measure).
            - "two_qubit_gates": Total number of two-qubit quantum gates (excluding barrier and measure).
            - "depth": Circuit depth considering only quantum gates (excluding barrier and measure).
    """
    ignored = {"barrier", "measure"}
    filtered_instructions = [
        inst for inst in circuit.data if inst.operation.name not in ignored
    ]
    total_gates = len(filtered_instructions)
    two_qubit_gates = sum(1 for inst in filtered_instructions if len(inst.qubits) == 2)
    depth = circuit.depth(
        filter_function=lambda inst: inst.operation.name not in ignored
    )

    return {
        "total_gates": total_gates,
        "two_qubit_gates": two_qubit_gates,
        "depth": depth,
    }
