"""Baseline circuit compilation using Qiskit's transpile API."""

from typing import Sequence
from qiskit import QuantumCircuit, transpile


def qiskit_transpile(
    circuit: QuantumCircuit,
    level: int,
    basis_gates: Sequence[str] = ("rz", "sx", "x", "cx"),
    seed: int = 42,
) -> QuantumCircuit:
    """Transpile a circuit using Qiskit's built-in transpiler at levels 0-3.

    Args:
        circuit: Input QuantumCircuit.
        level: Optimization level (0, 1, 2, or 3).
        basis_gates: Tuple or list of target basis gates. Defaults to ("rz", "sx", "x", "cx").
        seed: Random seed for stochastic transpiler passes (seed_transpiler).

    Returns:
        Transpiled QuantumCircuit.
    """
    return transpile(
        circuit,
        optimization_level=level,
        basis_gates=list(basis_gates),
        seed_transpiler=seed,
    )
