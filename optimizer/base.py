"""Base definitions for quantum circuit optimization passes."""

from qiskit import QuantumCircuit


class OptimizationPass:
    """Abstract base class for circuit optimization passes."""

    name: str = "base"

    def run(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Run the optimization pass on the provided quantum circuit.

        Args:
            circuit: Input QuantumCircuit to be optimized.

        Returns:
            Optimized QuantumCircuit.
        """
        raise NotImplementedError("Subclasses must implement run()")


class IdentityPass(OptimizationPass):
    """Identity pass that returns an unmodified copy of the input circuit."""

    name: str = "identity"

    def run(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Return an exact copy of the input circuit.

        Args:
            circuit: Input QuantumCircuit.

        Returns:
            Copy of the input QuantumCircuit.
        """
        return circuit.copy()
