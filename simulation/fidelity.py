"""Fidelity evaluation and noisy simulation metrics."""

from typing import Any, Dict, Optional, Union
import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.providers import Backend
import qiskit_ibm_runtime.fake_provider as fp


def hellinger_fidelity_from_counts(
    counts: Dict[str, int],
    ideal_counts: Dict[str, int],
) -> float:
    """Calculate classical Hellinger fidelity between simulated and reference measurement distributions.

    The Hellinger fidelity is defined as:
        F_H(P, Q) = ( sum_{x} sqrt( P(x) * Q(x) ) )^2
    where P and Q are empirical probabilities normalized over the respective total shots.

    Properties:
    - F_H(P, P) = 1.0 (identical distributions yield exact 1.0 fidelity).
    - F_H(P, Q) = 0.0 for disjoint/orthogonal distributions.
    - Symmetric: F_H(P, Q) = F_H(Q, P).

    Args:
        counts: Observed counts from noisy simulation using IBM device noise models.
        ideal_counts: Reference counts from ideal noiseless simulation.

    Returns:
        float: Hellinger fidelity in the range [0.0, 1.0].
    """
    if not counts or not ideal_counts:
        return 0.0

    total_counts = sum(counts.values())
    total_ideal = sum(ideal_counts.values())

    if total_counts <= 0 or total_ideal <= 0:
        return 0.0

    all_bitstrings = set(counts.keys()) | set(ideal_counts.keys())
    bhattacharyya_coeff = 0.0

    for bitstring in all_bitstrings:
        p = counts.get(bitstring, 0) / total_counts
        q = ideal_counts.get(bitstring, 0) / total_ideal
        bhattacharyya_coeff += np.sqrt(p * q)

    fidelity = float(bhattacharyya_coeff ** 2)
    return max(0.0, min(1.0, fidelity))


def success_probability(
    counts: Dict[str, int],
    correct_bitstring: str,
) -> float:
    """Compute empirical success probability of measuring the target correct bitstring.

    Calculates:
        P_success = counts[correct_bitstring] / total_shots
    Matching bitstrings are compared after stripping any whitespace.

    Args:
        counts: Observed measurement counts from simulation.
        correct_bitstring: Target ground-truth bitstring.

    Returns:
        float: Success probability in the range [0.0, 1.0].
    """
    if not counts or not correct_bitstring:
        return 0.0

    total_shots = sum(counts.values())
    if total_shots <= 0:
        return 0.0

    clean_target = correct_bitstring.replace(" ", "")
    matching_shots = counts.get(clean_target, 0)

    return float(matching_shots / total_shots)


def estimated_fidelity(
    circuit: QuantumCircuit,
    backend: Union[str, Any] = "FakeSherbrooke",
) -> float:
    """Estimate expected circuit execution fidelity from backend calibration data.

    Computation methodology:
    Computes the composite gate-error product:
        F_est = prod_{g in gates} (1.0 - error(g))
    where each gate error rate error(g) is retrieved directly from the backend's
    target calibration properties (target[gate_name][qargs].error).

    If the input circuit contains gates that are not native to the backend
    (e.g., basis CX while the backend native 2-qubit gate is ECR), the circuit
    is first transpiled to the backend at optimization_level=0 so the fidelity
    reflects the physical instructions executed on the device noise model.
    Non-unitary instructions (barrier, measure, reset) are excluded from the product.

    Args:
        circuit: Input QuantumCircuit.
        backend: Backend instance or name in qiskit_ibm_runtime.fake_provider. Defaults to 'FakeSherbrooke'.

    Returns:
        float: Analytical estimated fidelity in the range [0.0, 1.0].
    """
    # Resolve backend instance
    if isinstance(backend, str):
        if not hasattr(fp, backend):
            raise ValueError(f"Backend '{backend}' not found in qiskit_ibm_runtime.fake_provider.")
        backend_obj = getattr(fp, backend)()
    else:
        backend_obj = backend

    target = backend_obj.target

    # Determine if circuit requires physical mapping to backend basis / connectivity
    needs_transpile = False
    for inst in circuit.data:
        if inst.operation.name not in ("barrier", "measure", "reset"):
            if inst.operation.name not in target.operation_names:
                needs_transpile = True
                break

    if needs_transpile or circuit.num_qubits != backend_obj.num_qubits:
        t_qc = transpile(circuit, backend_obj, optimization_level=0, seed_transpiler=42)
    else:
        t_qc = circuit

    running_fidelity = 1.0

    for inst in t_qc.data:
        gate_name = inst.operation.name
        if gate_name in ("barrier", "measure", "reset"):
            continue

        qargs = tuple(t_qc.find_bit(q).index for q in inst.qubits)
        if gate_name in target and qargs in target[gate_name]:
            gate_props = target[gate_name][qargs]
            err = gate_props.error if gate_props and gate_props.error is not None else 0.0
            gate_success = 1.0 - max(0.0, min(1.0, float(err)))
            running_fidelity *= gate_success

    return max(0.0, min(1.0, float(running_fidelity)))
