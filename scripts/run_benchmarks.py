"""Benchmark execution runner across circuits, compiler variants, and noisy simulation."""

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

# Ensure repository root is in sys.path for direct script execution
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from baselines.qiskit_baseline import generate_variants
from benchmarks.generators import get_benchmark_suite, save_all_benchmarks_to_qasm
from metrics.metrics import get_metrics
from optimizer.cancellation import CancellationPass
from simulation.fidelity import estimated_fidelity, success_probability
from simulation.noisy_sim import run_noisy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_all_benchmarks(
    backend_name: str = "FakeSherbrooke",
    shots: int = 4096,
    seed: int = 42,
    output_csv: str = "results/results.csv",
    save_qasm: bool = True,
) -> pd.DataFrame:
    """Execute benchmark evaluation across all variants and write results.csv.

    Columns in results.csv:
        benchmark, variant, qubits, total_gates, two_qubit_gates, depth, est_fidelity, success_prob

    Args:
        backend_name: Target fake backend for noisy simulation using IBM device noise models.
        shots: Number of measurement shots for noisy simulation.
        seed: Seed for transpiler and simulator.
        output_csv: Output CSV filepath.
        save_qasm: If True, exports all benchmark circuits to benchmarks/qasm/.

    Returns:
        pandas.DataFrame containing benchmark metrics and fidelity.
    """
    if save_qasm:
        logger.info("Exporting benchmark circuits to benchmarks/qasm/ ...")
        save_all_benchmarks_to_qasm("benchmarks/qasm")

    suite = get_benchmark_suite()
    logger.info(f"Loaded {len(suite)} benchmarks in evaluation suite.")

    # Configure our optimizer with CancellationPass
    our_passes = [CancellationPass()]

    rows: List[Dict[str, Any]] = []

    for item in suite:
        benchmark_name = item["name"]
        raw_circuit = item["circuit"]
        qubits = item["qubits"]
        correct_bitstring = item["correct_bitstring"]

        logger.info(f"Processing benchmark '{benchmark_name}' ({qubits} qubits)...")

        # Produce variants under strict fairness rules
        variants = generate_variants(raw_circuit, passes=our_passes, seed=seed)

        # Check eligibility for noisy simulation: <= 7 qubits and known correct bitstring
        is_eligible_for_noisy = (qubits <= 7) and (correct_bitstring is not None)
        if not is_eligible_for_noisy:
            if qubits > 7:
                logger.info(
                    f"  [Noisy Sim Skipped] '{benchmark_name}': {qubits} qubits exceeds 7-qubit threshold."
                )
            elif correct_bitstring is None:
                logger.info(
                    f"  [Noisy Sim Skipped] '{benchmark_name}': No single ground-truth bitstring."
                )

        for variant_name, variant_circuit in variants.items():
            metrics = get_metrics(variant_circuit)

            est_fid_val: Optional[float] = None
            success_prob_val: Optional[float] = None

            if is_eligible_for_noisy:
                try:
                    # Analytical fidelity estimate from backend properties
                    est_fid_val = estimated_fidelity(variant_circuit, backend=backend_name)

                    # Empirical noisy simulation
                    counts = run_noisy(
                        variant_circuit,
                        backend_name=backend_name,
                        shots=shots,
                        seed=seed,
                    )
                    success_prob_val = success_probability(counts, correct_bitstring)
                except Exception as ex:
                    logger.warning(
                        f"  Failed noisy simulation on {benchmark_name} ({variant_name}): {ex}"
                    )

            row = {
                "benchmark": benchmark_name,
                "variant": variant_name,
                "qubits": qubits,
                "total_gates": metrics["total_gates"],
                "two_qubit_gates": metrics["two_qubit_gates"],
                "depth": metrics["depth"],
                "est_fidelity": f"{est_fid_val:.6f}" if est_fid_val is not None else "",
                "success_prob": f"{success_prob_val:.6f}" if success_prob_val is not None else "",
            }
            rows.append(row)

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "benchmark",
        "variant",
        "qubits",
        "total_gates",
        "two_qubit_gates",
        "depth",
        "est_fidelity",
        "success_prob",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Wrote {len(rows)} result rows to {output_csv}")
    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run benchmark suite across all variants.")
    parser.add_argument("--backend", default="FakeSherbrooke", help="Fake backend name")
    parser.add_argument("--shots", type=int, default=4096, help="Simulation shots")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--output", default="results/results.csv", help="Output CSV path")
    args = parser.parse_args()

    df_results = run_all_benchmarks(
        backend_name=args.backend,
        shots=args.shots,
        seed=args.seed,
        output_csv=args.output,
    )
    print("\nBenchmark Evaluation Results Table:")
    print(df_results.to_string(index=False))
