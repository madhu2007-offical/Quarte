"""Quantum circuit gate-reduction optimizer package."""

from optimizer.base import IdentityPass, OptimizationPass
from optimizer.cancellation import CancellationPass
from optimizer.commutation import CommutationPass
from optimizer.equivalence import is_equivalent, strip_measurements
from optimizer.pipeline import OptimizationResult, optimize
from optimizer.routing import RoutingPass

__all__ = [
    "OptimizationPass",
    "IdentityPass",
    "CancellationPass",
    "CommutationPass",
    "RoutingPass",
    "strip_measurements",
    "is_equivalent",
    "OptimizationResult",
    "optimize",
]
