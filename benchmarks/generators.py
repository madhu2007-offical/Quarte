"""Quantum circuit benchmark generators and QASM exporters."""

from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import CDKMRippleCarryAdder
from qiskit.qasm2 import dumps


def bell(measure: bool = False) -> QuantumCircuit:
    """Generate a standard 2-qubit Bell state (|00> + |11>) / sqrt(2).

    No deterministic single measurement bitstring exists.

    Args:
        measure: If True, adds measurement operations.

    Returns:
        QuantumCircuit: 2-qubit Bell circuit.
    """
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    if measure:
        qc.measure_all()
    qc.metadata = {"correct_bitstring": None}
    return qc


def ghz(n: int, measure: bool = False) -> QuantumCircuit:
    """Generate an n-qubit Greenberger-Horne-Zeilinger (GHZ) state.

    No single deterministic bitstring exists (superposition of |0...0> and |1...1>).

    Args:
        n: Number of qubits (>= 1).
        measure: If True, adds measurement operations.

    Returns:
        QuantumCircuit: n-qubit GHZ circuit.
    """
    if n < 1:
        raise ValueError("n must be at least 1.")
    qc = QuantumCircuit(n)
    qc.h(0)
    for i in range(1, n):
        qc.cx(0, i)
    if measure:
        qc.measure_all()
    qc.metadata = {"correct_bitstring": None}
    return qc


