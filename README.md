# Quantum Circuit Gate-Reduction Optimizer

## 1. Project Summary

A classical, explainable quantum circuit gate-reduction optimizer built on Qiskit. The optimizer takes an input `QuantumCircuit`, applies custom modular DAG-based optimization passes, verifies that the resulting circuit is mathematically and unitarily equivalent to the input, and evaluates gate count, depth reduction, and fidelity against Qiskit's built-in transpiler (`optimization_level=0..3`).

### Core Optimization Pipeline
- **Pass 1 (`CancellationPass`)**: Operates on Qiskit's `DAGCircuit` to eliminate adjacent self-inverse gates ($H-H$, $X-X$, $CX-CX$, etc.), inverse conjugate pairs ($S-S^\dagger$, $T-T^\dagger$, $SX-SX^\dagger$), compact $SX-SX \to X$, and merge collinear rotation gates along matching Pauli axes ($RZ, RX, RY, P$), removing any rotation with angle $\approx 0 \pmod{2\pi}$. See [docs/pass1_cancellation.md](docs/pass1_cancellation.md).
- **Pass 2 (`CommutationPass`)**: Exploits algebraic commutation rules (disjoint support, diagonal gates on $CX$ controls, $X$-type gates on $CX$ targets, shared controls/targets) to slide gates forward speculatively up to a lookahead horizon. If a slide enables a cancellation or merge, the rewrite is committed; otherwise, all changes are rolled back bit-for-bit. See [docs/pass2_commutation.md](docs/pass2_commutation.md).
- **Unitary Equivalence Verification (`is_equivalent`)**: Uses Qiskit's `Operator(qc).equiv(Operator(target))` to rigorously prove that the optimized circuit is identical up to global phase. Enforces a safety limit of $\le 10$ qubits to prevent state-space memory exhaustion.
- **Evaluation & Baselines**: Compares optimized circuits against Qiskit transpilation levels 0, 1, 2, and 3 in the identical basis $\{rz, sx, x, cx\}$.
- **Statistical Noisy Simulation**: Evaluates circuit execution under `FakeSherbrooke` device noise models across multiple random seeds, tracking Hellinger fidelity and success probability distributions with error bars.

> **Important Note**: There is no physical quantum hardware used in this project. All device-level noise experiments represent **noisy simulation using IBM device noise models** (`FakeSherbrooke` via Qiskit Aer).

---

## 2. Setup Instructions

### Prerequisites
- Python 3.12+
- `git`

### Environment Setup
Clone or navigate to the repository:
```bash
cd quantum-optimizer
```

Create and activate a virtual environment:
```bash
# On Linux / macOS
python -m venv .venv
source .venv/bin/activate

# On Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## 3. How to Run Tests

Execute the complete test suite (95+ unit and integration tests) using `pytest`:
```bash
pytest -q
```

The test suite covers:
- Scaffolding and interface compliance ([`tests/test_smoke.py`](tests/test_smoke.py))
- Hardened equivalence verification and qubit bounds ([`tests/test_equivalence.py`](tests/test_equivalence.py))
- Pass 1 cancellation, rotation merging, and wire adjacency ([`tests/test_cancellation.py`](tests/test_cancellation.py))
- Pass 2 commutation rules, slide lookahead, and bit-for-bit rollback ([`tests/test_commutation.py`](tests/test_commutation.py))
- Randomized circuit optimization fuzzing across 8 seeds ([`tests/test_random_circuits.py`](tests/test_random_circuits.py))
- Structural metrics extraction and depth calculations ([`tests/test_metrics.py`](tests/test_metrics.py))
- Noisy simulation and Hellinger fidelity calculations ([`tests/test_fidelity.py`](tests/test_fidelity.py))
- End-to-end benchmark sweep runner ([`tests/test_benchmarks_runner.py`](tests/test_benchmarks_runner.py))
- FastAPI endpoints and Streamlit dashboard smoke import ([`tests/test_api.py`](tests/test_api.py))

---

## 4. API & Dashboard Launch Commands

### 4.1 Launch FastAPI REST Service
Start the Uvicorn web server:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Endpoint: `http://localhost:8000`
- Interactive Swagger UI: `http://localhost:8000/docs`
- OpenAPI Specification: `http://localhost:8000/openapi.json`

