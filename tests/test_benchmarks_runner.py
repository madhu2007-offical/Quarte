"""End-to-end smoke tests for benchmark runner."""

from pathlib import Path
import pandas as pd
import pytest

from scripts.run_benchmarks import run_all_benchmarks


def test_run_benchmarks_smoke(tmp_path):
    """Run an end-to-end benchmark execution and verify output CSV format."""
    out_csv = tmp_path / "test_results.csv"
    qasm_dir = tmp_path / "qasm"

    df = run_all_benchmarks(
        backend_name="FakeSherbrooke",
        shots=100,  # small shot count for quick test
        seed=42,
        output_csv=str(out_csv),
        save_qasm=False,
    )

    assert out_csv.exists()
    assert len(df) > 0

    expected_cols = [
        "benchmark",
        "variant",
        "qubits",
        "total_gates",
        "two_qubit_gates",
        "depth",
        "est_fidelity",
        "success_prob",
    ]
    assert list(df.columns) == expected_cols

    # Verify variants exist
    variants = set(df["variant"].unique())
    assert {"original", "qiskit_L0", "qiskit_L1", "qiskit_L2", "qiskit_L3", "ours"}.issubset(variants)
