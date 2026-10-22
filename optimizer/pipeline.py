"""Optimization pipeline and result representations."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
from qiskit import QuantumCircuit

from metrics.metrics import get_metrics
from optimizer.base import IdentityPass, OptimizationPass
from optimizer.equivalence import is_equivalent


@dataclass
class OptimizationResult:
    """Result of running circuit optimization passes."""

    optimized_circuit: QuantumCircuit
    per_pass_metrics: List[Dict[str, Any]]
    equivalent: bool


def optimize(
    circuit: QuantumCircuit,
    passes: Optional[Sequence[OptimizationPass]] = None,
    backend: Optional[Any] = None,
) -> OptimizationResult:
    """Optimize a quantum circuit by iteratively applying optimization passes.

    Default passes = [IdentityPass()]. Runs the passes in a loop until the circuit
    stops changing (up to a maximum of 20 iterations), records metrics before and after
    each pass execution, and verifies equivalence against the original circuit at the end.

    Args:
        circuit: Input QuantumCircuit to optimize.
        passes: Sequence of OptimizationPass instances to apply. If None, defaults to [IdentityPass()].
        backend: Optional backend (or noise model/coupling map) for backend-aware passes.

    Returns:
        OptimizationResult containing the optimized circuit, recorded per-pass metrics,
        and an equivalence verification flag.
    """
    if passes is None:
        passes = [IdentityPass()]

    current_circuit = circuit.copy()
    per_pass_metrics: List[Dict[str, Any]] = []
    max_iterations = 20

    for iteration in range(max_iterations):
        circuit_before_iter = current_circuit.copy()

        for opt_pass in passes:
            metrics_before = get_metrics(current_circuit)
            new_circuit = opt_pass.run(current_circuit)
            metrics_after = get_metrics(new_circuit)

            per_pass_metrics.append({
                "pass_name": getattr(opt_pass, "name", opt_pass.__class__.__name__),
                "metrics_before": metrics_before,
                "metrics_after": metrics_after,
                "iteration": iteration + 1,
            })
            current_circuit = new_circuit

        if current_circuit == circuit_before_iter:
            break

    equivalent = is_equivalent(circuit, current_circuit)

    return OptimizationResult(
        optimized_circuit=current_circuit,
        per_pass_metrics=per_pass_metrics,
        equivalent=equivalent,
    )
