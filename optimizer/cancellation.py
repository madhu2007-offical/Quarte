"""Pass 1: Gate cancellation and rotation merging operating on Qiskit's DAGCircuit."""

from typing import Dict, Optional, Set, Tuple
import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import Parameter, ParameterExpression
from qiskit.circuit.library import PhaseGate, RXGate, RYGate, RZGate
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.dagcircuit import DAGCircuit, DAGOpNode

from optimizer.base import OptimizationPass

# Single-qubit self-inverse gates: G * G = I
SELF_INVERSE_1Q: Set[str] = {"h", "x", "y", "z"}

# Two-qubit self-inverse gates requiring exact control/target qubit ordering
SELF_INVERSE_2Q_ORDERED: Set[str] = {"cx"}

# Two-qubit self-inverse gates symmetric with respect to qubit order
SELF_INVERSE_2Q_SYMMETRIC: Set[str] = {"cz", "swap"}

# Adjoint pairs where G1 * G2 = I and G2 * G1 = I on the same qubit
ADJOINT_PAIRS: Set[Tuple[str, str]] = {
    ("s", "sdg"),
    ("sdg", "s"),
    ("t", "tdg"),
    ("tdg", "t"),
}

# Single-qubit rotation families that merge along the same axis
ROTATION_GATES: Set[str] = {"rz", "rx", "ry", "p"}

ROTATION_CLASSES = {
    "rz": RZGate,
    "rx": RXGate,
    "ry": RYGate,
    "p": PhaseGate,
}


def is_zero_angle(angle: float, tol: float = 1e-9) -> bool:
    """Check whether a rotation angle is congruent to 0 mod 2*pi within tolerance.

    Args:
        angle: Numeric rotation angle in radians.
        tol: Absolute tolerance for numeric comparison. Defaults to 1e-9.

    Returns:
        True if angle is ~0 mod 2*pi, False otherwise.
    """
    rem = (float(angle) + np.pi) % (2.0 * np.pi) - np.pi
    return abs(rem) < tol


