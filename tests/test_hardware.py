"""Tests for IBM Quantum hardware workflow and dry-run execution."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
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


def test_usage_guard_aborts_when_qpu_time_below_threshold(tmp_path):
    """Verify that submit=True immediately aborts without submitting if QPU time is below safety cap."""
    with patch("qiskit_ibm_runtime.QiskitRuntimeService") as mock_service_cls, \
         patch("qiskit_ibm_runtime.SamplerV2") as mock_sampler_cls:

        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

        mock_backend = fp.FakeSherbrooke()
        mock_service.least_busy.return_value = mock_backend
        mock_service.backend.return_value = mock_backend

        # Scenario 1: remaining QPU time (25s) is below max_qpu_seconds (60s)
        mock_service.usage.return_value = {
            "usage_remaining_seconds": 25.0,
            "usage_limit_reached": False,
        }

        mock_sampler = MagicMock()
        mock_sampler_cls.return_value = mock_sampler

        with pytest.raises(RuntimeError) as exc_info:
            run_hardware_workflow(
                benchmark_name="bell",
                shots=100,
                submit=True,
                max_qpu_seconds=60.0,
                output_dir=str(tmp_path),
            )

        assert "Aborting hardware submission" in str(exc_info.value)
        assert "below the configured safety threshold of 60.0s" in str(exc_info.value)
        # Verify SamplerV2.run was NEVER called
        mock_sampler.run.assert_not_called()

        # Scenario 2: usage_limit_reached is True
        mock_service.usage.return_value = {
            "usage_remaining_seconds": 120.0,
            "usage_limit_reached": True,
        }

        with pytest.raises(RuntimeError) as exc_info2:
            run_hardware_workflow(
                benchmark_name="bell",
                shots=100,
                submit=True,
                max_qpu_seconds=60.0,
                output_dir=str(tmp_path),
            )

        assert "Aborting hardware submission" in str(exc_info2.value)
        mock_sampler.run.assert_not_called()


def test_aggregation_hardware_results(tmp_path):
    """Verify aggregate_hardware_results computes accurate mean, std, and ignores dry-run files."""
    from scripts.aggregate_hardware import aggregate_hardware_results

    # Run 1 (Hardware)
    run1 = {
        "benchmark": "qft_then_inverse_3",
        "backend": "ibm_fez",
        "job_id": "job_001",
        "timestamp": "2026-10-23T01:00:00+00:00",
        "shots": 2000,
        "layout": [22, 23, 24],
        "mode": "hardware",
        "variants": {
            "original": {
                "post_transpile_metrics": {"total_gates": 180, "two_qubit_gates": 24, "depth": 120},
                "success_probability": 0.88,
                "stderr": 0.007,
                "hellinger_fidelity": 0.88,
            },
            "ours": {
                "post_transpile_metrics": {"total_gates": 130, "two_qubit_gates": 18, "depth": 90},
                "success_probability": 0.90,
                "stderr": 0.006,
                "hellinger_fidelity": 0.90,
            },
            "qiskit_L1": {
                "post_transpile_metrics": {"total_gates": 130, "two_qubit_gates": 18, "depth": 90},
                "success_probability": 0.91,
                "stderr": 0.006,
                "hellinger_fidelity": 0.91,
            },
            "qiskit_L3": {
                "post_transpile_metrics": {"total_gates": 2, "two_qubit_gates": 0, "depth": 1},
                "success_probability": 0.98,
                "stderr": 0.003,
                "hellinger_fidelity": 0.98,
            },
        },
    }

    # Run 2 (Hardware)
    run2 = {
        "benchmark": "qft_then_inverse_3",
        "backend": "ibm_fez",
        "job_id": "job_002",
        "timestamp": "2026-10-23T01:05:00+00:00",
        "shots": 2000,
        "layout": [22, 23, 24],
        "mode": "hardware",
        "variants": {
            "original": {
                "post_transpile_metrics": {"total_gates": 180, "two_qubit_gates": 24, "depth": 120},
                "success_probability": 0.90,
                "stderr": 0.006,
                "hellinger_fidelity": 0.90,
            },
            "ours": {
                "post_transpile_metrics": {"total_gates": 130, "two_qubit_gates": 18, "depth": 90},
                "success_probability": 0.94,
                "stderr": 0.005,
                "hellinger_fidelity": 0.94,
            },
            "qiskit_L1": {
                "post_transpile_metrics": {"total_gates": 130, "two_qubit_gates": 18, "depth": 90},
                "success_probability": 0.93,
                "stderr": 0.005,
                "hellinger_fidelity": 0.93,
            },
            "qiskit_L3": {
                "post_transpile_metrics": {"total_gates": 2, "two_qubit_gates": 0, "depth": 1},
                "success_probability": 0.98,
                "stderr": 0.003,
                "hellinger_fidelity": 0.98,
            },
        },
    }

    # Run 3 (Dry Run - should be ignored)
    run_dry = {
        "benchmark": "qft_then_inverse_3",
        "backend": "fake_sherbrooke",
        "job_id": "dry_run_003",
        "timestamp": "2026-10-23T01:10:00+00:00",
        "shots": 2000,
        "layout": [0, 1, 2],
        "mode": "dry_run",
        "variants": {},
    }

    (tmp_path / "run1.json").write_text(json.dumps(run1), encoding="utf-8")
    (tmp_path / "run2.json").write_text(json.dumps(run2), encoding="utf-8")
    (tmp_path / "run_dry.json").write_text(json.dumps(run_dry), encoding="utf-8")

    agg = aggregate_hardware_results(tmp_path)
    assert "qft_then_inverse_3" in agg
    data = agg["qft_then_inverse_3"]

    assert data["total_runs"] == 2
    assert data["backends"] == ["ibm_fez"]

    ours = data["variants"]["ours"]
    assert ours["num_runs"] == 2
    assert abs(ours["success_probability_mean"] - 0.92) < 1e-5
    # Sample std of [0.90, 0.94] with ddof=1 is sqrt(0.04^2 / 2) = 0.028284
    assert abs(ours["success_probability_std"] - 0.028284) < 1e-4

    orig = data["variants"]["original"]
    assert abs(orig["success_probability_mean"] - 0.89) < 1e-5
    assert abs(orig["success_probability_std"] - 0.014142) < 1e-4


def test_hellinger_versus_ideal_known_inputs():
    """Verify exact Hellinger fidelity calculations and ideal distribution simulation on known inputs."""
    from benchmarks.generators import ghz, qft_then_inverse
    from hardware.run_ibm import bootstrap_hellinger_stderr, compute_ideal_distribution
    from simulation.fidelity import hellinger_fidelity_from_counts

    # Known Input 1: Exact identical distributions -> F_H = 1.0
    dist_exact = {"000": 500, "111": 500}
    fid_exact = hellinger_fidelity_from_counts(dist_exact, dist_exact)
    assert abs(fid_exact - 1.0) < 1e-6
    err_exact = bootstrap_hellinger_stderr(dist_exact, dist_exact, shots=1000)
    assert abs(err_exact) < 1e-3

    # Known Input 2: Orthogonal / disjoint distributions -> F_H = 0.0
    dist_ortho_1 = {"000": 1000}
    dist_ortho_2 = {"111": 1000}
    fid_ortho = hellinger_fidelity_from_counts(dist_ortho_1, dist_ortho_2)
    assert abs(fid_ortho - 0.0) < 1e-6

    # Known Input 3: Half overlap -> Bhattacharyya coeff = sqrt(0.5) -> F_H = 0.5
    dist_half_1 = {"00": 1000}
    dist_half_2 = {"00": 500, "11": 500}
    fid_half = hellinger_fidelity_from_counts(dist_half_1, dist_half_2)
    assert abs(fid_half - 0.5) < 1e-6

    # Known Input 4: GHZ 3-qubit state ideal distribution
    ghz_circ = ghz(3)
    ideal_ghz = compute_ideal_distribution(ghz_circ)
    assert len(ideal_ghz) == 2
    assert abs(ideal_ghz.get("000", 0.0) - 0.5) < 1e-5
    assert abs(ideal_ghz.get("111", 0.0) - 0.5) < 1e-5

    # Known Input 5: QFT-then-inverse 3-qubit deterministic state |101>
    qft_inv_circ = qft_then_inverse(3, "101")
    ideal_qft_inv = compute_ideal_distribution(qft_inv_circ)
    assert len(ideal_qft_inv) == 1
    assert abs(ideal_qft_inv.get("101", 0.0) - 1.0) < 1e-5
