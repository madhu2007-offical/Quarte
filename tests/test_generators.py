"""Tests for seeded benchmark circuit generators and QASM export."""

from pathlib import Path
import pytest
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector

from benchmarks.generators import (
    bell,
    get_benchmark_suite,
    get_random_benchmark_circuits,
    ghz,
    grover_small,
    qft,
    qft_then_inverse,
    random_redundant_circuit,
    ripple_carry_adder,
    save_all_benchmarks_to_qasm,
)


def test_random_redundant_circuit_deterministic_seed():
    """Two circuits generated with identical seeds must be identical."""
    qc1 = random_redundant_circuit(n=3, depth=20, seed=123)
    qc2 = random_redundant_circuit(n=3, depth=20, seed=123)
    qc3 = random_redundant_circuit(n=3, depth=20, seed=456)

    # Identical operations
    ops1 = [(inst.operation.name, [qc1.find_bit(q).index for q in inst.qubits]) for inst in qc1.data]
    ops2 = [(inst.operation.name, [qc2.find_bit(q).index for q in inst.qubits]) for inst in qc2.data]
    ops3 = [(inst.operation.name, [qc3.find_bit(q).index for q in inst.qubits]) for inst in qc3.data]

    assert ops1 == ops2
    assert ops1 != ops3


def test_grover_small_ideal_success():
    """grover_small must have correct_bitstring='11' with 100% ideal probability."""
    qc = grover_small()
    assert qc.metadata.get("correct_bitstring") == "11"

    sv = Statevector.from_instruction(qc)
    probs = sv.probabilities_dict()
    assert probs.get("11", 0) > 0.999


def test_qft_then_inverse_ideal_success():
    """qft_then_inverse must reproduce the input bitstring with 100% probability."""
    target = "101"
    qc = qft_then_inverse(3, basis_state=target)
    assert qc.metadata.get("correct_bitstring") == target

    sv = Statevector.from_instruction(qc)
    probs = sv.probabilities_dict()
    assert probs.get(target, 0) > 0.999


def test_ripple_carry_adder_n1():
    """ripple_carry_adder(1) must yield correct_bitstring='1010' with 100% probability."""
    qc = ripple_carry_adder(1)
    assert qc.metadata.get("correct_bitstring") == "1010"

    sv = Statevector.from_instruction(qc)
    probs = sv.probabilities_dict()
    assert probs.get("1010", 0) > 0.999


def test_qasm_export_creates_files(tmp_path):
    """save_all_benchmarks_to_qasm must create valid QASM files for all suite circuits."""
    files = save_all_benchmarks_to_qasm(target_dir=str(tmp_path))
    assert len(files) == 17
    for f in files:
        p = Path(f)
        assert p.exists()
        assert p.stat().st_size > 0
        content = p.read_text(encoding="utf-8")
        assert "OPENQASM 2.0;" in content
