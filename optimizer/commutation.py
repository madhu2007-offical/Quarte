"""Pass 2: Commutation-based rewriting pass on Qiskit DAGCircuit."""

from typing import Dict, List, Optional, Tuple
import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import XGate
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.dagcircuit import DAGCircuit, DAGOpNode

from optimizer.base import OptimizationPass
from optimizer.cancellation import (
    ADJOINT_PAIRS,
    ROTATION_CLASSES,
    ROTATION_GATES,
    SELF_INVERSE_1Q,
    SELF_INVERSE_2Q_ORDERED,
    SELF_INVERSE_2Q_SYMMETRIC,
    get_wire_successors,
    is_zero_angle,
)
from optimizer.commutation_rules import commutes, is_safe_unitary_node


def can_swap_nodes(dag: DAGCircuit, node_a: DAGOpNode, node_b: DAGOpNode) -> bool:
    """Check whether node_a directly connects to node_b on all shared quantum wires.

    Ensures there are no intervening operations on any shared wires between node_a and node_b.

    Args:
        dag: DAGCircuit instance.
        node_a: Predecessor node.
        node_b: Candidate successor node.

    Returns:
        bool: True if node_a has direct outgoing edges to node_b on all shared wires.
    """
    shared_wires = set(node_a.qargs) & set(node_b.qargs)
    if not shared_wires:
        return False

    succs = {}
    for src, dst, wire in dag.edges(nodes=[node_a]):
        if src == node_a and wire in shared_wires:
            succs[wire] = dst

    if len(succs) != len(shared_wires):
        return False

    return all(dst == node_b for dst in succs.values())


def check_reduction_partner(
    dag: DAGCircuit,
    current: DAGOpNode,
) -> Optional[Tuple[str, DAGOpNode]]:
    """Determine whether current node is directly adjacent to an inverse or mergeable partner.

    Args:
        dag: DAGCircuit instance.
        current: Active sliding node.

    Returns:
        Tuple of (action_type, partner_node) if a reduction is possible, None otherwise.
    """
    succs = get_wire_successors(dag, current)
    if len(succs) != len(current.qargs):
        return None
    if not all(isinstance(d, DAGOpNode) for d in succs.values()):
        return None

    unique_succs = set(succs.values())
    if len(unique_succs) != 1:
        return None

    partner = next(iter(unique_succs))
    if not is_safe_unitary_node(partner):
        return None
    if len(partner.qargs) != len(current.qargs):
        return None

    # Rule 1a: Inverse cancellation
    if current.name in SELF_INVERSE_1Q and partner.name == current.name and current.qargs == partner.qargs:
        return ("cancel", partner)
    if (current.name, partner.name) in ADJOINT_PAIRS and current.qargs == partner.qargs:
        return ("cancel", partner)
    if (
        current.name in SELF_INVERSE_2Q_ORDERED
        and partner.name == current.name
        and current.qargs == partner.qargs
    ):
        return ("cancel", partner)
    if (
        current.name in SELF_INVERSE_2Q_SYMMETRIC
        and partner.name == current.name
        and set(current.qargs) == set(partner.qargs)
    ):
        return ("cancel", partner)

    # Rule 1b: Rotation merging
    if current.name in ROTATION_GATES and partner.name == current.name and current.qargs == partner.qargs:
        if not current.is_parameterized() and not partner.is_parameterized():
            return ("merge_rot", partner)

    # Rule 1a extension: SX - SX -> X
    if current.name == "sx" and partner.name == "sx" and current.qargs == partner.qargs:
        return ("merge_sx", partner)

    return None


def apply_reduction(
    dag: DAGCircuit,
    current: DAGOpNode,
    action: str,
    partner: DAGOpNode,
    tol: float = 1e-9,
) -> None:
    """Apply graph reduction for adjacent partner nodes on the DAG.

    Args:
        dag: DAGCircuit instance.
        current: Active node.
        action: Reduction action ('cancel', 'merge_rot', 'merge_sx').
        partner: Partner node.
        tol: Tolerance for zero-angle checks mod 2*pi.
    """
    if action == "cancel":
        dag.remove_op_node(current)
        dag.remove_op_node(partner)
    elif action == "merge_rot":
        summed = float(current.params[0]) + float(partner.params[0])
        if is_zero_angle(summed, tol=tol):
            dag.remove_op_node(current)
            dag.remove_op_node(partner)
        else:
            dag.substitute_node(current, ROTATION_CLASSES[current.name](summed), inplace=True)
            dag.remove_op_node(partner)
    elif action == "merge_sx":
        dag.substitute_node(current, XGate(), inplace=True)
        dag.remove_op_node(partner)


class CommutationPass(OptimizationPass):
    """Pass 2: Commutation-based rewriting on Qiskit DAGCircuit.

    Sliding Principle:
    - For each gate, looks ahead along its quantum wires up to a bounded window.
    - Slides it past gates that commute with it ONLY IF doing so enables an inverse
      cancellation or rotation merge with a downstream partner.
    - Does NOT perform pure reordering that enables no reduction.
    - If no reduction is unlocked, all swaps are rolled back in reverse order,
      preserving the exact circuit bit-for-bit.
    """

    name: str = "commutation"

    def __init__(
        self,
        lookahead_limit: int = 10,
        max_iterations: int = 20,
        tol: float = 1e-9,
    ) -> None:
        """Initialize CommutationPass.

        Args:
            lookahead_limit: Maximum gate depth to lookahead along wires (defaults to 10).
            max_iterations: Maximum iterations to find commuting rewrites (defaults to 20).
            tol: Tolerance for numeric angle zero modulo 2*pi checks.
        """
        self.lookahead_limit = lookahead_limit
        self.max_iterations = max_iterations
        self.tol = tol

    def run(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Execute commutation-based rewriting pass on the input circuit.

        Args:
            circuit: Input QuantumCircuit.

        Returns:
            Optimized QuantumCircuit with commuting gates slid to enable cancellations.
        """
        dag = circuit_to_dag(circuit)

        for _ in range(self.max_iterations):
            changed = False

            for node in list(dag.topological_op_nodes()):
                if not is_safe_unitary_node(node):
                    continue

                swapped_history: List[DAGOpNode] = []
                curr = node

                for step in range(self.lookahead_limit):
                    # Check if sliding brought curr adjacent to a reduction partner
                    if swapped_history:
                        reduction = check_reduction_partner(dag, curr)
                        if reduction is not None:
                            action, partner = reduction
                            apply_reduction(dag, curr, action, partner, tol=self.tol)
                            changed = True
                            break

                    # Look for immediate successors to swap past
                    succs = get_wire_successors(dag, curr)
                    candidates = [d for d in set(succs.values()) if isinstance(d, DAGOpNode)]

                    swapped_this_step = False
                    for cand in candidates:
                        if commutes(curr, cand) and can_swap_nodes(dag, curr, cand):
                            dag.swap_nodes(curr, cand)
                            swapped_history.append(cand)
                            swapped_this_step = True
                            break

                    if not swapped_this_step:
                        break

                if changed:
                    break

                # Rollback if no cancellation or merge was achieved
                if swapped_history:
                    for s in reversed(swapped_history):
                        dag.swap_nodes(s, curr)

            if not changed:
                break

        return dag_to_circuit(dag)
