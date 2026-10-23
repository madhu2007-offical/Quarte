"""Aggregate IBM Quantum hardware execution results across runs and benchmarks.

Parses all saved hardware evaluation records (JSON files with "mode": "hardware")
in the results/hardware directory, aggregates metrics across repeated runs,
computes sample mean and standard deviation, and outputs formatted summary tables.
"""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

VARIANTS_ORDER = ["original", "ours", "qiskit_L1", "qiskit_L3"]


def load_hardware_records(hardware_dir: Union[str, Path] = "results/hardware") -> List[Dict[str, Any]]:
    """Load all valid hardware execution records from the target directory.

    Only records containing '"mode": "hardware"' are loaded.

    Args:
        hardware_dir: Path to directory containing hardware JSON files.

    Returns:
        List of parsed JSON record dictionaries sorted chronologically.
    """
    path = Path(hardware_dir)
    if not path.exists():
        logger.warning(f"Hardware directory does not exist: {path}")
        return []

    records: List[Dict[str, Any]] = []
    for json_file in sorted(path.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                content = json.load(f)
                if content.get("mode") == "hardware":
                    content["_file_name"] = json_file.name
                    records.append(content)
        except Exception as e:
            logger.warning(f"Failed to read/parse {json_file.name}: {e}")

    # Sort chronologically by timestamp if available
    records.sort(key=lambda r: r.get("timestamp", ""))
    return records


def compute_sample_stats(values: List[float]) -> Tuple[Optional[float], Optional[float]]:
    """Calculate mean and sample standard deviation (ddof=1) for a sequence of values."""
    if not values:
        return None, None
    mean_val = float(np.mean(values))
    std_val = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    return round(mean_val, 6), round(std_val, 6)


def aggregate_hardware_results(
    records_or_dir: Union[str, Path, List[Dict[str, Any]]] = "results/hardware"
) -> Dict[str, Any]:
    """Aggregate hardware execution results across benchmarks and variants.

    Args:
        records_or_dir: Directory path or pre-loaded list of hardware records.

    Returns:
        Dictionary keyed by benchmark name, containing aggregated metrics and per-run points.
    """
    if isinstance(records_or_dir, (str, Path)):
        records = load_hardware_records(records_or_dir)
    else:
        records = [r for r in records_or_dir if r.get("mode") == "hardware"]

    if not records:
        return {}

    # Group records by benchmark
    by_benchmark: Dict[str, List[Dict[str, Any]]] = {}
    for rec in records:
        bench = rec.get("benchmark", "unknown")
        by_benchmark.setdefault(bench, []).append(rec)

    aggregated: Dict[str, Any] = {}

    for bench_name, bench_records in by_benchmark.items():
        variants_summary: Dict[str, Any] = {}

        for v_name in VARIANTS_ORDER:
            p_succ_list: List[float] = []
            h_fid_list: List[float] = []
            gates_list: List[int] = []
            two_q_list: List[int] = []
            depth_list: List[int] = []
            run_points: List[Dict[str, Any]] = []

            for run_idx, rec in enumerate(bench_records, start=1):
                v_data = rec.get("variants", {}).get(v_name)
                if not v_data:
                    continue

                p_val = v_data.get("success_probability")
                h_val = v_data.get("hellinger_fidelity")
                pm = v_data.get("post_transpile_metrics", {})

                if p_val is not None:
                    p_succ_list.append(float(p_val))
                if h_val is not None:
                    h_fid_list.append(float(h_val))
                if "total_gates" in pm:
                    gates_list.append(int(pm["total_gates"]))
                if "two_qubit_gates" in pm:
                    two_q_list.append(int(pm["two_qubit_gates"]))
                if "depth" in pm:
                    depth_list.append(int(pm["depth"]))

                run_points.append({
                    "run_idx": run_idx,
                    "job_id": rec.get("job_id"),
                    "backend": rec.get("backend"),
                    "timestamp": rec.get("timestamp"),
                    "success_probability": p_val,
                    "stderr": v_data.get("stderr"),
                    "hellinger_fidelity": h_val,
                    "hellinger_stderr": v_data.get("hellinger_stderr"),
                })

            p_mean, p_std = compute_sample_stats(p_succ_list)
            h_mean, h_std = compute_sample_stats(h_fid_list)

            variants_summary[v_name] = {
                "num_runs": len(run_points),
                "total_gates": int(round(np.mean(gates_list))) if gates_list else None,
                "two_qubit_gates": int(round(np.mean(two_q_list))) if two_q_list else None,
                "depth": int(round(np.mean(depth_list))) if depth_list else None,
                "success_probability_mean": p_mean,
                "success_probability_std": p_std,
                "hellinger_fidelity_mean": h_mean,
                "hellinger_fidelity_std": h_std,
                "run_points": run_points,
            }

        backends = list({r.get("backend") for r in bench_records if r.get("backend")})
        layouts = [r.get("layout") for r in bench_records if r.get("layout")]

        aggregated[bench_name] = {
            "total_runs": len(bench_records),
            "backends": backends,
            "layouts": layouts,
            "variants": variants_summary,
        }

    return aggregated


def print_aggregation_table(aggregated: Dict[str, Any]) -> None:
    """Print formatted ASCII summary tables for all aggregated benchmark results."""
    if not aggregated:
        print("No valid hardware records found to aggregate.")
        return

    print("=" * 90)
    print("IBM QUANTUM HARDWARE EXECUTION - AGGREGATE PERFORMANCE SUMMARY")
    print("=" * 90)

    for bench_name, bench_data in aggregated.items():
        runs = bench_data["total_runs"]
        backends = ", ".join(bench_data["backends"])
        print(f"\nBenchmark: {bench_name} | Total Runs: {runs} | Backend(s): {backends}")
        print("-" * 90)
        print(
            f"{'Variant':12s} | {'Runs':4s} | {'Total Gates':11s} | {'2Q Gates':8s} | {'Depth':6s} | "
            f"{'Success Prob (Mean +/- Std)':27s} | {'Hellinger (Mean +/- Std)':23s}"
        )
        print("-" * 90)

        for v_name, v_stats in bench_data["variants"].items():
            n = v_stats["num_runs"]
            tg = str(v_stats["total_gates"]) if v_stats["total_gates"] is not None else "N/A"
            tq = str(v_stats["two_qubit_gates"]) if v_stats["two_qubit_gates"] is not None else "N/A"
            dp = str(v_stats["depth"]) if v_stats["depth"] is not None else "N/A"

            p_m = v_stats["success_probability_mean"]
            p_s = v_stats["success_probability_std"]
            if p_m is not None:
                p_str = f"{p_m:.4f} +/- {p_s:.4f}"
            else:
                p_str = "N/A"

            h_m = v_stats["hellinger_fidelity_mean"]
            h_s = v_stats["hellinger_fidelity_std"]
            if h_m is not None:
                h_str = f"{h_m:.4f} +/- {h_s:.4f}"
            else:
                h_str = "N/A"

            print(f"{v_name:12s} | {n:4d} | {tg:11s} | {tq:8s} | {dp:6s} | {p_str:27s} | {h_str:23s}")
        print("-" * 90)


def main():
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description="Aggregate IBM Quantum hardware execution results across saved JSON files."
    )
    parser.add_argument(
        "--hardware-dir",
        default="results/hardware",
        help="Path to hardware results directory (default: results/hardware)",
    )
    parser.add_argument(
        "--benchmark",
        default=None,
        help="Filter results to a specific benchmark name",
    )

    args = parser.parse_args()
    aggregated = aggregate_hardware_results(args.hardware_dir)

    if args.benchmark:
        if args.benchmark in aggregated:
            aggregated = {args.benchmark: aggregated[args.benchmark]}
        else:
            print(f"Benchmark '{args.benchmark}' not found in hardware results. Available: {list(aggregated.keys())}")
            sys.exit(1)

    print_aggregation_table(aggregated)


if __name__ == "__main__":
    main()
