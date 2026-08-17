# flake8: noqa: E402

import mlflow

from q8s.runtime.mlflow.qrisp import autolog

autolog()

from iqm.qiskit_iqm.fake_backends.fake_aphrodite import IQMFakeAphrodite
from iqm.qrisp_iqm import create_iqm_pass_manager
from qrisp import (
    Clbit,
    QuantumCircuit,
    Qubit,
)


def build_demo_circuit() -> QuantumCircuit:
    """Build a small demo circuit with 2-qubit interactions.

    https://docs.iqm.tech/iqm-client/user_guide_qrisp/plasma_sabre_tutorial.html#demo-circuit.
    """
    qc = QuantumCircuit()

    # Give logical qubits distinctive names
    for i in range(4):
        qc.add_qubit(Qubit("original_qb_" + str(i)))

    for i in range(4):
        qc.add_clbit(Clbit("c" + str(i)))

    qc.h(0)
    qc.cx(0, 1)
    qc.ry(0.7, 2)
    qc.cz(1, 2)
    qc.cx(2, 3)
    qc.s(1)
    qc.cy(0, 2)

    # Add measurements for execution workflows
    qc.measure(qc.qubits, qc.clbits)
    return qc


mlflow.set_experiment("qrisp-transpilation")

backend = IQMFakeAphrodite()

connectivity = backend.target.build_coupling_map()

with mlflow.start_run():
    qc = build_demo_circuit()

    pm = create_iqm_pass_manager(connectivity=connectivity)

    optimized_qc = pm.run(qc)
