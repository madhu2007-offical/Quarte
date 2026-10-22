"""Tests for CancellationPass over 50 fixed-seed random redundant circuits."""

import random
import numpy as np
import pytest
from qiskit import QuantumCircuit

from optimizer.cancellation import CancellationPass
from optimizer.equivalence import is_equivalent


def generate_random_redundant(n_qubits: int, depth: int, seed: int) -> QuantumCircuit:
    """Generate a reproducible pseudo-random circuit containing redundancies.

    Allowed gates: H, X, Z, S, Sdg, T, Tdg, CX, RZ.

    Args:
        n_qubits: Number of qubits (2 to 5).
        depth: Circuit depth/cycles (up to 30).
        seed: Fixed seed for reproducibility.

    Returns:
        QuantumCircuit containing deliberate redundancies.
    """
    rng = random.Random(seed)
    qc = QuantumCircuit(n_qubits)
    single_gates = ["h", "x", "z", "s", "sdg", "t", "tdg"]

    for _ in range(depth):
        choice = rng.random()
        if choice < 0.28:
            # Inject adjacent self-inverse or adjoint pair
            q = rng.randrange(n_qubits)
            pair_type = rng.choice(["h", "x", "z", "s_sdg", "t_tdg", "rz_cancel"])
            if pair_type in ["h", "x", "z"]:
                getattr(qc, pair_type)(q)
                getattr(qc, pair_type)(q)
            elif pair_type == "s_sdg":
                qc.s(q)
                qc.sdg(q)
            elif pair_type == "t_tdg":
                qc.t(q)
                qc.tdg(q)
            elif pair_type == "rz_cancel":
                theta = rng.uniform(0.1, 3.0)
                qc.rz(theta, q)
                qc.rz(-theta, q)
        elif choice < 0.55 and n_qubits >= 2:
            # CX gate or redundant CX pair
            q1, q2 = rng.sample(range(n_qubits), 2)
            qc.cx(q1, q2)
            if rng.random() < 0.5:
                qc.cx(q1, q2)
        elif choice < 0.78:
            # Single qubit gate
            q = rng.randrange(n_qubits)
            g = rng.choice(single_gates)
            getattr(qc, g)(q)
        else:
            # Rotation gate
            q = rng.randrange(n_qubits)
            theta = rng.uniform(-np.pi, np.pi)
            qc.rz(theta, q)

    return qc


def test_random_circuits_optimization(capsys):
    """Run CancellationPass across 50 fixed-seed random redundant circuits.

    Verifies:
    1. Output circuit is strictly equivalent to input circuit up to global phase.
    2. Gate count never increases after optimization.
    3. Prints total gate count reduction across the 50 circuits.
    """
    opt_pass = CancellationPass()
    total_original_gates = 0
    total_optimized_gates = 0

    num_circuits = 50
    for i in range(num_circuits):
        n = (i % 4) + 2           # 2, 3, 4, 5 qubits
        depth = 10 + (i % 21)     # depths 10 to 30
        seed = 1000 + i

        qc = generate_random_redundant(n_qubits=n, depth=depth, seed=seed)
        original_gate_count = len(qc.data)

        optimized_qc = opt_pass.run(qc)
        optimized_gate_count = len(optimized_qc.data)

        # Invariant 1: Semantic equivalence
        assert is_equivalent(qc, optimized_qc), (
            f"Equivalence failure on circuit {i} (qubits={n}, depth={depth}, seed={seed})"
        )

        # Invariant 2: Non-increasing gate count
        assert optimized_gate_count <= original_gate_count, (
            f"Gate count increased on circuit {i}: {original_gate_count} -> {optimized_gate_count}"
        )

        total_original_gates += original_gate_count
        total_optimized_gates += optimized_gate_count

    total_reduction = total_original_gates - total_optimized_gates
    reduction_pct = (total_reduction / total_original_gates) * 100

    report = (
        f"\nRandom Redundant Circuits Optimization Report:\n"
        f"  Total Circuits Evaluated: {num_circuits}\n"
        f"  Total Input Gates:        {total_original_gates}\n"
        f"  Total Output Gates:       {total_optimized_gates}\n"
        f"  Total Gates Cancelled:    {total_reduction} ({reduction_pct:.1f}% reduction)\n"
    )
    # Output to stdout so it appears in test runs and logs
    print(report)
