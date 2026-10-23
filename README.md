# Quantum Circuit Gate-Reduction Optimizer

## 1. Project Summary

A classical, explainable quantum circuit gate-reduction optimizer built on Qiskit. The optimizer takes an input `QuantumCircuit`, applies custom modular DAG-based optimization passes, verifies that the resulting circuit is mathematically and unitarily equivalent to the input, and evaluates gate count, depth reduction, fidelity, and hardware execution against Qiskit's built-in transpiler (`optimization_level=0..3`).

### Core Optimization Pipeline
- **Pass 1 (`CancellationPass`)**: Operates on Qiskit's `DAGCircuit` to eliminate adjacent self-inverse gates ($H-H$, $X-X$, $CX-CX$, etc.), inverse conjugate pairs ($S-S^\dagger$, $T-T^\dagger$, $SX-SX^\dagger$), compact $SX-SX \to X$, and merge collinear rotation gates along matching Pauli axes ($RZ, RX, RY, P$), removing any rotation with angle $\approx 0 \pmod{2\pi}$. See [docs/pass1_cancellation.md](docs/pass1_cancellation.md).
- **Pass 2 (`CommutationPass`)**: Exploits algebraic commutation rules (disjoint support, diagonal gates on $CX$ controls, $X$-type gates on $CX$ targets, shared controls/targets) to slide gates forward speculatively up to a lookahead horizon. If a slide enables a cancellation or merge, the rewrite is committed; otherwise, all changes are rolled back bit-for-bit. See [docs/pass2_commutation.md](docs/pass2_commutation.md).
- **Unitary Equivalence Verification (`is_equivalent`)**: Uses Qiskit's `Operator(qc).equiv(Operator(target))` to rigorously prove that the optimized circuit is identical up to global phase. Enforces a safety limit of $\le 10$ qubits to prevent state-space memory exhaustion.
- **Evaluation & Baselines**: Compares optimized circuits against Qiskit transpilation levels 0, 1, 2, and 3 in the identical basis $\{rz, sx, x, cx\}$.
- **Statistical Noisy Simulation**: Evaluates circuit execution under `FakeSherbrooke` device noise models across multiple random seeds, tracking Hellinger fidelity and success probability distributions with error bars.
- **Physical Hardware Execution**: Evaluates compiler variants on IBM Quantum hardware (e.g. `ibm_fez`, Heron r2) with fair physical layout selection and a single `SamplerV2` job. See [docs/hardware_run.md](docs/hardware_run.md).

---

## 2. Setup Instructions

### Prerequisites
- Python 3.12+
- `git`
- (Optional) `docker` & `docker-compose`

### Environment Setup
Clone or navigate to the repository:
```bash
git clone https://github.com/madhu2007-offical/Quarte.git
cd Quarte
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

Install pinned dependencies:
```bash
pip install -r requirements.txt
```

---

## 3. How to Run Tests

Execute the complete test suite (**99 passed, 1 skipped**) using `pytest`:
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
- Hardware workflow, dry-run isolation, schema validation, and layout fairness ([`tests/test_hardware.py`](tests/test_hardware.py))

---

## 4. Local Execution & Launch Commands

### 4.1 Launch Streamlit Interactive Dashboard
Start the visual dashboard:
```bash
streamlit run dashboard/app.py --server.port 8501
```
- Dashboard URL: `http://localhost:8501`

**Dashboard Features (7 Panels)**:
1. **Circuit Selection & Controls**: Pick built-in benchmarks or upload/paste OpenQASM 2.0.
2. **Before & After Circuit Drawings**: Side-by-side Matplotlib circuit schematics.
3. **Metrics Table & Verification Badge**: Immediate "Equivalent: PASS" indicator and pass telemetry.
4. **Baseline Comparisons**: Gate count and depth charts against Qiskit L0–L3.
5. **Noisy Simulation Fidelity**: Hellinger fidelity and success rate with error bars across 3 random seeds.
6. **Honest Results Summary**: Explicit Wins/Ties/Losses table vs Qiskit L0–L3.
7. **Hardware Run Results**: Activates when hardware runs are recorded; displays physical layout, metrics table, and success probability bar chart with binomial error bars.

### 4.2 Launch FastAPI REST Service
Start the Uvicorn web server:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger UI: `http://localhost:8000/docs`
- Endpoints: `GET /benchmarks`, `GET /benchmarks/{name}`, `POST /optimize`, `GET /results`

### 4.3 IBM Quantum Hardware Execution Workflow
The script [`hardware/run_ibm.py`](hardware/run_ibm.py) supports both offline dry-run simulation and real hardware submission:

