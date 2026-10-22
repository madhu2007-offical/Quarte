"""Conservative commutation rules and lookup logic for quantum gate instructions."""

from typing import Set
from qiskit.dagcircuit import DAGOpNode

# Diagonal single-qubit gates (commute with each other and with CX control)
DIAGONAL_GATES: Set[str] = {"z", "s", "sdg", "t", "tdg", "rz", "p"}

# X-type single-qubit gates (commute with CX target)
X_TYPE_GATES: Set[str] = {"x", "rx", "sx", "sxdg"}


def is_safe_unitary_node(node: DAGOpNode) -> bool:
    """Validate whether a node is an unconditioned unitary operation safe for commutation.

    Excludes:
    - Directives: barrier, measure, reset.
    - Gates with classical bits or classical condition registers.
    - Control flow blocks.
    - Parameterized gates with symbolic expressions.

    Args:
        node: DAGOpNode to inspect.

    Returns:
        True if the node is safe to evaluate for commutation, False otherwise.
    """
    if not isinstance(node, DAGOpNode):
        return False
    if node.name in ("barrier", "measure", "reset"):
        return False
    if len(node.cargs) > 0:
        return False
    if getattr(node.op, "condition", None) is not None:
        return False
    if getattr(node, "is_control_flow", None) and node.is_control_flow():
        return False
    if getattr(node, "is_parameterized", None) and node.is_parameterized():
        return False
    return True


def commutes(node_a: DAGOpNode, node_b: DAGOpNode) -> bool:
    """Determine whether two DAGOpNodes commute under conservative algebraic rules.

    Commutation Conditions:
    1. Disjoint qubit supports: qargs(A) and qargs(B) share no qubits -> True.
    2. Two diagonal gates on the same single qubit -> True.
    3. Diagonal gate and CX on its CONTROL qubit -> True.
    4. X-type gate and CX on its TARGET qubit -> True.
    5. Diagonal gate and CZ on either qubit -> True.
    6. Two CX gates sharing only their control qubit -> True.
    7. Two CX gates sharing only their target qubit -> True.

    Explicit Non-Commutation Guards (returns False):
    - Any non-unitary or directive (barrier, measure, reset, classical bits, conditions).
    - Symbolic parameterized gates.
    - Diagonal gate on CX target qubit -> False.
    - X-type gate on CX control qubit -> False.
    - CX(0, 1) and CX(1, 2) (target of one is control of the other) -> False.
    - CX(0, 1) and CX(1, 0) (swapped control and target) -> False.
    - Any other pair not explicitly proven to commute -> False.

    Args:
        node_a: First DAGOpNode.
        node_b: Second DAGOpNode.

    Returns:
        bool: True if node_a and node_b are guaranteed to commute, False otherwise.
    """
    if not is_safe_unitary_node(node_a) or not is_safe_unitary_node(node_b):
        return False

    qargs_a = set(node_a.qargs)
    qargs_b = set(node_b.qargs)

    # Rule 1: Disjoint qubit supports always commute
    if qargs_a.isdisjoint(qargs_b):
        return True

    # Rule 7: Two single-qubit diagonal gates on the same qubit
    if len(node_a.qargs) == 1 and len(node_b.qargs) == 1:
        if node_a.qargs == node_b.qargs:
            if node_a.name in DIAGONAL_GATES and node_b.name in DIAGONAL_GATES:
                return True
            if node_a.name in X_TYPE_GATES and node_b.name in X_TYPE_GATES:
                return True
        return False

    # Rule 2 & 3: Single-qubit gate and CX gate
    if (len(node_a.qargs) == 1 and node_b.name == "cx" and len(node_b.qargs) == 2) or (
        len(node_b.qargs) == 1 and node_a.name == "cx" and len(node_a.qargs) == 2
    ):
        sq_node = node_a if len(node_a.qargs) == 1 else node_b
        cx_node = node_b if len(node_a.qargs) == 1 else node_a

        sq_qubit = sq_node.qargs[0]
        cx_ctrl = cx_node.qargs[0]
        cx_tgt = cx_node.qargs[1]

        # Diagonal on CX control commutes
        if sq_qubit == cx_ctrl:
            return sq_node.name in DIAGONAL_GATES

        # X-type on CX target commutes
        if sq_qubit == cx_tgt:
            return sq_node.name in X_TYPE_GATES

        return False

    # Rule 4: Single-qubit diagonal gate and CZ gate
    if (len(node_a.qargs) == 1 and node_b.name == "cz" and len(node_b.qargs) == 2) or (
        len(node_b.qargs) == 1 and node_a.name == "cz" and len(node_a.qargs) == 2
    ):
        sq_node = node_a if len(node_a.qargs) == 1 else node_b
        cz_node = node_b if len(node_a.qargs) == 1 else node_a
        if sq_node.qargs[0] in cz_node.qargs:
            return sq_node.name in DIAGONAL_GATES
        return False

    # Rule 5 & 6: Two CX gates
    if node_a.name == "cx" and node_b.name == "cx" and len(node_a.qargs) == 2 and len(node_b.qargs) == 2:
        c1, t1 = node_a.qargs[0], node_a.qargs[1]
        c2, t2 = node_b.qargs[0], node_b.qargs[1]

        # Negative checks: cross roles
        if c1 == t2 or c2 == t1:
            return False

        # Rule 5: Shared control, disjoint targets
        if c1 == c2 and t1 != t2:
            return True

        # Rule 6: Shared target, disjoint controls
        if t1 == t2 and c1 != c2:
            return True

        # Identical control and target
        if c1 == c2 and t1 == t2:
            return True

        return False

    # Conservative default
    return False