Available endpoints:
- `GET /benchmarks`: List metadata for all 17 built-in benchmark circuits.
- `GET /benchmarks/{name}`: Retrieve circuit details and OpenQASM 2.0 text.
- `POST /optimize`: Submit custom OpenQASM 2.0 or a benchmark name to execute optimization passes and receive verified before/after metrics and QASM output.
- `GET /results`: Return precomputed sweep data from `results/results.csv`.

### 4.2 Launch Streamlit Interactive Dashboard
Start the visual dashboard:
```bash
streamlit run dashboard/app.py --server.port 8501
```
- Dashboard URL: `http://localhost:8501`

The dashboard loads precomputed sweep data from [`results/results.csv`](results/results.csv) immediately on startup and provides interactive circuit diagram rendering, real-time optimization, baseline bar charts, and noisy simulation fidelity error bar visualizations.

---

## 5. Results Summary

All experimental evaluation metrics are dynamically tracked and recorded in [`results/results.csv`](results/results.csv), comprising 119 evaluation rows across 17 benchmark circuits and 7 compiler variants (`original`, `qiskit_L0`, `qiskit_L1`, `qiskit_L2`, `qiskit_L3`, `ours`, and `ours_highlevel`).

A comparative analysis against Qiskit's transpiler (transpiled to the identical basis $\{rz, sx, x, cx\}$) reveals the following empirical performance:

### Head-to-Head Comparison (Ours vs Qiskit Baselines)
- **Against Qiskit Level 0 (`qiskit_L0`)**:
  - **Total Gates**: Wins on 14 circuits, ties on 3 circuits, 0 losses.
  - **Two-Qubit (CX) Gates**: Wins on 6 circuits, ties on 11 circuits, 0 losses.
  - **Circuit Depth**: Wins on 14 circuits, ties on 3 circuits, 0 losses.
- **Against Qiskit Level 1 (`qiskit_L1`)**:
  - **Two-Qubit (CX) Gates**: Matches Qiskit Level 1 on all 17 benchmarks (**17 ties, 0 losses**), confirming that our cancellation and commutation passes capture standard entangling reductions.
  - **Total Gates & Depth**: Wins on 6 circuits with clustered redundant rotations, ties on 5, losses on 6.
- **Against Qiskit Level 2 & Level 3 (`qiskit_L2` / `qiskit_L3`)**:
  - **Two-Qubit (CX) Gates**: Matches L2/L3 on 13 circuits, losses on 4 circuits. Qiskit's high-level KAK unitary resynthesis finds cross-block CX reductions on structured multi-qubit blocks (such as adders and Grover diffusion) that local DAG rewrites cannot synthesize.
  - **Circuit Depth**: Wins on 2 random redundant benchmarks by eliminating commutable redundant pairs that Qiskit's default heuristics schedule differently.
- **Equivalence Verification**: 100% of circuits optimized by our pipeline are unitarily equivalent to their inputs up to global phase (`equivalent=True` for all 17 benchmarks).

For the full benchmark dataset and individual circuit metrics, refer directly to [`results/results.csv`](results/results.csv).

---

## 6. Project Structure & Folder Ownership