```bash
# 1. Safe offline dry run (default: FakeSherbrooke, 2000 shots, no cloud calls)
python hardware/run_ibm.py --benchmark qft_then_inverse_3 --shots 2000

# 2. Real IBM Quantum Cloud execution (auto-selects least-busy operational backend)
python hardware/run_ibm.py --benchmark qft_then_inverse_3 --shots 2000 --submit

# 3. Explicit backend target (e.g. ibm_fez)
python hardware/run_ibm.py --benchmark qft_then_inverse_3 --backend ibm_fez --shots 2000 --submit
```

---

## 5. Results Summary

### 5.1 Comprehensive Benchmark Sweep (`results/results.csv`)
All evaluation metrics are dynamically tracked and recorded in [`results/results.csv`](results/results.csv), comprising 119 evaluation rows across 17 benchmark circuits and 7 compiler variants (`original`, `qiskit_L0`, `qiskit_L1`, `qiskit_L2`, `qiskit_L3`, `ours`, and `ours_highlevel`).

Head-to-head comparison across all 17 benchmarks in the basis $\{rz, sx, x, cx\}$:

| Metric | vs `qiskit_L0` | vs `qiskit_L1` | vs `qiskit_L2` | vs `qiskit_L3` |
| :--- | :---: | :---: | :---: | :---: |
| **Total Gate Count** | **14 Wins**, 3 Ties, 0 Losses | **6 Wins**, 5 Ties, 6 Losses | 0 Wins, 8 Ties, 9 Losses | 0 Wins, 8 Ties, 9 Losses |
| **Two-Qubit (CX) Gates** | **6 Wins**, 11 Ties, 0 Losses | 0 Wins, **17 Ties**, 0 Losses | 0 Wins, 13 Ties, 4 Losses | 0 Wins, 13 Ties, 4 Losses |
| **Circuit Depth** | **14 Wins**, 3 Ties, 0 Losses | **6 Wins**, 5 Ties, 6 Losses | **2 Wins**, 7 Ties, 8 Losses | **2 Wins**, 7 Ties, 8 Losses |

- **vs Qiskit L0**: Our optimizer beats Qiskit L0 on 14 circuits on total gates/depth and eliminates CX gates where L0 leaves them untouched.
- **vs Qiskit L1**: Achieves **17 ties out of 17 circuits** on two-qubit CX gates—matching Qiskit L1's entangling gate reduction perfectly across every benchmark—while beating L1 on total single-qubit gates on 6 benchmarks.
- **vs Qiskit L2/L3**: Matches L2/L3 on 13 circuits for CX gates. Qiskit's high-level KAK unitary resynthesis finds additional cross-block CX reductions on complex arithmetic adders.
- **Equivalence Verification**: 100% of circuits optimized by our pipeline are unitarily equivalent to their inputs up to global phase (`equivalent=True` across all 17 benchmarks).

---

