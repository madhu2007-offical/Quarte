OPENQASM 2.0;
include "qelib1.inc";
gate gate_MAJ q0,q1,q2 { cx q0,q1; cx q0,q2; ccx q2,q1,q0; }
gate gate_UMA q0,q1,q2 { ccx q2,q1,q0; cx q0,q2; cx q2,q1; }
qreg q[4];
x q[1];
x q[2];
gate_MAJ q[1],q[2],q[0];
cx q[1],q[3];
gate_UMA q[1],q[2],q[0];