def is_safe_unitary_op(node: DAGOpNode) -> bool:
    """Validate whether a DAG node is a pure, unconditioned unitary operation.

    Enforces safety rules:
    - Excludes directives: barrier, measure, reset.
    - Excludes operations with classical registers or classical conditions.
    - Excludes dynamic control-flow blocks.

    Args:
        node: Node from the DAGCircuit.

    Returns:
        True if the node is safe to cancel or merge, False otherwise.
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
    return True


def get_wire_successors(dag: DAGCircuit, node: DAGOpNode) -> Dict[object, object]:
    """Retrieve the direct successor node on each quantum wire of the given node.

    Args:
        dag: DAGCircuit instance.
        node: Source DAGOpNode.

    Returns:
        Dictionary mapping each qubit wire in node.qargs to its immediate successor in the DAG.
    """
    succs = {}
    for src, dst, wire in dag.edges(nodes=[node]):
        if src == node and wire in node.qargs:
            succs[wire] = dst
    return succs


class CancellationPass(OptimizationPass):
    """Pass 1: Gate cancellation and rotation merging on Qiskit DAGCircuit.

    Rewrite Rules:
    - Rule 1a (Inverse pairs):
        Cancels directly adjacent self-inverse gates (H-H, X-X, Y-Y, Z-Z,
        CX-CX with matching control/target, CZ-CZ, SWAP-SWAP) and adjoint pairs
        (S-Sdg, Sdg-S, T-Tdg, Tdg-T).
    - Rule 1b (Rotation merging & identity elimination):
        Merges adjacent 1-qubit rotations along the same axis (RZ, RX, RY, P)
        into a single rotation with the summed angle.
        Eliminates any rotation whose angle evaluates to ~0 mod 2*pi (tol=1e-9).
        Skips gates with symbolic Parameters.

    Safety Invariants:
    - Never cancels across barriers, measurements, resets, or classical conditions.
    - Two gates are adjacent only if nothing else touches any of their qubits between them.
    - CX(c, t) and CX(t, c) are not inverses and are never cancelled.
    """

    name: str = "cancellation"

    def __init__(self, max_iterations: int = 50, tol: float = 1e-9) -> None:
        """Initialize CancellationPass.

        Args:
            max_iterations: Maximum loop iterations to find fixed-point cancellations.
            tol: Numeric tolerance for zero-angle checks mod 2*pi.
        """
        self.max_iterations = max_iterations
        self.tol = tol

    def run(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Execute cancellation and rotation merging pass on the input circuit.

        Converts the circuit to a DAGCircuit, applies rewrites repeatedly until
        a fixed point is reached or max_iterations is exhausted, and returns the
        reconstructed QuantumCircuit.

        Args:
            circuit: Input QuantumCircuit.

        Returns:
            Optimized QuantumCircuit with inverse gates cancelled and rotations merged.
        """
        dag = circuit_to_dag(circuit)

        for _ in range(self.max_iterations):
            changed = False

            # Phase 1: Standalone identity rotation elimination (~0 mod 2*pi)
            for node in dag.topological_op_nodes():
                if not is_safe_unitary_op(node):
                    continue
                if node.name in ROTATION_GATES and not node.is_parameterized():
                    if len(node.params) > 0:
                        param = node.params[0]
                        if isinstance(param, (int, float, np.number)) and not isinstance(
                            param, (Parameter, ParameterExpression)
                        ):
                            if is_zero_angle(float(param), tol=self.tol):
                                dag.remove_op_node(node)
                                changed = True
                                break
            if changed:
                continue

            # Phase 2: Adjacent pair cancellation and rotation merging
            for node in dag.topological_op_nodes():
                if not is_safe_unitary_op(node):
                    continue

                succs = get_wire_successors(dag, node)
                # Verify that all qubit wires have a direct successor
                if len(succs) != len(node.qargs):
                    continue
                # Verify that all wire successors are operational gate nodes (not output nodes)
                if not all(isinstance(dst, DAGOpNode) for dst in succs.values()):
                    continue
                # Verify that all shared qubit wires point to the exact same successor node
                unique_succs = set(succs.values())
                if len(unique_succs) != 1:
                    continue

                succ_node = next(iter(unique_succs))
                if not is_safe_unitary_op(succ_node):
                    continue

                # Verify qubit support matches exactly
                if len(succ_node.qargs) != len(node.qargs) or set(succ_node.qargs) != set(node.qargs):
                    continue

                # Rule 1a: Inverse gate pair cancellation
                can_cancel = False
                if node.name in SELF_INVERSE_1Q and succ_node.name == node.name:
                    can_cancel = True
                elif (node.name, succ_node.name) in ADJOINT_PAIRS:
                    can_cancel = True
                elif (
                    node.name in SELF_INVERSE_2Q_ORDERED
                    and succ_node.name == node.name
                    and node.qargs == succ_node.qargs
                ):
                    can_cancel = True
                elif (
                    node.name in SELF_INVERSE_2Q_SYMMETRIC
                    and succ_node.name == node.name
                    and set(node.qargs) == set(succ_node.qargs)
                ):
                    can_cancel = True

                if can_cancel:
                    dag.remove_op_node(node)
                    dag.remove_op_node(succ_node)
                    changed = True
                    break

                # Rule 1b: Rotation merging on identical single-qubit rotation gates
                if (
                    node.name in ROTATION_GATES
                    and succ_node.name == node.name
                    and node.qargs == succ_node.qargs
                ):
                    # Skip if either gate has symbolic parameters
                    if node.is_parameterized() or succ_node.is_parameterized():
                        continue
                    p1 = node.params[0]
                    p2 = succ_node.params[0]
                    if isinstance(p1, (Parameter, ParameterExpression)) or isinstance(
                        p2, (Parameter, ParameterExpression)
                    ):
                        continue

                    angle1 = float(p1)
                    angle2 = float(p2)
                    summed_angle = angle1 + angle2

                    if is_zero_angle(summed_angle, tol=self.tol):
                        dag.remove_op_node(node)
                        dag.remove_op_node(succ_node)
                    else:
                        new_gate = ROTATION_CLASSES[node.name](summed_angle)
                        dag.substitute_node(node, new_gate, inplace=True)
                        dag.remove_op_node(succ_node)
                    changed = True
                    break

            if not changed:
                break

        return dag_to_circuit(dag)