```
quantum-optimizer/
  README.md                   # Project overview, setup, instructions, and results
  requirements.txt            # Pinned dependencies
  pytest.ini                  # Pytest configuration
  .gitignore                  # Git exclusions (virtualenvs, results, cache)
  optimizer/                  # Core optimization passes and equivalence engine
    base.py                   # OptimizationPass abstract base interface
    cancellation.py           # Pass 1: inverse pair cancellation & rotation merge
    commutation.py            # Pass 2: speculative commutation sliding & rollback
    commutation_rules.py      # Conservative algebraic commutation relations
    routing.py                # Pass 3: routing interface stub (scoped out)
    equivalence.py            # Unitary equivalence checker (Operator.equiv)
    pipeline.py               # optimize() orchestrator with per-pass telemetry
  benchmarks/                 # Benchmark circuit generators and OpenQASM exports
    generators.py             # Deterministic parameterized benchmark generators
    qasm/                     # Exported OpenQASM 2.0 files
  metrics/                    # Circuit complexity metrics
    metrics.py                # Total gates, 2Q gates, and critical-path depth
  baselines/                  # Qiskit transpilation baselines
    qiskit_baseline.py        # Compiler variants (original, L0-L3, ours)
  simulation/                 # Simulation and fidelity analysis
    noisy_sim.py              # Noisy simulation using IBM device noise models
    fidelity.py               # Hellinger fidelity and success probability
  api/                        # FastAPI REST service
    main.py                   # API routes and application lifespan
    schemas.py                # Pydantic request and response schemas
  dashboard/                  # Interactive visual dashboard
    app.py                    # 6-panel Streamlit application
  scripts/                    # Execution runners
    run_benchmarks.py         # Full evaluation sweep and statistical runner
  results/                    # Empirical evaluation datasets
    results.csv               # 119-row sweep records
  tests/                      # Pytest suite
  docs/                       # Architectural specifications and reports
    pass1_cancellation.md     # Mathematical specification of Pass 1
    pass2_commutation.md      # Mathematical specification of Pass 2
    commutation_rules.md      # Detailed commutation rules and DAG methods
    limitations.md            # Scope boundaries and honesty disclosures
    demo_script.md            # 3-minute live demonstration script
```

### Team Ownership Division
- **Developer A**:
  - `optimizer/`: `base.py`, `cancellation.py`, `commutation.py`, `commutation_rules.py`, `routing.py`, `equivalence.py`, `pipeline.py`
  - `tests/`: `test_smoke.py`, `test_cancellation.py`, `test_commutation.py`, `test_routing.py`, `test_equivalence.py`, `test_random_circuits.py`
- **Developer B**:
  - `benchmarks/`: `generators.py`, `qasm/`
  - `metrics/`: `metrics.py`
  - `baselines/`: `qiskit_baseline.py`
  - `simulation/`: `noisy_sim.py`, `fidelity.py`
  - `api/`: `main.py`, `schemas.py`
  - `dashboard/`: `app.py`
  - `scripts/`: `run_benchmarks.py`
  - `results/` & `docs/`

---

## 7. Honesty Rules

1. **Equivalence & Determinism First**: No pass is committed or merged until it passes unitary equivalence verification and deterministic fixed-seed regression tests.
2. **Fair Baseline Comparison**: All variants (`original`, `ours`, `qiskit_L0`–`L3`) are transpiled to the exact same basis set ($\{rz, sx, x, cx\}$) using identical random seeds, shot counts, and noise models.
3. **No Hardcoded Numbers**: All summary tables, charts, and statistics in the dashboard and API are dynamically derived from [`results/results.csv`](results/results.csv).
4. **Empirical Claims Only (No Hardware Claims)**: Claims are strictly limited to observable results in [`results/results.csv`](results/results.csv). No physical quantum hardware was used; all simulated hardware experiments represent **noisy simulation using IBM device noise models** (`FakeSherbrooke`).
5. **Contextualizing Synthetic Benchmark Gains**: Reductions of up to ~66% in total gates and ~35% in circuit depth achieved on synthetic benchmarks (`random_redundant_circuit_seed_0..7`) demonstrate the limits of DAG simplification on intentionally unoptimized circuits. These figures are **not** general claims for arbitrary production quantum algorithms.
6. **Transparent Limitations**: Known constraints—such as Qiskit L2/L3's advantage on structured circuits via multi-qubit resynthesis and the 10-qubit boundary for unitary matrix equivalence—are openly documented in [docs/limitations.md](docs/limitations.md).
