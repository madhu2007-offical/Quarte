"""Tests for FastAPI endpoints and dashboard smoke test."""

import importlib
import pytest
from fastapi.testclient import TestClient
from qiskit import QuantumCircuit
from qiskit.qasm2 import dumps

from api.main import app

client = TestClient(app)


def test_get_benchmarks():
    """Verify GET /benchmarks returns complete benchmark catalog."""
    response = client.get("/benchmarks")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 17

    names = [item["name"] for item in data]
    assert "bell" in names
    assert "ghz_3" in names
    assert "grover_small" in names
    assert "ripple_carry_adder_1" in names
    assert "ripple_carry_adder_2" in names
    for i in range(8):
        assert f"random_seed_{i}" in names

    first = data[0]
    assert "name" in first
    assert "qubits" in first
    assert "has_ground_truth" in first


def test_get_benchmark_detail_success():
    """Verify GET /benchmarks/{name} returns correct details and valid QASM."""
    response = client.get("/benchmarks/bell")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "bell"
    assert data["qubits"] == 2
    assert data["has_ground_truth"] is True
    assert "OPENQASM" in data["qasm"]


def test_get_benchmark_detail_not_found():
    """Verify GET /benchmarks/{name} returns 404 for unknown benchmark."""
    response = client.get("/benchmarks/nonexistent_benchmark_xyz")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_optimize_with_benchmark_name():
    """Verify POST /optimize successfully optimizes a named benchmark."""
    response = client.post(
        "/optimize",
        json={"benchmark_name": "bell", "translate_to_basis": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["equivalent"] is True
    assert "before_metrics" in data
    assert "after_metrics" in data
    assert "per_pass_metrics" in data
    assert "original_qasm" in data
    assert "optimized_qasm" in data
    assert "OPENQASM" in data["original_qasm"]
    assert "OPENQASM" in data["optimized_qasm"]


def test_optimize_with_raw_qasm():
    """Verify POST /optimize reduces gates and preserves equivalence on raw QASM."""
    # Circuit with redundant H-H and X-X pairs
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.h(0)
    qc.cx(0, 1)
    qc.x(1)
    qc.x(1)
    qasm_str = dumps(qc)

    response = client.post(
        "/optimize",
        json={"qasm": qasm_str, "translate_to_basis": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["equivalent"] is True
    assert data["after_metrics"]["total_gates"] < data["before_metrics"]["total_gates"]
    assert data["after_metrics"]["two_qubit_gates"] == 1


def test_optimize_invalid_qasm():
    """Verify POST /optimize returns 400 Bad Request on invalid QASM syntax."""
    response = client.post(
        "/optimize",
        json={"qasm": "THIS IS INVALID OPENQASM; SYNTAX ERROR"},
    )
    assert response.status_code == 400
    assert "Invalid OpenQASM syntax" in response.json()["detail"]


def test_optimize_qubit_limit_exceeded():
    """Verify POST /optimize rejects circuits with > 10 qubits with clear 400 error."""
    qc = QuantumCircuit(11)
    qc.x(0)
    qasm_str = dumps(qc)

    response = client.post(
        "/optimize",
        json={"qasm": qasm_str},
    )
    assert response.status_code == 400
    assert "limited to circuits with <= 10 qubits" in response.json()["detail"]
    assert "received 11 qubits" in response.json()["detail"]


def test_optimize_missing_inputs():
    """Verify POST /optimize validates presence of input fields."""
    response = client.post("/optimize", json={})
    assert response.status_code == 400
    assert "Must provide either 'qasm' string or 'benchmark_name'" in response.json()["detail"]

    response = client.post("/optimize", json={"benchmark_name": "unknown_bench"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_results():
    """Verify GET /results returns all precomputed rows from results.csv."""
    response = client.get("/results")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 119  # 17 benchmarks * 7 compiler variants

    required_keys = {
        "benchmark",
        "variant",
        "qubits",
        "total_gates",
        "two_qubit_gates",
        "depth",
        "equivalent",
    }
    for row in data:
        assert required_keys.issubset(set(row.keys()))
        assert row["equivalent"] is True

    # Check presence of random seeds
    bench_names = {row["benchmark"] for row in data}
    for i in range(8):
        assert f"random_seed_{i}" in bench_names


def test_swagger_and_openapi_docs():
    """Verify OpenAPI JSON schema and Swagger UI /docs endpoints are functional."""
    openapi_res = client.get("/openapi.json")
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    assert schema["info"]["title"] == "Quantum Circuit Optimizer API"
    assert "/benchmarks" in schema["paths"]
    assert "/benchmarks/{name}" in schema["paths"]
    assert "/optimize" in schema["paths"]
    assert "/results" in schema["paths"]

    docs_res = client.get("/docs")
    assert docs_res.status_code == 200
    assert "text/html" in docs_res.headers["content-type"]


def test_dashboard_smoke():
    """Smoke test dashboard module import without uncaught exceptions."""
    mod = importlib.import_module("dashboard.app")
    assert hasattr(mod, "RESULTS_CSV_PATH")
    assert mod.RESULTS_CSV_PATH.name == "results.csv"
