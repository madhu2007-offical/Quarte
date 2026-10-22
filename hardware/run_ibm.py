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
from typing import Any, Dict, List, Optional, Tuple
import uuid

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from qiskit import QuantumCircuit
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
        # Check direct class in fake_provider
        if hasattr(fp, backend_name):
            cls = getattr(fp, backend_name)
            if callable(cls):
                return cls()
        # Handle prefix e.g. ibm_sherbrooke -> FakeSherbrooke
        cleaned = backend_name.replace("ibm_", "").capitalize()
        fake_candidate = f"Fake{cleaned}"
        if hasattr(fp, fake_candidate):
            cls = getattr(fp, fake_candidate)
            if callable(cls):
                return cls()

    # Default to FakeSherbrooke
    return fp.FakeSherbrooke()


def compute_metrics_and_fidelity(
    counts: Dict[str, int],
    shots: int,
    correct_bitstring: Optional[str],
    ideal_distribution: Optional[Dict[str, float]],
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Compute empirical success probability, binomial standard error, and Hellinger fidelity."""
    p_success: Optional[float] = None
    stderr: Optional[float] = None
    h_fidelity: Optional[float] = None

    if correct_bitstring:
        clean_target = correct_bitstring.replace(" ", "")
        correct_count = counts.get(clean_target, 0)
        p = float(correct_count / shots)
        p_success = round(p, 6)
        stderr = round(math.sqrt(p * (1.0 - p) / shots), 6)

    if ideal_distribution:
        # Scale ideal distribution by shots to produce ideal counts
        ideal_counts = {k: int(round(v * shots)) for k, v in ideal_distribution.items()}
        h_fidelity = round(hellinger_fidelity_from_counts(counts, ideal_counts), 6)

    return p_success, stderr, h_fidelity


def run_hardware_workflow(
    benchmark_name: str = "qft_then_inverse_3",
    backend_name: Optional[str] = None,
    shots: int = 2000,
    submit: bool = False,
    seed: int = 42,
    output_dir: str = "results/hardware",
) -> Dict[str, Any]:
    """Execute the four-variant hardware evaluation workflow under fair transpile conditions.

    Variants evaluated:
        1. original: Qiskit optimization_level=0 to standard basis
        2. ours: optimize(translate_to_basis=True)
        3. qiskit_L1: Qiskit optimization_level=1
        4. qiskit_L3: Qiskit optimization_level=3

    Fairness rule:
        A single physical layout is selected for the backend and applied identically
        to every variant using generate_preset_pass_manager(optimization_level=0).

    Args:
        benchmark_name: Name of benchmark circuit from get_benchmark_suite().
        backend_name: Target backend name (or None for auto-selection).
        shots: Measurement shot count.
        submit: If True, submits a single SamplerV2 job to IBM Cloud. If False, runs dry-run simulation.
        seed: Random seed for deterministic simulation and transpilation.
        output_dir: Directory where results JSON is saved.

    Returns:
        Structured dictionary containing run metadata and evaluation results.
    """
    suite = get_benchmark_suite()
    matched = next((b for b in suite if b["name"] == benchmark_name), None)
    if matched is None:
        raise ValueError(f"Benchmark '{benchmark_name}' not found in suite. Available: {[b['name'] for b in suite]}")

    base_circuit = matched["circuit"]
    num_qubits = matched["qubits"]
    correct_bitstring = matched.get("correct_bitstring")
    ideal_dist = matched.get("ideal_distribution")

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
    job_id: str

    if submit:
        # Submit mode: Real IBM Cloud execution via QiskitRuntimeService
        from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2

        logger.info("Connecting to IBM Quantum Cloud via QiskitRuntimeService()...")
        service = QiskitRuntimeService()

        if backend_name:
            backend = service.backend(backend_name)
        else:
            logger.info("Querying least-busy operational backend...")
            backend = service.least_busy(operational=True)

        mode = "hardware"
        logger.info(f"Selected target hardware backend: {backend.name}")
    else:
        # Dry-run mode: Local simulation via Fake backend without cloud calls
        backend = resolve_fake_backend(backend_name)
        mode = "dry_run"
        job_id = f"dry_run_sim_{uuid.uuid4().hex[:8]}"
        logger.info(f"Dry-run mode active. Using offline device model: {backend.name}")

    # Step 4: Fair physical layout selection
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

    # Step 6: Execution
    counts_map: Dict[str, Dict[str, int]] = {}

    if submit:
        from qiskit_ibm_runtime import SamplerV2

        sampler = SamplerV2(mode=backend)
        variant_names_ordered = ["original", "ours", "qiskit_L1", "qiskit_L3"]
        pubs = [isa_circuits[name] for name in variant_names_ordered]

        logger.info("Submitting single SamplerV2 job containing all 4 PUBs...")
        job = sampler.run(pubs, shots=shots)
        job_id = job.job_id()
        print(f"Submitted job ID: {job_id}")

        # Polling loop with timeout (max 15 minutes)
        import time

        start_time = time.time()
        timeout_seconds = 900
        poll_interval = 10

        while True:
            status = job.status()
            logger.info(f"Job {job_id} status: {status}")
            if status in ("DONE", "COMPLETED"):
                break
            elif status in ("ERROR", "CANCELLED"):
                raise RuntimeError(f"Job {job_id} terminated with failure status: {status}")

            if time.time() - start_time > timeout_seconds:
                raise TimeoutError(f"Job {job_id} timed out after {timeout_seconds}s waiting for completion.")

            time.sleep(poll_interval)

        job_result = job.result()
        for idx, name in enumerate(variant_names_ordered):
            pub_data = job_result[idx].data
            # Extract measurement counts from first available classical register
            key = list(pub_data.keys())[0]
            counts_map[name] = pub_data[key].get_counts()
    else:
        # Dry-run AerSimulator execution
        sim = AerSimulator.from_backend(backend)
        for name, isa_circ in isa_circuits.items():
            result = sim.run(isa_circ, shots=shots, seed_simulator=seed).result()
            counts_map[name] = result.get_counts()

    # Step 7: Calculate fidelity and binomial error per variant
    results_variants: Dict[str, Any] = {}
    for name in ["original", "ours", "qiskit_L1", "qiskit_L3"]:
        counts = counts_map[name]
        p_succ, stderr, h_fid = compute_metrics_and_fidelity(
            counts=counts,
            shots=shots,
            correct_bitstring=correct_bitstring,
            ideal_distribution=ideal_dist,
        )
        results_variants[name] = {
            "post_transpile_metrics": post_metrics[name],
            "counts": counts,
            "success_probability": p_succ,
            "stderr": stderr,
            "hellinger_fidelity": h_fid,
        }

    # Step 8: Build and serialize results JSON
    timestamp_iso = datetime.now(timezone.utc).isoformat()
    record: Dict[str, Any] = {
        "benchmark": benchmark_name,
        "backend": backend.name,
        "job_id": job_id,
        "timestamp": timestamp_iso,
        "shots": shots,
        "layout": layout,
        "mode": mode,
        "correct_bitstring": correct_bitstring,
        "variants": results_variants,
    }

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    clean_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{benchmark_name}_{backend.name}_{clean_timestamp}.json"
    file_path = out_path / output_filename

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    logger.info(f"Results successfully saved to: {file_path}")
    return record


def main():
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(
        description="Execute quantum circuit optimization variants on IBM Quantum hardware or dry-run simulation."
    )
    parser.add_argument(
        "--benchmark",
        default="qft_then_inverse_3",
        help="Benchmark name from evaluation suite (default: qft_then_inverse_3)",
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

    print("=" * 65)
    print("IBM QUANTUM EVALUATION WORKFLOW")
    print(f"Mode: {'HARDWARE SUBMISSION' if args.submit else 'DRY RUN (SIMULATION)'}")
    print(f"Benchmark: {args.benchmark}")
    print(f"Shots: {args.shots}")
    print(f"Seed: {args.seed}")
    print("=" * 65)

    record = run_hardware_workflow(
        benchmark_name=args.benchmark,
        backend_name=args.backend,
        shots=args.shots,
        submit=args.submit,
        seed=args.seed,
        output_dir=args.output_dir,
    )

    print("\nExecution Summary:")
    print(f"Backend: {record['backend']}")
    print(f"Job ID: {record['job_id']}")
    print(f"Physical Layout: {record['layout']}")
    print("-" * 65)
    print(f"{'Variant':12s} | {'Total Gates':11s} | {'2Q Gates':8s} | {'Depth':6s} | {'Success Prob':18s}")
    print("-" * 65)
    for v_name, v_data in record["variants"].items():
        m = v_data["post_transpile_metrics"]
        p = v_data["success_probability"]
        err = v_data["stderr"]
        p_str = f"{p:.4f} +/- {err:.4f}" if p is not None else "N/A"
        print(f"{v_name:12s} | {m['total_gates']:11d} | {m['two_qubit_gates']:8d} | {m['depth']:6d} | {p_str:18s}")
    print("-" * 65)


if __name__ == "__main__":
    main()
