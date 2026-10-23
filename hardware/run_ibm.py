"""IBM Quantum execution workflow with fair layout allocation and dry-run safety.

Default mode executes as a dry run using a simulated fake backend (AerSimulator).
Real execution requires the explicit '--submit' CLI flag.
Credentials are only accessed via QiskitRuntimeService() or the local .env file
and are never logged or exposed.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
import numpy as np

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
import qiskit_ibm_runtime.fake_provider as fp

from baselines.qiskit_baseline import qiskit_transpile
from benchmarks.generators import get_benchmark_suite
from metrics.metrics import get_metrics
from optimizer.pipeline import optimize
from simulation.fidelity import hellinger_fidelity_from_counts

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def find_best_layout(backend: Any, num_qubits: int) -> List[int]:
    """Identify a physical qubit path on the backend with minimal 2-qubit gate error.

    Traverses the coupling map using depth-first path exploration, evaluating candidate
    connected chains against target calibration errors. Falls back to a deterministic
    linear slice if calibration data is unavailable.

    Args:
        backend: Target Qiskit backend instance.
        num_qubits: Number of contiguous physical qubits required.

    Returns:
        List of physical qubit indices representing the chosen initial layout.
    """
    total_physical = getattr(backend, "num_qubits", 127)
    if num_qubits <= 0 or num_qubits > total_physical:
        return list(range(min(num_qubits, total_physical)))

    cm = getattr(backend, "coupling_map", None)
    if cm is None:
        return list(range(num_qubits))

    # Identify primary two-qubit basis gate name in target
    target = getattr(backend, "target", None)
    two_q_name = None
    if target is not None:
        for op in target.operation_names:
            try:
                if any(q is not None and len(q) == 2 for q in target[op].keys()):
                    two_q_name = op
                    break
            except Exception:
                continue

    # Search for candidate paths of length num_qubits
    candidates: List[List[int]] = []

    def dfs(curr_path: List[int], visited: set):
        if len(curr_path) == num_qubits:
            candidates.append(list(curr_path))
            return
        last_node = curr_path[-1]
        try:
            neighbors = list(cm.neighbors(last_node))
        except Exception:
            neighbors = []
        for nbr in neighbors:
            if nbr not in visited:
                dfs(curr_path + [nbr], visited | {nbr})
                if len(candidates) >= 200:
                    return

    for start_node in range(total_physical):
        dfs([start_node], {start_node})
        if len(candidates) >= 200:
            break

    if not candidates:
        return list(range(num_qubits))

    if two_q_name is None or target is None:
        return candidates[0]

    # Rank paths by composite two-qubit error
    best_candidate: Optional[List[int]] = None
    lowest_error = float("inf")

    for path in candidates:
        total_err = 0.0
        for i in range(len(path) - 1):
            pair = (path[i], path[i + 1])
            prop = target[two_q_name].get(pair)
            if prop is None or getattr(prop, "error", None) is None:
                prop = target[two_q_name].get((pair[1], pair[0]))
            err = prop.error if (prop and getattr(prop, "error", None) is not None) else 0.01
            total_err += err

        if total_err < lowest_error:
            lowest_error = total_err
            best_candidate = path

    return best_candidate or candidates[0]


def resolve_fake_backend(backend_name: Optional[str] = None) -> Any:
    """Retrieve an offline fake backend instance without cloud calls."""
    if backend_name:
        if hasattr(fp, backend_name):
            cls = getattr(fp, backend_name)
            if callable(cls):
                return cls()
        cleaned = backend_name.replace("ibm_", "").capitalize()
        fake_candidate = f"Fake{cleaned}"
        if hasattr(fp, fake_candidate):
            cls = getattr(fp, fake_candidate)
            if callable(cls):
                return cls()

    return fp.FakeSherbrooke()


def compute_ideal_distribution(circuit: QuantumCircuit) -> Dict[str, float]:
    """Compute the exact ideal measurement distribution via statevector simulation for circuits <= 7 qubits."""
    sv = Statevector.from_instruction(circuit)
    raw_probs = sv.probabilities_dict()
    # Filter negligible floating point amplitudes
    return {str(k): float(v) for k, v in raw_probs.items() if v > 1e-6}


def bootstrap_hellinger_stderr(
    counts: Dict[str, int],
    ideal_counts: Dict[str, int],
    shots: int,
    num_bootstraps: int = 100,
    seed: int = 42,
) -> float:
    """Calculate the standard error of Hellinger fidelity via bootstrap resampling of counts."""
    if not counts or not ideal_counts or shots <= 0:
        return 0.0

    bitstrings = list(counts.keys())
    freqs = np.array([counts[b] for b in bitstrings], dtype=float)
    probs = freqs / shots

    rng = np.random.default_rng(seed)
    samples = rng.multinomial(shots, probs, size=num_bootstraps)
    fidelities = []
    for sample in samples:
        resampled = {b: int(cnt) for b, cnt in zip(bitstrings, sample) if cnt > 0}
        f = hellinger_fidelity_from_counts(resampled, ideal_counts)
        fidelities.append(f)

    return float(round(float(np.std(fidelities)), 6))


def compute_metrics_and_fidelity(
    counts: Dict[str, int],
    shots: int,
    correct_bitstring: Optional[str],
    ideal_distribution: Optional[Dict[str, float]],
    seed: int = 42,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Compute success probability, binomial error, Hellinger fidelity, and bootstrap standard error."""
    p_success: Optional[float] = None
    stderr: Optional[float] = None
    h_fidelity: Optional[float] = None
    h_stderr: Optional[float] = None

    if correct_bitstring:
        clean_target = correct_bitstring.replace(" ", "")
        correct_count = counts.get(clean_target, 0)
        p = float(correct_count / shots)
        p_success = round(p, 6)
        stderr = round(math.sqrt(p * (1.0 - p) / shots), 6)
    elif ideal_distribution:
        # For multi-state ground supports (e.g. GHZ state {'000': 0.5, '111': 0.5}),
        # success is defined as measuring any state in the target support
        matching_count = sum(counts.get(k, 0) for k in ideal_distribution.keys())
        p = float(matching_count / shots)
        p_success = round(p, 6)
        stderr = round(math.sqrt(p * (1.0 - p) / shots), 6)

    if ideal_distribution:
        ideal_counts = {k: int(round(v * shots)) for k, v in ideal_distribution.items()}
        h_fidelity = round(hellinger_fidelity_from_counts(counts, ideal_counts), 6)
        h_stderr = bootstrap_hellinger_stderr(counts, ideal_counts, shots=shots, seed=seed)

    return p_success, stderr, h_fidelity, h_stderr


