# Commutation Rules & DAG Rewrite Specification (Pass 2)

## 1. Commutation Rules & Mathematical Justification

The following conservative commutation relations will be implemented in `optimizer/commutation_rules.py` via `commutes(node_a, node_b) -> bool`:

| Rule # | Gate A | Gate B | Condition / Wire Roles | Mathematical Justification |
| :---: | :--- | :--- | :--- | :--- |
| **R1** | Any unitary $U_A$ | Any unitary $U_B$ | Disjoint qubit supports: $\text{qargs}(A) \cap \text{qargs}(B) = \emptyset$ | $U_A \otimes I$ and $I \otimes U_B$ act on separate tensor factor spaces; $[U_A \otimes I, I \otimes U_B] = 0$. |
| **R2** | Diagonal ($Z, S, S^\dagger, T, T^\dagger, RZ, P$) | $CX(c, t)$ | Single-qubit gate on **control** qubit $c$ only | $CX = \|0\rangle\langle 0\| \otimes I + \|1\rangle\langle 1\| \otimes X$; since $D = d_0 \|0\rangle\langle 0\| + d_1 \|1\rangle\langle 1\|$, $(D \otimes I) CX = CX (D \otimes I)$. |
| **R3** | $X$-type ($X, RX, SX, SX^\dagger$) | $CX(c, t)$ | Single-qubit gate on **target** qubit $t$ only | $X$-type operators commute with $X$: $[U_X, X] = 0$; therefore $(I \otimes U_X) CX = CX (I \otimes U_X)$. |
| **R4** | Diagonal ($Z, S, S^\dagger, T, T^\dagger, RZ, P$) | $CZ(q_1, q_2)$ | Single-qubit gate on **either** qubit ($q_1$ or $q_2$) | $CZ = \text{diag}(1, 1, 1, -1)$ and single-qubit diagonal operators are diagonal in the computational basis; all diagonal operators commute. |
| **R5** | $CX(c, t_1)$ | $CX(c, t_2)$ | Shared **control** qubit $c$, disjoint targets ($t_1 \ne t_2$) | Both gates are diagonal in the control basis and act on disjoint target registers; $[CX_{c, t_1}, CX_{c, t_2}] = 0$. |
| **R6** | $CX(c_1, t)$ | $CX(c_2, t)$ | Shared **target** qubit $t$, disjoint controls ($c_1 \ne c_2$) | Target actions are both Pauli $X$ and commute ($X \cdot X = I$); $[CX_{c_1, t}, CX_{c_2, t}] = 0$. |
| **R7** | Diagonal $D_1$ | Diagonal $D_2$ | Same single qubit | Diagonal matrices in the same basis commute: $\text{diag}(e^{i\alpha_0}, e^{i\alpha_1}) \text{diag}(e^{i\beta_0}, e^{i\beta_1}) = \text{diag}(e^{i(\alpha_0+\beta_0)}, e^{i(\alpha_1+\beta_1)})$. |

---

## 2. Cases Where a Slide Must NOT Happen (Safety Rules)

In any of the following cases, `commutes(node_a, node_b)` **must return `False`**, and no slide will occur:

1. **Diagonal Gate on $CX$ Target**:
   - $Z$-type operations on the target do not commute with $CX$: $[CX, I \otimes Z] \ne 0$ (flips relative phase based on target parity).
2. **$X$-type Gate on $CX$ Control**:
   - $X$-type operations on the control flip the control qubit state, changing when the target $X$ gate activates: $[CX, X \otimes I] \ne 0$.
3. **Non-Commuting Single-Qubit Gates on Same Wire**:
   - E.g., $X$ and $Z$, $H$ and $Z$, $RX$ and $RZ$, $SX$ and $RZ$, $H$ and $X$.
4. **$CX$ Gates with Swapped / Cross Roles**:
   - $CX(0, 1)$ and $CX(1, 0)$ do not commute ($CX_{01} CX_{10} \ne CX_{10} CX_{01}$).
5. **Directives & Classical Instructions**:
   - Barriers (`barrier`), measurements (`measure`), resets (`reset`).
   - Any gate with classical registers/bits (`len(node.cargs) > 0`).
   - Conditioned gates (`node.op.condition is not None`) or dynamic control-flow blocks (`node.is_control_flow()`).
6. **Symbolic Parameters**:
   - Any gate whose parameter is a symbolic `Parameter` or `ParameterExpression` (`node.is_parameterized() == True`).
7. **Pure Reordering That Enables No Cancellation / Merge**:
   - Even if two gates commute, a slide must only be committed if the slide brings a gate adjacent to an inverse partner (cancelling both) or a mergeable rotation (reducing gate count).
   - If the slide does not lead to a strict decrease in gate count within the lookahead window (max 10 gates), the changes must be rolled back.

---

## 3. Verified Qiskit DAG Methods (Installed Qiskit 2.6.0)

All methods below have been verified against the installed `qiskit-2.6.0` environment:

1. `dag.topological_op_nodes()`:
   Iterates through operational gate nodes in valid topological execution order.
2. `dag.edges(nodes=[node])`:
   Inspects wire-by-wire incident edges `(src, dst, wire)` to identify immediate predecessors and successors.
3. `dag.swap_nodes(node1, node2)`:
   Native Qiskit `DAGCircuit` method (`DAGCircuit.swap_nodes(self, /, node1, node2)`) specifically designed to swap two connected nodes due to commutation, rewiring the quantum edges cleanly while maintaining DAG integrity.
4. `dag.remove_op_node(node)`:
   Removes a cancelled node and reconnects incident edges to its predecessors/successors.
5. `dag.substitute_node(node, new_op, inplace=True)`:
   Replaces a rotation node in-place with its merged gate operation.
6. `circuit_to_dag(circuit)` & `dag_to_circuit(dag)`:
   Lossless conversions between `QuantumCircuit` and `DAGCircuit`.
