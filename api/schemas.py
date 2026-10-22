"""Pydantic data schemas for the Quantum Circuit Optimizer REST API."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BenchmarkInfo(BaseModel):
    """Summary metadata for an available benchmark circuit."""

    name: str = Field(..., description="Benchmark identifier")
    qubits: int = Field(..., description="Number of qubits in the circuit")
    has_ground_truth: bool = Field(..., description="Whether a ground-truth measurement distribution exists")


class BenchmarkDetail(BaseModel):
    """Detailed definition and QASM representation of a benchmark circuit."""

    name: str = Field(..., description="Benchmark identifier")
    qubits: int = Field(..., description="Number of qubits")
    qasm: str = Field(..., description="OpenQASM 2.0 representation")
    correct_bitstring: Optional[str] = Field(None, description="Ground truth bitstring if deterministic")
    has_ground_truth: bool = Field(..., description="Whether ground-truth distribution exists")


class CircuitMetrics(BaseModel):
    """Structural complexity metrics for a quantum circuit."""

    total_gates: int = Field(..., description="Total gate count (excluding barrier and measure)")
    two_qubit_gates: int = Field(..., description="Count of two-qubit entangling gates")
    depth: int = Field(..., description="Critical path depth (excluding barrier and measure)")


class PassMetricItem(BaseModel):
    """Metrics recorded before and after an individual optimization pass."""

    pass_name: str = Field(..., description="Name of the optimization pass")
    metrics_before: CircuitMetrics = Field(..., description="Metrics before pass execution")
    metrics_after: CircuitMetrics = Field(..., description="Metrics after pass execution")
    iteration: int = Field(..., description="Outer loop iteration index")


class OptimizeRequest(BaseModel):
    """Request payload for circuit optimization."""

    qasm: Optional[str] = Field(None, description="OpenQASM 2.0 circuit string to optimize")
    benchmark_name: Optional[str] = Field(None, description="Name of a built-in benchmark to optimize")
    translate_to_basis: bool = Field(
        True,
        description="Whether to pre-transpile to standard basis (rz, sx, x, cx) before optimization",
    )


class OptimizeResponse(BaseModel):
    """Response payload containing optimization results and verified equivalence."""

    before_metrics: CircuitMetrics = Field(..., description="Metrics of input circuit")
    after_metrics: CircuitMetrics = Field(..., description="Metrics of optimized circuit")
    per_pass_metrics: List[PassMetricItem] = Field(..., description="Detailed pass-by-pass telemetry")
    equivalent: bool = Field(..., description="Whether optimized circuit was proven equivalent to original")
    original_qasm: str = Field(..., description="OpenQASM representation of input circuit")
    optimized_qasm: str = Field(..., description="OpenQASM representation of optimized circuit")


class BenchmarkResultRow(BaseModel):
    """Single row from the precomputed results.csv dataset."""

    benchmark: str
    variant: str
    qubits: int
    total_gates: int
    two_qubit_gates: int
    depth: int
    est_fidelity: Optional[str] = None
    hellinger_mean: Optional[str] = None
    hellinger_std: Optional[str] = None
    success_prob_mean: Optional[str] = None
    success_prob_std: Optional[str] = None
    seeds: Optional[str] = None
    equivalent: bool
