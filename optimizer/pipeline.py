"""Optimization pipeline and result representations."""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence
from qiskit import QuantumCircuit, transpile

from metrics.metrics import get_metrics
from optimizer.base import OptimizationPass
from optimizer.cancellation import CancellationPass
from optimizer.commutation import CommutationPass
from optimizer.equivalence import is_equivalent

logger = logging.getLogger(__name__)


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
    translate_to_basis: bool = False,
) -> OptimizationResult:
    """Optimize a quantum circuit by iteratively applying optimization passes.

    Default passes = [CancellationPass(), CommutationPass()].
    Runs the passes in a loop until the circuit stops changing (up to a maximum of
    20 iterations), records metrics before and after each pass execution, and verifies
    equivalence against the original circuit at the end.

    Args:
        circuit: Input QuantumCircuit to optimize.
        passes: Sequence of OptimizationPass instances to apply.
            If None, defaults to [CancellationPass(), CommutationPass()].
        backend: Optional backend (or noise model/coupling map) for backend-aware passes.
        translate_to_basis: If True, pre-transpiles the input circuit to basis ('rz', 'sx', 'x', 'cx')
            at optimization_level=0 before running passes.

    Returns:
        OptimizationResult containing the optimized circuit, recorded per-pass metrics,
        and an equivalence verification flag.
    """
    if translate_to_basis:
        current_circuit = transpile(
            circuit,
            optimization_level=0,
            basis_gates=["rz", "sx", "x", "cx"],
            seed_transpiler=42,
        )
    else:
        current_circuit = circuit.copy()

    if passes is None:
        passes = [CancellationPass(), CommutationPass()]

    per_pass_metrics: List[Dict[str, Any]] = []
    max_iterations = 20

    for iteration in range(max_iterations):
        circuit_before_iter = current_circuit.copy()

        for opt_pass in passes:
            metrics_before = get_metrics(current_circuit)
            new_circuit = opt_pass.run(current_circuit)
            metrics_after = get_metrics(new_circuit)

            # Check per-pass equivalence to log any breaking pass
            try:
                pass_equiv = is_equivalent(current_circuit, new_circuit)
                if not pass_equiv:
                    logger.error(
                        f"Equivalence violation detected in pass '{opt_pass.name}' at iteration {iteration + 1}!"
                    )
            except Exception as ex:
                logger.error(f"Equivalence check failed in pass '{opt_pass.name}': {ex}")

            per_pass_metrics.append({
                "pass_name": getattr(opt_pass, "name", opt_pass.__class__.__name__),
                "metrics_before": metrics_before,
                "metrics_after": metrics_after,
                "iteration": iteration + 1,
            })
            current_circuit = new_circuit

        if current_circuit == circuit_before_iter:
            break

    # Final equivalence check against original circuit
    try:
        equivalent = is_equivalent(circuit, current_circuit)
    except Exception as ex:
        logger.warning(f"Final equivalence check encountered exception: {ex}")
        equivalent = False

    if not equivalent:
        logger.error("Final optimized circuit is NOT equivalent to the original circuit!")

    return OptimizationResult(
        optimized_circuit=current_circuit,
        per_pass_metrics=per_pass_metrics,
        equivalent=equivalent,
    )
