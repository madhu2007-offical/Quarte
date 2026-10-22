"""Tests for optimizer pipeline across 100 broad-mix fixed-seed random circuits and QFT."""

import random
import numpy as np
import pytest
from qiskit import QuantumCircuit

from benchmarks.generators import qft
from metrics.metrics import get_metrics
from optimizer.equivalence import is_equivalent
from optimizer.pipeline import optimize


def generate_broad_random_circuit(n_qubits: int, depth: int, seed: int) -> QuantumCircuit:
    """Generate a reproducible pseudo-random circuit using a broad gate set.

    Gate mix includes:
    H, X, Y, Z, S, Sdg, T, Tdg, SX, RX, RZ, CX, CZ, SWAP, and occasional barriers.

    Args:
        n_qubits: Number of qubits (2 to 5).
        depth: Number of layers/cycles (up to 30).
        seed: Random seed for reproducibility.

    Returns:
        QuantumCircuit: Seeded broad-mix circuit.
    """
    rng = random.Random(seed)
    qc = QuantumCircuit(n_qubits)
    single_1q = ["h", "x", "y", "z", "s", "sdg", "t", "tdg", "sx"]

    for _ in range(depth):
        choice = rng.random()
        if choice < 0.10:
            # Occasional barrier
            qc.barrier()
        elif choice < 0.40:
            # Single-qubit gate or redundant pair
            q = rng.randrange(n_qubits)
            g = rng.choice(single_1q)
            getattr(qc, g)(q)
            if rng.random() < 0.35:
                # Add duplicate or adjoint to provide cancellation opportunities
                if g == "sx":
                    getattr(qc, rng.choice(["sx", "sxdg"]))(q)
                elif g == "s":
                    getattr(qc, rng.choice(["s", "sdg"]))(q)
                elif g == "t":
                    getattr(qc, rng.choice(["t", "tdg"]))(q)
                else:
                    getattr(qc, g)(q)
        elif choice < 0.70 and n_qubits >= 2:
            # Two-qubit gate: CX, CZ, SWAP
            q1, q2 = rng.sample(range(n_qubits), 2)
            gate_2q = rng.choice(["cx", "cz", "swap"])
            getattr(qc, gate_2q)(q1, q2)
            if rng.random() < 0.35:
                getattr(qc, gate_2q)(q1, q2)
        else:
            # Single-qubit rotation: RZ, RX
            q = rng.randrange(n_qubits)
            rot = rng.choice(["rz", "rx"])
            angle = rng.uniform(-np.pi, np.pi)
            getattr(qc, rot)(angle, q)

    return qc


def test_random_circuits_broad_mix_100():
    """Run optimization pipeline across 100 fixed-seed broad-mix random circuits.

    Verifies:
    1. Output circuit is strictly equivalent to input circuit up to global phase.
    2. Gate count never increases.
    3. Prints total reduction across the 100 circuits.
    """
    total_original_gates = 0
    total_optimized_gates = 0
    num_circuits = 100

    for i in range(num_circuits):
        n = (i % 4) + 2          # 2, 3, 4, 5 qubits
        depth = 10 + (i % 21)    # depths 10 to 30
        seed = 4000 + i

        qc = generate_broad_random_circuit(n_qubits=n, depth=depth, seed=seed)
        m_before = get_metrics(qc)
        orig_gate_count = m_before["total_gates"]

        res = optimize(qc)
        m_after = get_metrics(res.optimized_circuit)
        opt_gate_count = m_after["total_gates"]

        # Invariant 1: Semantic equivalence
        assert res.equivalent, (
            f"Equivalence violation on circuit {i} (n={n}, depth={depth}, seed={seed})"
        )
        assert is_equivalent(qc, res.optimized_circuit), (
            f"Independent equivalence checker failed on circuit {i}"
        )

        # Invariant 2: Non-increasing gate count
        assert opt_gate_count <= orig_gate_count, (
            f"Gate count increased on circuit {i}: {orig_gate_count} -> {opt_gate_count}"
        )

        total_original_gates += orig_gate_count
        total_optimized_gates += opt_gate_count

    total_reduction = total_original_gates - total_optimized_gates
    reduction_pct = (total_reduction / total_original_gates) * 100 if total_original_gates > 0 else 0.0

    report = (
        f"\nBroad Gate-Set Optimization Report (100 Circuits):\n"
        f"  Total Circuits Evaluated: {num_circuits}\n"
        f"  Total Input Gates:        {total_original_gates}\n"
        f"  Total Output Gates:       {total_optimized_gates}\n"
        f"  Total Gates Cancelled:    {total_reduction} ({reduction_pct:.1f}% reduction)\n"
    )
    print(report)


def test_optimize_qft3_translate_to_basis():
    """Optimize QFT(3) with translate_to_basis=True and assert equivalence."""
    circuit = qft(3)
    res = optimize(circuit, translate_to_basis=True)

    assert res.equivalent is True
    assert is_equivalent(circuit, res.optimized_circuit) is True

    m_orig_basis = res.per_pass_metrics[0]["metrics_before"]
    m_final = get_metrics(res.optimized_circuit)

    # QFT(3) decomposes to 27 basis gates at L0; optimizer reduces to 24 gates
    assert m_final["total_gates"] <= m_orig_basis["total_gates"]