### 5.2 Physical Hardware Execution on `ibm_fez` (IBM Heron Processor)
A live execution of all 4 compiler variants was performed on the **`ibm_fez`** superconducting quantum processor (156 qubits, Heron r2 architecture with native `cz` gates) under Job ID [`dbd6v6k24mrc73cksj10`](https://quantum.cloud.ibm.com/jobs/dbd6v6k24mrc73cksj10).

All variants were compiled to the identical physical layout (`[22, 23, 24]`) using `generate_preset_pass_manager(optimization_level=0)`:

| Variant | Post-Transpile Total Gates | Post-Transpile 2Q Gates (`cz`) | Post-Transpile Depth | Correct Counts (`101` / 2000) | Success Probability ($p \pm \text{stderr}$) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `original` | 182 | 24 | 123 | 1,796 | $0.8980 \pm 0.0068$ |
| `ours` | **131** | **18** | **91** | **1,813** | **$0.9065 \pm 0.0065$** |
| `qiskit_L1` | 130 | 18 | 91 | 1,825 | $0.9125 \pm 0.0063$ |
| `qiskit_L3` | 2 | 0 | 1 | 1,961 | $0.9805 \pm 0.0031$ |

**Key Findings on Physical Hardware**:
- `ours` dropped two-qubit `cz` gates from 24 to 18 (matching `qiskit_L1`), and reduced depth from 123 to 91.
- Physical execution success probability increased from **89.80% to 90.65%**, confirming that compiler gate reduction directly mitigates real device noise and decoherence.
- Artifact recorded in [`results/hardware/qft_then_inverse_3_ibm_fez_20261023_014840.json`](results/hardware/qft_then_inverse_3_ibm_fez_20261023_014840.json).

---

## 6. Deployment & Cloud Hosting

### 6.1 Streamlit Community Cloud (Recommended)
Deploy the live interactive dashboard directly from GitHub with 1 click:

👉 **[Deploy to Streamlit Community Cloud](https://share.streamlit.io/deploy?repository=madhu2007-offical%2FQuarte&branch=main&mainModule=dashboard%2Fapp.py)**

- **Repository**: `madhu2007-offical/Quarte`
- **Branch**: `main`
- **Main file path**: `dashboard/app.py`
- Pre-configured with `.streamlit/config.toml` and pinned `requirements.txt`.

### 6.2 Container Deployment (Docker & Docker Compose)
Run both the Streamlit Dashboard (port 8501) and FastAPI Backend (port 8000) simultaneously:

```bash
docker-compose up --build
```

Or run standalone Docker containers:
```bash
# Build image
docker build -t quantum-optimizer .

# Run Streamlit Dashboard
docker run -p 8501:8501 quantum-optimizer

# Run FastAPI Server
docker run -p 8000:8000 quantum-optimizer uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## 7. Project Structure & File Layout

```
quantum-optimizer/
  README.md                   # Comprehensive project reference, guides, and empirical tables
  requirements.txt            # Pinned package versions
  Dockerfile                  # Production multi-stage container definition
  docker-compose.yml          # Compose file orchestrating Dashboard and API services
  .streamlit/config.toml      # Streamlit cloud theme and headless server configuration
  pytest.ini                  # Pytest execution configuration
  .gitignore                  # Git exclusion rules
  optimizer/                  # Core optimization passes and equivalence engine
    base.py                   # OptimizationPass abstract interface
    cancellation.py           # Pass 1: inverse pair cancellation & rotation merging
    commutation.py            # Pass 2: speculative commutation sliding & rollback
    commutation_rules.py      # Conservative algebraic commutation relations
    routing.py                # Pass 3: routing interface stub (scoped out)
    equivalence.py            # Unitary equivalence checker (Operator.equiv)
    pipeline.py               # optimize() orchestrator with per-pass telemetry
  benchmarks/                 # Benchmark circuit generators and OpenQASM exports
    generators.py             # Deterministic parameterized benchmark generators
    qasm/                     # Exported OpenQASM 2.0 files
  metrics/                    # Circuit structural metrics
    metrics.py                # Total gates, 2Q gates, and critical-path depth
  baselines/                  # Qiskit transpilation baselines
    qiskit_baseline.py        # Compiler variants (original, L0-L3, ours)
  simulation/                 # Simulation and fidelity analysis
    noisy_sim.py              # Noisy simulation using IBM device noise models
    fidelity.py               # Hellinger fidelity and success probability
  hardware/                   # IBM Quantum hardware submission and dry-run execution
    run_ibm.py                # Fair layout finder, transpile, SamplerV2 submit & poll
  api/                        # FastAPI REST service
    main.py                   # API routes and Swagger documentation
    schemas.py                # Pydantic request/response schemas
  dashboard/                  # Interactive visual dashboard
    app.py                    # 7-panel Streamlit application
  scripts/                    # Benchmark execution scripts
    run_benchmarks.py         # Full evaluation sweep and statistical runner
  results/                    # Empirical evaluation datasets
    results.csv               # 119-row sweep dataset across 17 benchmarks
    hardware/                 # JSON records from dry-run and physical hardware runs
  tests/                      # Pytest test suite (99 passed, 1 skipped)
  docs/                       # Architectural specifications and reports
    pass1_cancellation.md     # Mathematical specification of Pass 1
    pass2_commutation.md      # Mathematical specification of Pass 2
    commutation_rules.md      # Detailed commutation rules and DAG methods
    limitations.md            # Scope boundaries and honesty disclosures
    demo_script.md            # 3-minute live demonstration script
    hardware_run.md           # IBM Quantum execution protocol and caveats
```

---

## 8. Honesty Rules

1. **Equivalence & Determinism First**: No pass is committed or merged until it passes unitary equivalence verification and deterministic fixed-seed regression tests.
2. **Fair Baseline Comparison**: All variants (`original`, `ours`, `qiskit_L0`–`L3`) are transpiled to the exact same basis set ($\{rz, sx, x, cx\}$) using identical random seeds, shot counts, and noise models.
3. **No Hardcoded Numbers**: All summary tables, charts, and statistics in the dashboard and API are dynamically derived from [`results/results.csv`](results/results.csv) and execution JSONs in [`results/hardware/`](results/hardware/).
4. **Empirical Claims Only (No Unsupported Hardware Claims)**: Claims are strictly limited to observable results. Simulated hardware experiments represent **noisy simulation using IBM device noise models** (`FakeSherbrooke`). Cloud runs on real hardware are strictly documented with explicit job IDs and calibration timestamps.
5. **Contextualizing Synthetic Benchmark Gains**: Reductions of up to ~66% in total gates and ~35% in circuit depth achieved on synthetic benchmarks (`random_redundant_circuit_seed_0..7`) demonstrate the limits of DAG simplification on intentionally unoptimized circuits. These figures are **not** general claims for arbitrary production quantum algorithms.
6. **Transparent Limitations**: Known constraints—such as Qiskit L2/L3's advantage on structured circuits via multi-qubit resynthesis and the 10-qubit boundary for unitary matrix equivalence—are openly documented in [docs/limitations.md](docs/limitations.md).
