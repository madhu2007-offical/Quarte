OPENQASM 2.0;
include "qelib1.inc";
gate gate_MAJ q0,q1,q2 { cx q0,q1; cx q0,q2; ccx q2,q1,q0; }
gate gate_UMA q0,q1,q2 { ccx q2,q1,q0; cx q0,q2; cx q2,q1; }
qreg q[6];
x q[1];
x q[4];
gate_MAJ q[1],q[3],q[0];
gate_MAJ q[2],q[4],q[1];
cx q[2],q[5];
gate_UMA q[2],q[4],q[1];
gate_UMA q[1],q[3],q[0];