def run_hardware_workflow(
    benchmark_name: str = "qft_then_inverse_3",
    backend_name: Optional[str] = None,
    shots: int = 2000,
    submit: bool = False,
    seed: int = 42,
    repeats: int = 1,
    max_qpu_seconds: float = 60.0,
    output_dir: str = "results/hardware",
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Execute the four-variant hardware evaluation workflow with QPU usage guards and repeats support.

    Variants evaluated:
        1. original: Qiskit optimization_level=0 to standard basis
        2. ours: optimize(translate_to_basis=True)
        3. qiskit_L1: Qiskit optimization_level=1
        4. qiskit_L3: Qiskit optimization_level=3

    Args:
        benchmark_name: Name of benchmark circuit ('qft_then_inverse_3', 'ghz_3', 'random_seed_0', etc.).
        backend_name: Target backend name (or None for auto-selection of least-busy backend).
        shots: Measurement shot count per variant.
        submit: If True, submits single SamplerV2 jobs to IBM Cloud. If False, runs dry-run simulation.
        seed: Random seed for deterministic simulation and transpilation.
        repeats: Number of times to execute the submission workflow (default: 1).
        max_qpu_seconds: Safety cap on remaining QPU seconds before each submission (default: 60).
        output_dir: Directory where results JSON files are saved.

    Returns:
        Dictionary of results (or list of dictionaries if repeats > 1).
    """
    suite = get_benchmark_suite()
    matched = next((b for b in suite if b["name"] == benchmark_name), None)
    if matched is None:
        raise ValueError(f"Benchmark '{benchmark_name}' not found in suite. Available: {[b['name'] for b in suite]}")

    base_circuit = matched["circuit"]
    num_qubits = matched["qubits"]
    correct_bitstring = matched.get("correct_bitstring")
    ideal_dist = matched.get("ideal_distribution")

    # If ideal distribution is not pre-packaged and qubits <= 7, compute via Statevector
    if ideal_dist is None and num_qubits <= 7:
        logger.info(f"Computing ideal distribution for '{benchmark_name}' via Statevector simulation...")
        ideal_dist = compute_ideal_distribution(base_circuit)

    # For circuits that simplify to |000> (e.g. random_seed_0), set correct_bitstring if 100% in one state
    if correct_bitstring is None and ideal_dist and len(ideal_dist) == 1:
        correct_bitstring = list(ideal_dist.keys())[0]

    # Step 1: Generate the four comparison variants
    logger.info(f"Generating compiler variants for '{benchmark_name}' ({num_qubits} qubits)...")
    v_orig = qiskit_transpile(base_circuit, level=0, seed=seed)
    v_ours = optimize(base_circuit, translate_to_basis=True).optimized_circuit
    v_l1 = qiskit_transpile(base_circuit, level=1, seed=seed)
    v_l3 = qiskit_transpile(base_circuit, level=3, seed=seed)

    variants_raw = {
        "original": v_orig,
        "ours": v_ours,
        "qiskit_L1": v_l1,
        "qiskit_L3": v_l3,
    }

    # Step 2: Add measurement operations
    variants_measured: Dict[str, QuantumCircuit] = {}
    for name, circ in variants_raw.items():
        c_meas = circ.copy()
        if c_meas.num_clbits == 0:
            c_meas.measure_all()
        variants_measured[name] = c_meas

    # Step 3: Backend resolution
    backend: Any
    mode: str
    service: Any = None

    if submit:
        from qiskit_ibm_runtime import QiskitRuntimeService

        logger.info("Connecting to IBM Quantum Cloud via QiskitRuntimeService()...")
        service = QiskitRuntimeService()

        if backend_name:
            backend = service.backend(backend_name)
        else:
            logger.info("Querying least-busy operational backend...")
            backend = service.least_busy(operational=True)

        mode = "hardware"
        logger.info(f"Selected target hardware backend: {backend.name} (qubits: {backend.num_qubits})")
    else:
        backend = resolve_fake_backend(backend_name)
        mode = "dry_run"
        logger.info(f"Dry-run mode active. Using offline device model: {backend.name}")

    # Step 4: Fair physical layout selection (same for all variants and all repeats)
    layout = find_best_layout(backend, num_qubits)
    logger.info(f"Fair initial layout chosen ({len(layout)} physical qubits): {layout}")

    # Step 5: Transpile all variants using identical layout and level 0
    pm = generate_preset_pass_manager(
        optimization_level=0,
        backend=backend,
        initial_layout=layout,
        seed_transpiler=seed,
    )

    isa_circuits: Dict[str, QuantumCircuit] = {}
    post_metrics: Dict[str, Dict[str, int]] = {}

    for name, circ in variants_measured.items():
        isa_circ = pm.run(circ)
        isa_circuits[name] = isa_circ
        post_metrics[name] = get_metrics(isa_circ)

    # Step 6: Execution Loop (supports --repeats N)
    records: List[Dict[str, Any]] = []

    for rep in range(1, repeats + 1):
        if repeats > 1:
            logger.info(f"--- Execution run {rep} of {repeats} ---")

        job_id: str
        counts_map: Dict[str, Dict[str, int]] = {}

        if submit:
            # Check remaining QPU time budget before submission
            try:
                usage = service.usage()
                remaining_sec = usage.get("usage_remaining_seconds", 0)
                limit_reached = usage.get("usage_limit_reached", False)
                logger.info(f"QPU Time Status before job {rep}: {remaining_sec}s remaining (quota cap: {max_qpu_seconds}s).")

                if limit_reached or remaining_sec < max_qpu_seconds:
                    raise RuntimeError(
                        f"Aborting hardware submission: remaining QPU time ({remaining_sec}s) is below "
                        f"the configured safety threshold of {max_qpu_seconds}s (or quota limit reached)."
                    )
            except Exception as ex:
                if "Aborting hardware submission" in str(ex):
                    raise
                logger.warning(f"Could not verify service.usage() before submission: {ex}")

            from qiskit_ibm_runtime import SamplerV2

            sampler = SamplerV2(mode=backend)
            variant_names_ordered = ["original", "ours", "qiskit_L1", "qiskit_L3"]
            pubs = [isa_circuits[name] for name in variant_names_ordered]

            logger.info("Submitting single SamplerV2 job containing all 4 PUBs...")
            job = sampler.run(pubs, shots=shots)
            job_id = job.job_id()
            print(f"Submitted job ID: {job_id}")

            # Polling loop with timeout (max 15 minutes) - Never auto-retry
            import time

            start_time = time.time()
            timeout_seconds = 900
            poll_interval = 10

            while True:
                raw_status = job.status()
                status_name = raw_status.name if hasattr(raw_status, "name") else str(raw_status).upper()
                logger.info(f"Job {job_id} status: {status_name}")
                if status_name in ("DONE", "COMPLETED"):
                    break
                elif status_name in ("ERROR", "CANCELLED"):
                    raise RuntimeError(f"Job {job_id} terminated with failure status: {status_name}")

                if time.time() - start_time > timeout_seconds:
                    raise TimeoutError(f"Job {job_id} timed out after {timeout_seconds}s waiting for completion.")

                time.sleep(poll_interval)

            job_result = job.result()
            for idx, name in enumerate(variant_names_ordered):
                pub_data = job_result[idx].data
                keys = list(pub_data.keys()) if hasattr(pub_data, "keys") else [k for k in dir(pub_data) if not k.startswith("_")]
                key = keys[0]
                meas_obj = pub_data[key] if hasattr(pub_data, "__getitem__") else getattr(pub_data, key)
                counts_map[name] = meas_obj.get_counts()

            # Print usage after each job
            try:
                post_usage = service.usage()
                consumed_sec = post_usage.get("usage_consumed_seconds", "N/A")
                rem_sec = post_usage.get("usage_remaining_seconds", "N/A")
                print(f"QPU Usage after job {job_id}: {consumed_sec}s consumed, {rem_sec}s remaining.")
            except Exception as e_use:
                logger.warning(f"Unable to read post-job usage: {e_use}")
        else:
            # Dry-run AerSimulator execution
            job_id = f"dry_run_sim_{uuid.uuid4().hex[:8]}"
            sim = AerSimulator.from_backend(backend)
            for name, isa_circ in isa_circuits.items():
                result = sim.run(isa_circ, shots=shots, seed_simulator=seed + rep).result()
                counts_map[name] = result.get_counts()

        # Calculate metrics and fidelity per variant
        results_variants: Dict[str, Any] = {}
        for name in ["original", "ours", "qiskit_L1", "qiskit_L3"]:
            counts = counts_map[name]
            p_succ, stderr, h_fid, h_stderr = compute_metrics_and_fidelity(
                counts=counts,
                shots=shots,
                correct_bitstring=correct_bitstring,
                ideal_distribution=ideal_dist,
                seed=seed + rep,
            )
            results_variants[name] = {
                "post_transpile_metrics": post_metrics[name],
                "counts": counts,
                "success_probability": p_succ,
                "stderr": stderr,
                "hellinger_fidelity": h_fid,
                "hellinger_stderr": h_stderr,
            }

        # Build and serialize results JSON
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        record: Dict[str, Any] = {
            "benchmark": benchmark_name,
            "backend": backend.name,
            "job_id": job_id,
            "timestamp": timestamp_iso,
            "shots": shots,
            "layout": layout,
            "mode": mode,
            "repeat_index": rep,
            "total_repeats": repeats,
            "correct_bitstring": correct_bitstring,
            "ideal_distribution": ideal_dist,
            "variants": results_variants,
        }

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        clean_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{benchmark_name}_{backend.name}_{clean_timestamp}_{rep}.json"
        file_path = out_path / output_filename

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)

        logger.info(f"Results successfully saved to: {file_path}")
        records.append(record)

    return records[0] if repeats == 1 else records


def main():
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description="Execute quantum circuit optimization variants on IBM Quantum hardware or dry-run simulation."
    )
    parser.add_argument(
        "--benchmark",
        default="qft_then_inverse_3",
        help="Benchmark name from evaluation suite (e.g. qft_then_inverse_3, ghz_3, random_seed_0)",
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="Target backend name (default: least-busy operational backend for submit, FakeSherbrooke for dry-run)",
    )
    parser.add_argument(
        "--shots",
        type=int,
        default=2000,
        help="Number of measurement shots (default: 2000)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="Number of repeated runs (default: 1)",
    )
    parser.add_argument(
        "--max-qpu-seconds",
        type=float,
        default=60.0,
        help="Safety cap: abort if remaining QPU seconds are below this value (default: 60)",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        default=False,
        help="Submit job to real IBM Quantum cloud backend. If omitted, executes a safe dry run.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for simulation and transpilation (default: 42)",
    )
    parser.add_argument(
        "--output-dir",
        default="results/hardware",
        help="Directory to save output JSON files (default: results/hardware)",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("IBM QUANTUM EVALUATION WORKFLOW")
    print(f"Mode: {'HARDWARE SUBMISSION' if args.submit else 'DRY RUN (SIMULATION)'}")
    print(f"Benchmark: {args.benchmark}")
    print(f"Shots: {args.shots}")
    print(f"Repeats: {args.repeats}")
    print(f"QPU Safety Cap: {args.max_qpu_seconds}s")
    print(f"Seed: {args.seed}")
    print("=" * 70)

    result = run_hardware_workflow(
        benchmark_name=args.benchmark,
        backend_name=args.backend,
        shots=args.shots,
        submit=args.submit,
        seed=args.seed,
        repeats=args.repeats,
        max_qpu_seconds=args.max_qpu_seconds,
        output_dir=args.output_dir,
    )

    records = result if isinstance(result, list) else [result]

    for idx, rec in enumerate(records, start=1):
        print(f"\nExecution Summary (Run {idx}/{len(records)}):")
        print(f"Backend: {rec['backend']}")
        print(f"Job ID: {rec['job_id']}")
        print(f"Physical Layout: {rec['layout']}")
        print("-" * 75)
        print(f"{'Variant':12s} | {'Total Gates':11s} | {'2Q Gates':8s} | {'Depth':6s} | {'Success Prob':18s} | {'Hellinger':12s}")
        print("-" * 75)
        for v_name, v_data in rec["variants"].items():
            m = v_data["post_transpile_metrics"]
            p = v_data["success_probability"]
            err = v_data["stderr"]
            p_str = f"{p:.4f} +/- {err:.4f}" if p is not None else "N/A"
            h_fid = v_data["hellinger_fidelity"]
            h_err = v_data.get("hellinger_stderr", 0.0)
            h_str = f"{h_fid:.4f} +/- {h_err:.4f}" if h_fid is not None else "N/A"
            print(f"{v_name:12s} | {m['total_gates']:11d} | {m['two_qubit_gates']:8d} | {m['depth']:6d} | {p_str:18s} | {h_str:12s}")
        print("-" * 75)


if __name__ == "__main__":
    main()
