"""FastAPI REST API application for quantum circuit optimization."""

from pathlib import Path
from typing import Any, Dict, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from qiskit import QuantumCircuit
from qiskit.qasm2 import QASM2Error, dumps, loads

from api.schemas import (
    BenchmarkDetail,
    BenchmarkInfo,
    BenchmarkResultRow,
    CircuitMetrics,
    OptimizeRequest,
    OptimizeResponse,
    PassMetricItem,
)
from benchmarks.generators import get_benchmark_suite
from metrics.metrics import get_metrics
from optimizer.pipeline import optimize

app = FastAPI(
    title="Quantum Circuit Optimizer API",
    description=(
        "Classical, explainable quantum circuit gate-reduction optimizer built on Qiskit. "
        "Provides gate cancellation, rotation merging, commutation-based rewriting, "
        "and unitary equivalence verification."
    ),
    version="1.0.0",
)

# Enable CORS for frontend / dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RESULTS_CSV_PATH = Path(__file__).resolve().parent.parent / "results" / "results.csv"


@app.get(
    "/benchmarks",
    response_model=List[BenchmarkInfo],
    summary="List available benchmark circuits",
    tags=["Benchmarks"],
)
def list_benchmarks() -> List[BenchmarkInfo]:
    """Retrieve metadata for all benchmark circuits available in the evaluation suite."""
    suite = get_benchmark_suite()
    return [
        BenchmarkInfo(
            name=b["name"],
            qubits=b["qubits"],
            has_ground_truth=b.get("ideal_distribution") is not None,
        )
        for b in suite
    ]


@app.get(
    "/benchmarks/{name}",
    response_model=BenchmarkDetail,
    summary="Retrieve benchmark circuit details and QASM",
    tags=["Benchmarks"],
)
def get_benchmark(name: str) -> BenchmarkDetail:
    """Retrieve details and OpenQASM 2.0 definition for a named benchmark circuit."""
    suite = get_benchmark_suite()
    matched = next((b for b in suite if b["name"] == name), None)
    if matched is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Benchmark '{name}' not found. Check /benchmarks for available circuits.",
        )

    qc: QuantumCircuit = matched["circuit"]
    qasm_str = dumps(qc)
    return BenchmarkDetail(
        name=matched["name"],
        qubits=matched["qubits"],
        qasm=qasm_str,
        correct_bitstring=matched.get("correct_bitstring"),
        has_ground_truth=matched.get("ideal_distribution") is not None,
    )


@app.post(
    "/optimize",
    response_model=OptimizeResponse,
    summary="Optimize a quantum circuit",
    tags=["Optimization"],
)
def optimize_circuit(req: OptimizeRequest) -> OptimizeResponse:
    """Optimize a quantum circuit via cancellation, merging, and commutation passes.

    Input can be provided as raw OpenQASM 2.0 text or as a built-in benchmark name.
    Verifies unitary equivalence up to global phase. Rejects circuits with > 10 qubits.
    """
    if not req.qasm and not req.benchmark_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'qasm' string or 'benchmark_name'.",
        )

    circuit: QuantumCircuit
    if req.benchmark_name:
        suite = get_benchmark_suite()
        matched = next((b for b in suite if b["name"] == req.benchmark_name), None)
        if matched is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Benchmark '{req.benchmark_name}' not found.",
            )
        circuit = matched["circuit"]
    else:
        try:
            circuit = loads(req.qasm)
        except Exception as ex:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OpenQASM syntax: {ex}",
            )

    # Check qubit boundary for equivalence checking
    if circuit.num_qubits > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Equivalence checking is limited to circuits with <= 10 qubits "
                f"(received {circuit.num_qubits} qubits). "
                f"Direct unitary equivalence computation exceeds state space constraints."
            ),
        )

    orig_qasm = dumps(circuit)
    before_metrics_dict = get_metrics(circuit)

    # Execute optimizer pipeline
    opt_result = optimize(circuit, translate_to_basis=req.translate_to_basis)

    after_metrics_dict = get_metrics(opt_result.optimized_circuit)
    opt_qasm = dumps(opt_result.optimized_circuit)

    # Convert per-pass telemetry
    pass_items: List[PassMetricItem] = []
    for item in opt_result.per_pass_metrics:
        mb = item["metrics_before"]
        ma = item["metrics_after"]
        pass_items.append(
            PassMetricItem(
                pass_name=item["pass_name"],
                metrics_before=CircuitMetrics(
                    total_gates=mb["total_gates"],
                    two_qubit_gates=mb["two_qubit_gates"],
                    depth=mb["depth"],
                ),
                metrics_after=CircuitMetrics(
                    total_gates=ma["total_gates"],
                    two_qubit_gates=ma["two_qubit_gates"],
                    depth=ma["depth"],
                ),
                iteration=item["iteration"],
            )
        )

    return OptimizeResponse(
        before_metrics=CircuitMetrics(
            total_gates=before_metrics_dict["total_gates"],
            two_qubit_gates=before_metrics_dict["two_qubit_gates"],
            depth=before_metrics_dict["depth"],
        ),
        after_metrics=CircuitMetrics(
            total_gates=after_metrics_dict["total_gates"],
            two_qubit_gates=after_metrics_dict["two_qubit_gates"],
            depth=after_metrics_dict["depth"],
        ),
        per_pass_metrics=pass_items,
        equivalent=opt_result.equivalent,
        original_qasm=orig_qasm,
        optimized_qasm=opt_qasm,
    )


@app.get(
    "/results",
    response_model=List[BenchmarkResultRow],
    summary="Get precomputed evaluation sweep results",
    tags=["Results"],
)
def get_results() -> List[BenchmarkResultRow]:
    """Retrieve precomputed benchmark comparison results across all compiler variants and simulation."""
    if not RESULTS_CSV_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="results.csv not found. Run scripts/run_benchmarks.py first.",
        )

    df = pd.read_csv(RESULTS_CSV_PATH)
    # Fill NaN values with empty string or sensible default
    df_clean = df.astype(object).fillna("")
    records = df_clean.to_dict(orient="records")

    rows: List[BenchmarkResultRow] = []
    for r in records:
        rows.append(
            BenchmarkResultRow(
                benchmark=str(r["benchmark"]),
                variant=str(r["variant"]),
                qubits=int(r["qubits"]),
                total_gates=int(r["total_gates"]),
                two_qubit_gates=int(r["two_qubit_gates"]),
                depth=int(r["depth"]),
                est_fidelity=str(r["est_fidelity"]) if r["est_fidelity"] != "" else None,
                hellinger_mean=str(r["hellinger_mean"]) if r["hellinger_mean"] != "" else None,
                hellinger_std=str(r["hellinger_std"]) if r["hellinger_std"] != "" else None,
                success_prob_mean=str(r["success_prob_mean"]) if r["success_prob_mean"] != "" else None,
                success_prob_std=str(r["success_prob_std"]) if r["success_prob_std"] != "" else None,
                seeds=str(r["seeds"]) if r["seeds"] != "" else None,
                equivalent=bool(r["equivalent"]),
            )
        )
    return rows
