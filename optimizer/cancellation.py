"""Pass 1: Gate cancellation and rotation merging."""

from qiskit import QuantumCircuit

from optimizer.base import OptimizationPass


class CancellationPass(OptimizationPass):
    """Optimization pass for inverse/self-inverse gate cancellation and rotation merging.

    Rule details:
    - Cancels adjacent inverse or self-inverse gate pairs (e.g., H-H, X-X, CX-CX).
    - Merges consecutive single-qubit rotations along the same axis (e.g., RZ(theta1) * RZ(theta2) -> RZ(theta1 + theta2)).
    - Eliminates rotation gates that evaluate to identity modulo 2*pi (e.g., RZ(0) or RZ(2*pi*k)).
    """

    name: str = "cancellation"

    def run(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Run cancellation and merging pass on the quantum circuit.

        Args:
            circuit: Input QuantumCircuit.

        Returns:
            QuantumCircuit with redundant gates cancelled and rotations merged.
        """
        # TODO: Implement DAG-based or peephole gate cancellation and rotation merging
        return circuit.copy()
