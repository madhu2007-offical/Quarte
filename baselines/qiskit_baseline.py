"""Baseline circuit compilation using Qiskit's transpile API and fairness rules."""

from typing import Any, Dict, Optional, Sequence
from qiskit import QuantumCircuit, transpile

from metrics.metrics import get_metrics
from optimizer.pipeline import optimize

DEFAULT_BASIS_GATES: Sequence[str] = ("rz", "sx", "x", "cx")


def qiskit_transpile(
    circuit: QuantumCircuit,
    level: int,
    basis_gates: Sequence[str] = DEFAULT_BASIS_GATES,
    seed: int = 42,
) -> QuantumCircuit:
    """Transpile a circuit using Qiskit's built-in transpiler at levels 0-3.

    Args:
        circuit: Input QuantumCircuit.
        level: Optimization level (0, 1, 2, or 3).
        basis_gates: Target basis gates sequence (defaults to ('rz', 'sx', 'x', 'cx')).
        seed: Random seed for stochastic transpiler passes (seed_transpiler).

    Returns:
        Transpiled QuantumCircuit in the target basis.
    """
    return transpile(
        circuit,
        optimization_level=level,
        basis_gates=list(basis_gates),
        seed_transpiler=seed,
    )


def generate_variants(
    circuit: QuantumCircuit,
    passes: Optional[Sequence[Any]] = None,
    basis_gates: Sequence[str] = DEFAULT_BASIS_GATES,
    seed: int = 42,
) -> Dict[str, QuantumCircuit]:
    """Produce all comparison variants under strict fairness rules.

    Fairness rule:
    Every variant is mapped to the EXACT same basis (rz, sx, x, cx) before
    metrics are evaluated.

    Variants produced:
    - original: Baseline decomposition to target basis with level=0.
    - qiskit_L0: Qiskit transpile with optimization_level=0.
    - qiskit_L1: Qiskit transpile with optimization_level=1.
    - qiskit_L2: Qiskit transpile with optimization_level=2.
    - qiskit_L3: Qiskit transpile with optimization_level=3.
    - ours: optimize(circuit, translate_to_basis=True).
    - ours_highlevel: optimize(circuit, translate_to_basis=False) then mapped to basis at level=0.

    Args:
        circuit: Input QuantumCircuit benchmark.
        passes: Optional sequence of custom optimization passes. If None, uses default pipeline passes.
        basis_gates: Target basis gates tuple.
        seed: Random seed for reproducibility.

    Returns:
        Dict mapping variant name to QuantumCircuit.
    """
    basis_list = list(basis_gates)

    # 1. Original (basis-mapped at level=0 for apples-to-apples basis comparison)
    original_basis = qiskit_transpile(circuit, level=0, basis_gates=basis_list, seed=seed)

    # 2. Qiskit levels 0-3
    l0 = qiskit_transpile(circuit, level=0, basis_gates=basis_list, seed=seed)
    l1 = qiskit_transpile(circuit, level=1, basis_gates=basis_list, seed=seed)
    l2 = qiskit_transpile(circuit, level=2, basis_gates=basis_list, seed=seed)
    l3 = qiskit_transpile(circuit, level=3, basis_gates=basis_list, seed=seed)

    # 3. Our optimizer: basis-level pass pipeline
    ours_basis_result = optimize(circuit, passes=passes, translate_to_basis=True)
    ours_basis = ours_basis_result.optimized_circuit

    # 4. Our optimizer: high-level pass pipeline then basis-mapped at level=0
    ours_hl_result = optimize(circuit, passes=passes, translate_to_basis=False)
    ours_hl_basis = qiskit_transpile(
        ours_hl_result.optimized_circuit,
        level=0,
        basis_gates=basis_list,
        seed=seed,
    )

    return {
        "original": original_basis,
        "qiskit_L0": l0,
        "qiskit_L1": l1,
        "qiskit_L2": l2,
        "qiskit_L3": l3,
        "ours": ours_basis,
        "ours_highlevel": ours_hl_basis,
    }


def evaluate_variant_metrics(
    circuit: QuantumCircuit,
    passes: Optional[Sequence[Any]] = None,
    basis_gates: Sequence[str] = DEFAULT_BASIS_GATES,
    seed: int = 42,
) -> Dict[str, Dict[str, int]]:
    """Compute structural metrics across all compiler variants for a benchmark.

    Args:
        circuit: Input QuantumCircuit.
        passes: Custom passes for 'ours'.
        basis_gates: Target basis gates.
        seed: Seed for transpilation.

    Returns:
        Dict mapping variant name to its get_metrics dictionary.
    """
    variants = generate_variants(circuit, passes=passes, basis_gates=basis_gates, seed=seed)
    return {name: get_metrics(qc) for name, qc in variants.items()}
