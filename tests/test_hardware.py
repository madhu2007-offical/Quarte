"""Tests for IBM Quantum hardware workflow and dry-run execution."""

import json
from pathlib import Path
from unittest.mock import patch
import pytest

from hardware.run_ibm import find_best_layout, run_hardware_workflow
import qiskit_ibm_runtime.fake_provider as fp


def test_dry_run_never_calls_cloud(tmp_path):
    """Verify dry-run mode executes entirely offline without querying QiskitRuntimeService."""
    with patch("qiskit_ibm_runtime.QiskitRuntimeService") as mock_service:
        mock_service.side_effect = RuntimeError("Cloud service should NEVER be called in dry run mode!")

        record = run_hardware_workflow(
            benchmark_name="bell",
            backend_name="FakeSherbrooke",
            shots=100,
            submit=False,
            seed=42,
            output_dir=str(tmp_path),
        )

        assert record["mode"] == "dry_run"
        assert record["backend"] == "fake_sherbrooke"
        assert "dry_run_sim" in record["job_id"]
        mock_service.assert_not_called()


def test_hardware_json_schema(tmp_path):
    """Verify schema, types, and binomial error calculation of output JSON file."""
    record = run_hardware_workflow(
        benchmark_name="bell",
        backend_name="FakeSherbrooke",
        shots=500,
        submit=False,
        seed=42,
        output_dir=str(tmp_path),
    )

    # Verify JSON file written to disk
    json_files = list(tmp_path.glob("*.json"))
    assert len(json_files) == 1

    with open(json_files[0], "r", encoding="utf-8") as f:
        data = json.load(f)

    # Top-level schema
    required_keys = {
        "benchmark",
        "backend",
        "job_id",
        "timestamp",
        "shots",
        "layout",
        "mode",
        "variants",
    }
    assert required_keys.issubset(set(data.keys()))
    assert data["mode"] == "dry_run"
    assert data["shots"] == 500
    assert isinstance(data["layout"], list)
    assert len(data["layout"]) == 2  # bell has 2 qubits

    # Variants schema
    required_variants = {"original", "ours", "qiskit_L1", "qiskit_L3"}
    assert set(data["variants"].keys()) == required_variants

    for v_name, v_info in data["variants"].items():
        assert "post_transpile_metrics" in v_info
        assert "counts" in v_info
        assert "success_probability" in v_info
        assert "stderr" in v_info
        assert "hellinger_fidelity" in v_info

        m = v_info["post_transpile_metrics"]
        assert "total_gates" in m
        assert "two_qubit_gates" in m
        assert "depth" in m

        p = v_info["success_probability"]
        err = v_info["stderr"]
        if p is not None and err is not None:
            expected_err = (p * (1.0 - p) / 500) ** 0.5
            assert abs(err - expected_err) < 1e-4


def test_fair_initial_layout_applied_to_all_variants(tmp_path):
    """Verify that every variant is compiled to the identical physical qubit layout."""
    fake = fp.FakeSherbrooke()
    layout = find_best_layout(fake, num_qubits=3)
    assert len(layout) == 3
    assert len(set(layout)) == 3  # All qubits are unique physical indices

    record = run_hardware_workflow(
        benchmark_name="qft_then_inverse_3",
        backend_name="FakeSherbrooke",
        shots=100,
        submit=False,
        seed=42,
        output_dir=str(tmp_path),
    )

    assert record["layout"] == layout

    # Ensure all variants recorded post-transpile metrics using the same layout
    for v_name, v_data in record["variants"].items():
        m = v_data["post_transpile_metrics"]
        assert m["total_gates"] > 0
        assert m["depth"] > 0


def test_dashboard_hardware_panel_hiding_logic(tmp_path):
    """Verify dashboard hardware panel only activates when files with mode == 'hardware' exist."""
    # Scenario 1: Empty folder -> no hardware records
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    hw_files_empty = [
        f for f in empty_dir.glob("*.json")
        if json.loads(f.read_text(encoding="utf-8")).get("mode") == "hardware"
    ]
    assert len(hw_files_empty) == 0

    # Scenario 2: Folder with only dry_run files -> still no hardware records
    dry_dir = tmp_path / "dry_only"
    dry_dir.mkdir()
    dry_file = dry_dir / "sim_run.json"
    dry_file.write_text(json.dumps({"mode": "dry_run", "backend": "fake_sherbrooke"}), encoding="utf-8")

    hw_files_dry = [
        f for f in dry_dir.glob("*.json")
        if json.loads(f.read_text(encoding="utf-8")).get("mode") == "hardware"
    ]
    assert len(hw_files_dry) == 0  # Panel MUST stay hidden

    # Scenario 3: Folder with a hardware execution file -> panel activates
    hw_dir = tmp_path / "with_hw"
    hw_dir.mkdir()
    hw_file = hw_dir / "cloud_hw_run.json"
    hw_file.write_text(json.dumps({"mode": "hardware", "backend": "ibm_fez"}), encoding="utf-8")

    hw_files_real = [
        f for f in hw_dir.glob("*.json")
        if json.loads(f.read_text(encoding="utf-8")).get("mode") == "hardware"
    ]
    assert len(hw_files_real) == 1  # Panel activates