def qft(n: int) -> QuantumCircuit:
    """Generate an n-qubit Quantum Fourier Transform (QFT) circuit.

    Equal superposition of all 2^n basis states when input is |0...0>.

    Args:
        n: Number of qubits (>= 1).

    Returns:
        QuantumCircuit: n-qubit QFT circuit.
    """
    if n < 1:
        raise ValueError("n must be at least 1.")
    qc = QuantumCircuit(n)
    for i in range(n):
        qc.h(i)
        for j in range(i + 1, n):
            angle = np.pi / (2 ** (j - i))
            qc.cp(angle, j, i)
    for i in range(n // 2):
        qc.swap(i, n - 1 - i)
    qc.metadata = {"correct_bitstring": None}
    return qc


def qft_then_inverse(n: int, basis_state: Optional[str] = None) -> QuantumCircuit:
    """Prepare a computational basis state, apply QFT, then apply inverse QFT.

    Since QFT^dagger * QFT = Identity, the ideal final state is identically
    the input basis state with 100% deterministic measurement probability.

    Args:
        n: Number of qubits (>= 1).
        basis_state: Target bitstring of length n. Defaults to alternating bits.

    Returns:
        QuantumCircuit: Circuit whose noiseless measurement produces basis_state.
    """
    if n < 1:
        raise ValueError("n must be at least 1.")
    if basis_state is None:
        # Default alternating pattern, e.g. "101" for n=3, "1010" for n=4
        basis_state = "".join("1" if i % 2 == 0 else "0" for i in range(n))

    if len(basis_state) != n:
        raise ValueError(f"basis_state length ({len(basis_state)}) must equal n ({n}).")

    qc = QuantumCircuit(n)
    # Prepare basis state (Qiskit bitstrings are little-endian: index 0 is rightmost bit)
    for i, bit in enumerate(reversed(basis_state)):
        if bit == "1":
            qc.x(i)

    # Forward QFT
    fwd = qft(n)
    qc.compose(fwd, inplace=True)
    # Inverse QFT
    inv = fwd.inverse()
    qc.compose(inv, inplace=True)

    qc.metadata = {"correct_bitstring": basis_state}
    return qc


def grover_small() -> QuantumCircuit:
    """Generate a 2-qubit Grover search circuit targeting marked state |11>.

    With N=4 and M=1, exactly 1 Grover iteration amplifies |11> to 100% ideal probability.

    Returns:
        QuantumCircuit: 2-qubit Grover circuit with correct_bitstring = "11".
    """
    qc = QuantumCircuit(2)
    # Uniform superposition
    qc.h(0)
    qc.h(1)

    # Oracle marking |11> (phase flip via CZ)
    qc.cz(0, 1)

    # Diffuser (inversion about average)
    qc.h(0)
    qc.h(1)
    qc.x(0)
    qc.x(1)
    qc.cz(0, 1)
    qc.x(0)
    qc.x(1)
    qc.h(0)
    qc.h(1)

    qc.metadata = {"correct_bitstring": "11"}
    return qc


def ripple_carry_adder(n: int = 1) -> QuantumCircuit:
    """Generate an n-bit Cuccaro/CDKM ripple carry adder circuit.

    For n=1 (4 qubits: cin=0, a=1, b=1, cout=0):
        Input addition 1 + 1 = 2 (sum bit 0 = 0, cout = 1).
        Expected measurement bitstring (cout b0 a0 cin) is '1010' with 100% probability.
    For n=2 (6 qubits: cin=0, a=1, b=2, cout=0):
        Input addition 1 + 2 = 3 (sum bits b1 b0 = 1 1, cout = 0).
        Expected measurement bitstring is '011010' with 100% probability.

    Args:
        n: Number of operand bits (defaults to 1).

    Returns:
        QuantumCircuit: Ripple-carry adder with known deterministic output bitstring.
    """
    if n not in (1, 2):
        raise ValueError("ripple_carry_adder currently supports n=1 (4 qubits) or n=2 (6 qubits).")

    adder = CDKMRippleCarryAdder(num_state_qubits=n).decompose()
    qc = QuantumCircuit(adder.num_qubits)

    if n == 1:
        # cin=0, a0=1, b0=1, cout=0 -> output '1010'
        qc.x(1)
        qc.x(2)
        expected = "1010"
    else:
        # cin=0, a=1 (a0=1), b=2 (b1=1), cout=0 -> output '011010'
        qc.x(1)
        qc.x(4)
        expected = "011010"

    qc.compose(adder, inplace=True)
    qc.metadata = {"correct_bitstring": expected}
    return qc


def random_redundant_circuit(n: int, depth: int, seed: int = 42) -> QuantumCircuit:
    """Generate a reproducible pseudo-random circuit containing redundancies.

    Allowed gates: H, X, Z, S, Sdg, T, Tdg, CX, RZ.

    Args:
        n: Number of qubits.
        depth: Number of operational layers.
        seed: Random seed for deterministic generation.

    Returns:
        QuantumCircuit: Redundant circuit with correct_bitstring = None.
    """
    if n < 1:
        raise ValueError("n must be at least 1.")
    rng = random.Random(seed)
    qc = QuantumCircuit(n)
    single_gates = ["h", "x", "z", "s", "sdg", "t", "tdg"]

    for _ in range(depth):
        choice = rng.random()
        if choice < 0.28:
            q = rng.randrange(n)
            pair = rng.choice(["h", "x", "z", "s_sdg", "t_tdg", "rz_cancel"])
            if pair in ["h", "x", "z"]:
                getattr(qc, pair)(q)
                getattr(qc, pair)(q)
            elif pair == "s_sdg":
                qc.s(q)
                qc.sdg(q)
            elif pair == "t_tdg":
                qc.t(q)
                qc.tdg(q)
            elif pair == "rz_cancel":
                theta = rng.uniform(0.1, 3.0)
                qc.rz(theta, q)
                qc.rz(-theta, q)
        elif choice < 0.55 and n >= 2:
            q1, q2 = rng.sample(range(n), 2)
            qc.cx(q1, q2)
            if rng.random() < 0.5:
                qc.cx(q1, q2)
        elif choice < 0.78:
            q = rng.randrange(n)
            g = rng.choice(single_gates)
            getattr(qc, g)(q)
        else:
            q = rng.randrange(n)
            theta = rng.uniform(-np.pi, np.pi)
            qc.rz(theta, q)

    qc.metadata = {"correct_bitstring": None}
    return qc


def get_random_benchmark_circuits() -> List[Tuple[str, QuantumCircuit]]:
    """Generate the standard suite of 8 random benchmark circuits with seeds 0 through 7.

    Returns:
        List of (benchmark_name, circuit) tuples.
    """
    benchmarks = []
    for s in range(8):
        name = f"random_seed_{s}"
        # 3 qubits, depth 15, deterministic seed
        circ = random_redundant_circuit(n=3, depth=15, seed=s)
        benchmarks.append((name, circ))
    return benchmarks


def get_benchmark_suite() -> List[Dict[str, Any]]:
    """Assemble the comprehensive suite of benchmark circuits for evaluation.

    Returns:
        List of dicts containing 'name', 'circuit', 'qubits', and 'correct_bitstring'.
    """
    suite: List[Dict[str, Any]] = [
        {"name": "ghz_3", "circuit": ghz(3), "qubits": 3, "correct_bitstring": None},
        {"name": "ghz_8", "circuit": ghz(8), "qubits": 8, "correct_bitstring": None},
        {"name": "qft_3", "circuit": qft(3), "qubits": 3, "correct_bitstring": None},
        {"name": "qft_8", "circuit": qft(8), "qubits": 8, "correct_bitstring": None},
        {"name": "qft_then_inverse_3", "circuit": qft_then_inverse(3, "101"), "qubits": 3, "correct_bitstring": "101"},
        {"name": "bell", "circuit": bell(), "qubits": 2, "correct_bitstring": None},
        {"name": "grover_small", "circuit": grover_small(), "qubits": 2, "correct_bitstring": "11"},
        {"name": "ripple_carry_adder_1", "circuit": ripple_carry_adder(1), "qubits": 4, "correct_bitstring": "1010"},
        {"name": "ripple_carry_adder_2", "circuit": ripple_carry_adder(2), "qubits": 6, "correct_bitstring": "011010"},
    ]

    for name, circ in get_random_benchmark_circuits():
        suite.append({
            "name": name,
            "circuit": circ,
            "qubits": circ.num_qubits,
            "correct_bitstring": circ.metadata.get("correct_bitstring") if circ.metadata else None,
        })

    return suite


def save_all_benchmarks_to_qasm(target_dir: str = "benchmarks/qasm") -> List[str]:
    """Export all benchmark suite circuits as OpenQASM 2 files into target_dir.

    Args:
        target_dir: Directory path where .qasm files will be written.

    Returns:
        List of file paths created.
    """
    output_path = Path(target_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    saved_files: List[str] = []
    suite = get_benchmark_suite()

    for item in suite:
        name = item["name"]
        qc = item["circuit"]
        qasm_str = dumps(qc)
        file_path = output_path / f"{name}.qasm"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(qasm_str)
        saved_files.append(str(file_path))

    return saved_files
