"""Benchmark execution runner across circuits, compiler variants, and statistical noisy simulation."""

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
from optimizer.equivalence import is_equivalent
from simulation.fidelity import estimated_fidelity, hellinger_fidelity_from_counts, success_probability
from simulation.noisy_sim import run_noisy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SIM_SEEDS: List[int] = [42, 43, 44]


def run_all_benchmarks(
    backend_name: str = "FakeSherbrooke",
    shots: int = 4096,
    seeds: Optional[List[int]] = None,
    seed: Optional[int] = None,
    output_csv: str = "results/results.csv",
    save_qasm: bool = True,
) -> pd.DataFrame:
    """Execute benchmark evaluation across all variants and write results.csv.

    Columns in results.csv:
        benchmark, variant, qubits, total_gates, two_qubit_gates, depth,
        est_fidelity, hellinger_mean, hellinger_std, success_prob_mean, success_prob_std, seeds, equivalent

    Args:
        backend_name: Target fake backend for noisy simulation using IBM device noise models.
        shots: Number of measurement shots for noisy simulation.
        seeds: List of random seeds for statistical noisy simulation runs (defaults to [42, 43, 44]).
        seed: Single seed fallback (backwards compatibility).
        output_csv: Output CSV filepath.
        save_qasm: If True, exports all benchmark circuits to benchmarks/qasm/.

    Returns:
        pandas.DataFrame containing benchmark metrics and fidelity.
    """
    if seeds is None:
        if seed is not None:
            seeds = [seed]
        else:
            seeds = SIM_SEEDS

    if save_qasm:
        logger.info("Exporting benchmark circuits to benchmarks/qasm/ ...")
        save_all_benchmarks_to_qasm("benchmarks/qasm")

    suite = get_benchmark_suite()
    logger.info(f"Loaded {len(suite)} benchmarks in evaluation suite.")

    rows: List[Dict[str, Any]] = []

    for item in suite:
        benchmark_name = item["name"]
        raw_circuit = item["circuit"]
        qubits = item["qubits"]
        ideal_distribution = item.get("ideal_distribution")
        correct_bitstring = item.get("correct_bitstring")

        logger.info(f"Processing benchmark '{benchmark_name}' ({qubits} qubits)...")

        # Produce variants under strict fairness rules (ours = basis, ours_highlevel = highlevel)
        variants = generate_variants(raw_circuit, seed=seeds[0])

        # Noisy simulation eligibility: <= 7 qubits and known ideal distribution
        is_eligible_for_noisy = (qubits <= 7) and (ideal_distribution is not None)
        if not is_eligible_for_noisy:
            if qubits > 7:
                logger.info(
                    f"  [Noisy Sim Skipped] '{benchmark_name}': {qubits} qubits exceeds 7-qubit threshold."
                )
            elif ideal_distribution is None:
                logger.info(
                    f"  [Noisy Sim Skipped] '{benchmark_name}': No deterministic or 50/50 ground-truth distribution."
                )

        # Build ideal counts for Hellinger comparison
        ideal_counts: Optional[Dict[str, int]] = None
        if ideal_distribution is not None:
            ideal_counts = {bs: int(p * shots) for bs, p in ideal_distribution.items()}

        for variant_name, variant_circuit in variants.items():
            metrics = get_metrics(variant_circuit)

            # Equivalence validation
            if variant_name in ("ours", "ours_highlevel"):
                equiv = is_equivalent(raw_circuit, variant_circuit)
                if not equiv:
                    error_msg = (
                        f"CRITICAL EQUIVALENCE FAILURE: Benchmark '{benchmark_name}' "
                        f"variant '{variant_name}' is NOT equivalent to input circuit!"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            else:
                equiv = True

            est_fid_val: Optional[float] = None
            hellinger_mean: Optional[float] = None
            hellinger_std: Optional[float] = None
            success_mean: Optional[float] = None
            success_std: Optional[float] = None
            seed_str = ""

            if is_eligible_for_noisy and ideal_counts is not None:
                try:
                    # Analytical fidelity estimate from backend properties
                    est_fid_val = estimated_fidelity(variant_circuit, backend=backend_name)

                    hellingers: List[float] = []
                    successes: List[float] = []

                    for s in seeds:
                        counts = run_noisy(
                            variant_circuit,
                            backend_name=backend_name,
                            shots=shots,
                            seed=s,
                        )
                        # Hellinger fidelity vs ideal distribution
                        h_fid = hellinger_fidelity_from_counts(counts, ideal_counts)
                        hellingers.append(h_fid)

                        # Success probability in target subspace
                        total_valid = sum(counts.get(b, 0) for b in ideal_distribution)
                        s_prob = total_valid / sum(counts.values()) if sum(counts.values()) > 0 else 0.0
                        successes.append(s_prob)

                    hellinger_mean = float(np.mean(hellingers))
                    hellinger_std = float(np.std(hellingers))
                    success_mean = float(np.mean(successes))
                    success_std = float(np.std(successes))
                    seed_str = ",".join(str(s) for s in seeds)
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
                "hellinger_mean": f"{hellinger_mean:.6f}" if hellinger_mean is not None else "",
                "hellinger_std": f"{hellinger_std:.6f}" if hellinger_std is not None else "",
                "success_prob_mean": f"{success_mean:.6f}" if success_mean is not None else "",
                "success_prob_std": f"{success_std:.6f}" if success_std is not None else "",
                "seeds": seed_str,
                "equivalent": equiv,
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
        "hellinger_mean",
        "hellinger_std",
        "success_prob_mean",
        "success_prob_std",
        "seeds",
        "equivalent",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Wrote {len(rows)} result rows to {output_csv}")
    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run refreshed benchmark sweep.")
    parser.add_argument("--backend", default="FakeSherbrooke", help="Fake backend name")
    parser.add_argument("--shots", type=int, default=4096, help="Simulation shots")
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44], help="Simulation seeds")
    parser.add_argument("--output", default="results/results.csv", help="Output CSV path")
    args = parser.parse_args()

    df_results = run_all_benchmarks(
        backend_name=args.backend,
        shots=args.shots,
        seeds=args.seeds,
        output_csv=args.output,
    )
    print("\nRefreshed Benchmark Evaluation Results Table:")
    print(df_results.to_string(index=False))
