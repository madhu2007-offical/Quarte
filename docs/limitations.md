# Project Scope, Known Limitations & Honesty Disclosures

This document outlines the architectural boundaries, theoretical limits, and honest performance disclosures of the Quantum Circuit Gate-Reduction Optimizer.

---

## 1. Architectural Scope & Omission of Routing

### Why Physical Routing Was Cut
In the original 3-day project roadmap, Pass 3 was designated as a topological routing pass. During Day 1 architectural planning, routing was intentionally scoped out for the following engineering reasons:
1. **Logical vs. Physical Optimization Separation**:
   Our project's core contribution is explainable, rule-based gate reduction on **logical circuits** via DAG cancellation and commutation sliding.
2. **Coupling Map SWAP Overhead**:
   Hardware-aware routing requires mapping logical qubits to a physical hardware coupling graph (e.g., IBM's 127-qubit heavy-hex lattice) by inserting SWAP gates. A naive or unoptimized routing pass can increase two-qubit gate count by $3\times$ to $5\times$ simply to satisfy hardware adjacency constraints, which directly conflicts with and obscures gate-reduction benchmarking.
3. **Prioritizing Hardened Equivalence & Commutation**:
   Engineering resources were focused on zero-defect correctness: provable unitary equivalence verification, wire-by-wire DAG invariants, and speculative lookahead sliding with bit-for-bit rollback.

---

## 2. Noisy Simulation Using IBM Device Noise Models Only

### Clarification on Experimental Setup
- **Simulation Environment**: All noise studies and fidelity estimates are performed strictly via **noisy simulation using IBM device noise models** (`FakeSherbrooke` via Qiskit Aer).
- **Noise Model Properties**: The noise model replicates gate errors, readout errors, thermal relaxation ($T_1$), and dephasing ($T_2$) from calibrated IBM quantum hardware, but all calculations run on classical x86_64 host machines.

---

## 3. Resynthesis Comparison: Why Qiskit L2/L3 Outperforms Us on Structured Circuits

Our optimizer operates via **local and semi-local DAG rewrites**:
- Cancelling adjacent or commutable inverse pairs
- Merging collinear rotation gates
- Sliding commuting gates across non-interacting wires

### Where Qiskit L2 & L3 Win
Qiskit's optimization levels 2 and 3 do not merely perform pattern-matching rewrites; they execute **unitary resynthesis**:
- **KAK (Cartan) Decomposition**: Collapses any arbitrary 2-qubit unitary subcircuit into a canonical form containing at most 3 $CX$ gates and 1-qubit rotations.
- **Block Consolidation (`ConsolidateBlocks`)**: Collects multi-gate subgraphs into dense unitary matrices and resynthesizes them using analytical algorithms.
- **Clifford+T & Adder Synthesis**: Synthesizes structured arithmetic blocks (e.g., full adders, ripple-carry adders, and Grover diffusion operators) using specialized multi-qubit synthesis templates.

Because our optimizer does not perform full unitary matrix resynthesis:
- On **structured circuits** (such as `ripple_carry_adder` and `grover_small`), Qiskit L2 and L3 discover cross-block cancellations that cannot be expressed as simple pairwise commutations.
- On these benchmarks, our optimizer matches Qiskit L1 on two-qubit gates, but Qiskit L2 and L3 achieve lower two-qubit gate counts.

---

## 4. State-Space Constraints on Equivalence Checking ($\le 10$ Qubits)

### Exponential Unitary Matrix Explosion
Unitary equivalence verification is implemented in `optimizer/equivalence.py::is_equivalent` via Qiskit's `Operator(qc).equiv(Operator(target))` up to global phase.

An $n$-qubit quantum circuit corresponds to a unitary matrix $U \in \mathbb{C}^{2^n \times 2^n}$:
- **$n = 4$**: $16 \times 16$ complex matrix $\approx 4$ KB
- **$n = 8$**: $256 \times 256$ complex matrix $\approx 1$ MB
- **$n = 10$**: $1024 \times 1024$ complex matrix $\approx 16$ MB (computation time $\approx 0.1\text{s}$)
- **$n = 14$**: $16384 \times 16384$ complex matrix $\approx 4$ GB
- **$n = 16$**: $65536 \times 65536$ complex matrix $\approx 64$ GB (exceeds standard host RAM)
- **$n = 30$**: Exceeds all accessible supercomputing memory

### Practical Safeguard
To guarantee fast REST API response times and protect against out-of-memory crashes:
- Direct unitary equivalence checking is strictly enforced for circuits with **$\le 10$ qubits**.
- Any request to `/optimize` or `is_equivalent` for circuits with $> 10$ qubits is cleanly rejected with an explicit error explaining the state-space constraint.

---

## 5. Contextualizing Benchmark Reduction Numbers

In evaluation sweeps on synthetic redundant benchmarks (`random_redundant_circuit_seed_0..7`):
- Total gate counts dropped by up to **~66%**.
- Circuit depths dropped by up to **~35%**.

### Important Honesty Disclosure
These high percentage reductions occur because those specific synthetic benchmarks were intentionally generated with dense clusters of redundant inverse pairs and commutable rotation sequences to benchmark the outer limits of DAG simplification.

**These figures are NOT general claims for arbitrary production quantum algorithms.**
- On production algorithms that are already compiled to canonical minimal representations (such as optimized Quantum Fourier Transforms or variational ansatzes like QAOA/UCCSD), reduction percentages will be substantially lower or zero.
- All comparative figures presented in the dashboard and reports are directly derived from [`results/results.csv`](../results/results.csv) without manual extrapolation.
