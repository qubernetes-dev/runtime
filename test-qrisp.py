# flake8: noqa: E402

from qrisp import (
    PassManager,
    QuantumCircuit,
    combine_single_qubit_gates,
    commute_swaps,
    fuse_adjacents,
)

from q8s.runtime.mlflow.qrisp import autolog

autolog()

qc = QuantumCircuit(2)
qc.cx(0, 1)
qc.cx(0, 1)  # Self-inverse — will be cancelled
qc.h(0)
qc.h(0)  # Another self-inverse pair

print("Before:", qc, sep="\n")

pm = PassManager()
pm += fuse_adjacents
pm += commute_swaps
pm += combine_single_qubit_gates

optimized_qc = pm.run(qc)
print("After:", optimized_qc, sep="\n")
