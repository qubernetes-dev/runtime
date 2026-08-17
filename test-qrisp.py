# flake8: noqa: E402

import mlflow

from q8s.runtime.mlflow.qrisp import autolog

autolog()

from qrisp import (
    PassManager,
    QuantumCircuit,
    combine_single_qubit_gates,
    commute_swaps,
    fuse_adjacents,
)

from q8s.runtime.mlflow.qrisp.autologging import get_context
from q8s.runtime.qprov.graphs import plot_transpilation_timeline

mlflow.set_experiment("qrisp-transpilation")

with mlflow.start_run():

    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    qc.cx(0, 1)  # Self-inverse — will be cancelled
    qc.h(0)
    qc.h(0)  # Another self-inverse pair

    # print("Before:", qc, sep="\n")

    pm = PassManager()
    pm += fuse_adjacents
    pm += commute_swaps
    pm += combine_single_qubit_gates

    optimized_qc = pm.run(qc)
    # print("After:", optimized_qc, sep="\n")

    # fig = plot_transpilation_timeline(
    #     passes=get_context().compilation.passes,
    #     figsize=(16, 8),
    # )

    # fig.savefig("transpilation_timeline.png", dpi=300, bbox_inches="tight")
