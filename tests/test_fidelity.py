"""Tests for fidelity calculation and noisy simulation metrics."""

import pytest
from qiskit import QuantumCircuit

from simulation.fidelity import (
    estimated_fidelity,
    hellinger_fidelity_from_counts,
    success_probability,
)


def test_hellinger_fidelity_identical_counts_returns_one():
    """Identical distributions (even with different total shots) must yield 1.0 fidelity."""
    counts1 = {"00": 50, "11": 50}
    counts2 = {"00": 500, "11": 500}
    fid = hellinger_fidelity_from_counts(counts1, counts2)
    assert pytest.approx(fid, abs=1e-8) == 1.0


def test_hellinger_fidelity_orthogonal_counts_returns_zero():
    """Completely disjoint measurement distributions must yield 0.0 fidelity."""
    counts1 = {"00": 100}
    counts2 = {"11": 100}
    fid = hellinger_fidelity_from_counts(counts1, counts2)
    assert pytest.approx(fid, abs=1e-8) == 0.0


def test_hellinger_fidelity_empty_counts():
    """Empty counts must return 0.0 without errors."""
    assert hellinger_fidelity_from_counts({}, {"00": 10}) == 0.0
    assert hellinger_fidelity_from_counts({"00": 10}, {}) == 0.0


def test_success_probability_exact_match():
    """Fraction of matching shots must accurately compute."""
    counts = {"101": 800, "000": 200}
    assert pytest.approx(success_probability(counts, "101"), abs=1e-8) == 0.8
    assert pytest.approx(success_probability(counts, "000"), abs=1e-8) == 0.2
    assert pytest.approx(success_probability(counts, "111"), abs=1e-8) == 0.0


def test_estimated_fidelity_physical_scaling():
    """Deeper circuit with more 2-qubit gates must have lower estimated fidelity."""
    qc_short = QuantumCircuit(2)
    qc_short.cx(0, 1)

    qc_deep = QuantumCircuit(2)
    for _ in range(8):
        qc_deep.cx(0, 1)

    fid_short = estimated_fidelity(qc_short, backend="FakeSherbrooke")
    fid_deep = estimated_fidelity(qc_deep, backend="FakeSherbrooke")

    assert 0.0 < fid_deep < fid_short <= 1.0
