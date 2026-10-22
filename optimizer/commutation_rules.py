"""Rules and lookup tables for quantum gate commutation relations."""

from qiskit.circuit import CircuitInstruction


def gates_commute(
    inst1: CircuitInstruction,
    inst2: CircuitInstruction,
) -> bool:
    """Check whether two gate instructions commute.

    Commutation conditions:
    1. Disjoint qubit supports always commute trivially.
    2. Shared single-qubit rotations around identical axes commute (e.g., RZ and RZ).
    3. Diagonal gates (Z, RZ, T, S, CZ) commute with each other.
    4. RZ(theta) on the control qubit of a CX commutes with the CX.
    5. X / RX(theta) on the target qubit of a CX commutes with the CX.
    6. Two CX gates sharing both control and target commute.

    Args:
        inst1: First circuit instruction.
        inst2: Second circuit instruction.

    Returns:
        True if the two instructions are guaranteed to commute, False otherwise.
    """
    # TODO: Implement complete commutation table and parametric angle checks
    return False
