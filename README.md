# Quantum Circuit Gate-Reduction Optimizer

## Project Summary

A classical, explainable quantum circuit gate-reduction optimizer built on Qiskit. The optimizer takes an input `QuantumCircuit`, applies custom modular optimization passes, verifies that the resulting circuit is mathematically and unitarily equivalent to the input, and evaluates gate count and depth reduction against Qiskit's built-in transpiler (`optimization_level=0..3`).

Optimization pipeline:
- **Pass 1 (`CancellationPass`)**: Adjacent self-inverse/inverse gate cancellation (e.g. $H-H$, $X-X$, $CX-CX$) and rotation merging along matching Pauli axes (e.g. $RZ(\theta_1) RZ(\theta_2) \to RZ(\theta_1 + \theta_2)$).
- **Pass 2 (`CommutationPass`)**: Commutation-based rewriting to shift commuting gates across one another, exposing blocked cancellation and merging opportunities.
- **Pass 3 (`RoutingPass`, Stretch Goal)**: Topology-aware routing and SWAP insertion for coupling map constraints.
- **Verification (`is_equivalent`)**: Unitary equivalence checking up to global phase via `Operator.equiv`.
- **Benchmarking & Simulation**: Evaluated against Qiskit baseline levels 0 to 3 under ideal conditions and under noisy simulation using IBM device noise models (via Qiskit Aer and `qiskit_ibm_runtime.fake_provider`).

> **Note**: There is no physical quantum hardware used in this project. All device-level noise experiments are executed via noisy simulation using IBM device noise models.

---

## Setup Instructions

### 1. Prerequisites
- Python 3.12+
- `git`

### 2. Environment Setup
Clone or navigate to the repository:
```bash
cd quantum-optimizer
```

Create and activate a virtual environment:
```bash
# On Linux/macOS
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

## Running Tests

Execute the test suite using `pytest`:
```bash
pytest -q
```

All smoke tests in `tests/test_smoke.py` verify the Day 0 scaffolding, shared interfaces, metrics extraction, equivalence verification, and noisy simulation using IBM device noise models.

---

## Project Structure & Ownership

```
quantum-optimizer/
  README.md
  requirements.txt
  pytest.ini
  .gitignore
  optimizer/      # Core optimization passes, equivalence checking, pipeline
  benchmarks/     # Circuit generators (GHZ, QFT, Bell, random redundant) and QASM files
  metrics/        # Gate count, two-qubit gate count, and depth metrics
  baselines/      # Qiskit transpile baseline at levels 0-3
  simulation/     # Noisy simulation using IBM device noise models and fidelity stubs
  api/            # FastAPI service placeholders
  dashboard/      # Streamlit interactive UI placeholder
  scripts/        # Benchmark runners and figure generators
  tests/          # Test suite (smoke tests, pass unit tests, equivalence tests)
  results/        # Benchmark output records (results.csv tracked)
  docs/           # Documentation assets
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
  - `scripts/`: `run_benchmarks.py`, `make_figures.py`
  - `results/` & `docs/`

---

## Honesty Rules

1. **Equivalence & Determinism First**: No pass is merged until it passes the equivalence checker and the fixed-seed random-circuit test.
2. **Fair Baseline Comparison**: All variants (original, ours, Qiskit) must use the same basis gates, backend, shots and seed when compared.
3. **No Hardcoded Numbers**: Do not hardcode any result numbers anywhere.
4. **Empirical Claims Only**: Claims are limited to what `results/results.csv` shows. No hardware claim; all simulated hardware experiments represent noisy simulation using IBM device noise models.
5. **Verified APIs**: Verify every Qiskit import against the installed version; if an API does not exist, find the correct one instead of guessing.
