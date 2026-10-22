"""Fidelity evaluation and validation stubs."""

from typing import Any, Dict
from qiskit import QuantumCircuit


def hellinger_fidelity_from_counts(
    counts: Dict[str, int],
    ideal_counts: Dict[str, int],
) -> float:
    """Calculate the classical Hellinger fidelity between simulated and ideal measurement counts.

    The Hellinger fidelity is defined as:
        F_H(P, Q) = (sum_x sqrt(P(x) * Q(x)))^2
    where P and Q are normalized probability distributions over the observed bitstrings.

    Args:
        counts: Observed counts from noisy simulation using IBM device noise models.
        ideal_counts: Reference counts from ideal noiseless simulation.

    Returns:
        Fidelity metric between 0.0 and 1.0.

    Raises:
        NotImplementedError: Stub awaiting Day 1 implementation.
    """
    # TODO: Implement classical Hellinger fidelity computation
    raise NotImplementedError("hellinger_fidelity_from_counts is not yet implemented.")


def success_probability(
    counts: Dict[str, int],
    correct_bitstring: str,
) -> float:
    """Compute the empirical success probability of obtaining the expected bitstring.

    Determines the fraction of total measurement shots that coincide with the known
    ground-truth bitstring (e.g. for deterministic algorithms or oracle markers).

    Args:
        counts: Observed measurement counts from simulation.
        correct_bitstring: Expected bitstring solution.

    Returns:
        Fraction of shots matching the expected bitstring, between 0.0 and 1.0.

    Raises:
        NotImplementedError: Stub awaiting Day 1 implementation.
    """
    # TODO: Implement success probability evaluation
    raise NotImplementedError("success_probability is not yet implemented.")


def estimated_fidelity(
    circuit: QuantumCircuit,
    backend: Any,
) -> float:
    """Estimate expected circuit execution fidelity using device noise parameters.

    Calculates an analytical gate-error fidelity proxy based on the backend's
    1-qubit error rates, 2-qubit CX/ECR error rates, and readout errors derived
    from noisy simulation using IBM device noise models.

    Args:
        circuit: Input QuantumCircuit.
        backend: Fake backend instance containing target device calibration data.

    Returns:
        Estimated aggregate circuit fidelity between 0.0 and 1.0.

    Raises:
        NotImplementedError: Stub awaiting Day 1 implementation.
    """
    # TODO: Implement analytic fidelity estimation from device calibration properties
    raise NotImplementedError("estimated_fidelity is not yet implemented.")
