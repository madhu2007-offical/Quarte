"""Quantum circuit benchmark generators."""

import random
from typing import Optional
import numpy as np
from qiskit import QuantumCircuit


def bell(measure: bool = False) -> QuantumCircuit:
    """Generate a standard 2-qubit Bell state (|00> + |11>) / sqrt(2).

    Args:
        measure: If True, adds measurement operations to classical registers.

    Returns:
        QuantumCircuit implementing the Bell state.
    """
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    if measure:
        qc.measure_all()
    return qc


def ghz(n: int, measure: bool = False) -> QuantumCircuit:
    """Generate an n-qubit Greenberger-Horne-Zeilinger (GHZ) state (|0...0> + |1...1>) / sqrt(2).

    Args:
        n: Number of qubits (must be >= 1).
        measure: If True, adds measurement operations to classical registers.

    Returns:
        QuantumCircuit creating the n-qubit GHZ state.
    """
    if n < 1:
        raise ValueError("n must be at least 1.")
    qc = QuantumCircuit(n)
    qc.h(0)
    for i in range(1, n):
        qc.cx(0, i)
    if measure:
        qc.measure_all()
    return qc


def qft(n: int) -> QuantumCircuit:
    """Generate an n-qubit Quantum Fourier Transform (QFT) circuit.

    Args:
        n: Number of qubits (must be >= 1).

    Returns:
        QuantumCircuit executing the standard QFT without measurements.
    """
    if n < 1:
        raise ValueError("n must be at least 1.")
    qc = QuantumCircuit(n)
    for i in range(n):
        qc.h(i)
        for j in range(i + 1, n):
            angle = np.pi / (2 ** (j - i))
            qc.cp(angle, j, i)
    for i in range(n // 2):
        qc.swap(i, n - 1 - i)
    return qc


def random_redundant_circuit(n: int, depth: int, seed: int = 42) -> QuantumCircuit:
    """Generate a reproducible pseudo-random circuit with deliberate redundancies.

    Injects patterns such as adjacent self-inverse gates (H-H, X-X, CX-CX),
    adjacent single-qubit rotations on the same axis (RZ-RZ), and commuting gates
    to provide optimization targets for passes.

    Args:
        n: Number of qubits.
        depth: Number of layers of operations.
        seed: Random seed for deterministic generation.

    Returns:
        QuantumCircuit containing deliberate redundancies.
    """
    if n < 1:
        raise ValueError("n must be at least 1.")
    rng = random.Random(seed)
    qc = QuantumCircuit(n)

    patterns = ["self_inverse", "rotation_pair"]
    if n >= 2:
        patterns.extend(["cx_pair", "commuting_rz_cx"])

    for _ in range(depth):
        choice = rng.choice(patterns)
        if choice == "self_inverse":
            q = rng.randrange(n)
            gate = rng.choice(["h", "x", "z", "y"])
            getattr(qc, gate)(q)
            getattr(qc, gate)(q)
        elif choice == "rotation_pair":
            q = rng.randrange(n)
            theta1 = rng.uniform(0.1, np.pi)
            theta2 = rng.uniform(0.1, np.pi)
            qc.rz(theta1, q)
            qc.rz(theta2, q)
        elif choice == "cx_pair" and n >= 2:
            q1, q2 = rng.sample(range(n), 2)
            qc.cx(q1, q2)
            qc.cx(q1, q2)
        elif choice == "commuting_rz_cx" and n >= 2:
            q1, q2 = rng.sample(range(n), 2)
            theta = rng.uniform(0.1, np.pi)
            qc.rz(theta, q1)
            qc.cx(q1, q2)

    return qc


def load_qasm(filepath: str) -> QuantumCircuit:
    """Load a benchmark circuit from an OpenQASM file.

    Args:
        filepath: Path to the OpenQASM (.qasm) file.

    Returns:
        Loaded QuantumCircuit.
    """
    # TODO: Implement QASM loading and validation
    raise NotImplementedError("load_qasm is not yet implemented.")


def random_clifford_circuit(n: int, depth: int, seed: int = 42) -> QuantumCircuit:
    """Generate a random Clifford circuit.

    Args:
        n: Number of qubits.
        depth: Circuit depth.
        seed: Random seed.

    Returns:
        QuantumCircuit.
    """
    # TODO: Implement random Clifford circuit generation
    raise NotImplementedError("random_clifford_circuit is not yet implemented.")
