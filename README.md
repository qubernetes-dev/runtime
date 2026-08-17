# q8s.runtime

`q8s.runtime` provides common runtime, provenance, and experiment-tracking capabilities for quantum software.

The library provides a QDK-independent representation of quantum programs and their execution metadata, together with integrations for quantum development kits such as [Qiskit](https://www.ibm.com/quantum/qiskit) and [Qrisp](https://www.qrisp.eu/index.html). This makes it possible to collect and analyse execution and compilation information consistently across different quantum software stacks.

## Installation

Install the core package using:

```bash
pip install q8s.runtime
```

Support for individual quantum development kits can be installed using the corresponding optional dependencies:

```bash
pip install "q8s.runtime[qiskit]"
pip install "q8s.runtime[qrisp]"
```

Multiple integrations can be installed together:

```bash
pip install "q8s.runtime[qiskit,qrisp]"
```

## Integrations

### Qiskit

The Qiskit integration provides adapters for Qiskit objects and automatic experiment tracking through MLflow.

#### MLflow autologging

Qiskit transpilation and execution can be automatically captured by enabling autologging:

```python
import mlflow
from mqt.bench import BenchmarkLevel, get_benchmark
from q8s.runtime.mlflow.qiskit import autolog

autolog()

from iqm.qiskit_iqm.fake_backends.fake_aphrodite import IQMFakeAphrodite
from qiskit.transpiler import generate_preset_pass_manager

mlflow.set_experiment("qiskit-transpilation")


with mlflow.start_run():
    qc = get_benchmark(
        benchmark="qft",
        level=BenchmarkLevel.ALG,
        circuit_size=30,
    )

    backend = IQMFakeAphrodite()

    manager = generate_preset_pass_manager(
        optimization_level=3, backend=backend, seed_transpiler=42
    )

    tqc = manager.run(qc)

    job = backend.run(tqc, shots=1024, memory=True)

    result = job.result()

    result.get_counts()
```

The integration can capture information about the transpilation process, including individual transpiler passes and their associated metadata.

### Qrisp

The Qrisp integration converts Qrisp programs into the common `q8s.runtime` representation, allowing provenance and experiment information produced by Qrisp workflows to be handled using the same model as Qiskit workflows.

```python
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

    pm = PassManager()
    pm += fuse_adjacents
    pm += commute_swaps
    pm += combine_single_qubit_gates

    optimized_qc = pm.run(qc)
```

## Capabilities

### Provenance

`q8s.runtime` uses the **QProv provenance model** to describe the information associated with the lifecycle of a quantum program.

QProv organizes provenance information into four main categories:

| QProv category       | Description                                                       | Qiskit | Qrisp |
| -------------------- | ----------------------------------------------------------------- | :----: | :---: |
| **Quantum Circuit**  | Structure and characteristics of the quantum circuit              |   ◐    |   ◐   |
| **Quantum Computer** | Characteristics of the quantum computer or execution backend      |   -    |   -   |
| **Compilation**      | Transformation of a quantum circuit for a target quantum computer |   ◐    |   ◐   |
| **Execution**        | Information associated with executing the compiled circuit        |   -    |   -   |

The availability of individual provenance attributes depends on the QDK, backend, provider, and application.

### Quantum Circuit

Quantum Circuit provenance describes the structure and characteristics of the quantum circuit being executed.

| QProv  | Provenance attribute | Qiskit | Qrisp |
| ------ | -------------------- | :----: | :---: |
| **Q1** | Gates                |   ✓    |   ✓   |
| **Q2** | Measurements         |   ✓    |   ✓   |
| **Q3** | Execution order      |   -    |   -   |
| **Q4** | Circuit width        |   ✓    |   ✓   |
| **Q5** | Circuit depth        |   ✓    |   ✓   |
| **Q6** | Circuit size         |   ✓    |   ✓   |
| **Q7** | Encoding             |   —    |   —   |

Circuit width represents the number of qubits used by the circuit, circuit depth describes the number of sequential operations required by the circuit, and circuit size describes its number of operations.

### Compilation

Compilation provenance describes how an abstract quantum circuit is transformed into a circuit that can be executed by a particular quantum computer.

| QProv  | Provenance attribute | Qiskit | Qrisp |
| ------ | -------------------- | :----: | :---: |
| **C1** | Qubit assignments    |   ✓    |   ✓   |
| **C2** | Gate mappings        |   ✓    |   ✓   |
| **C3** | Optimisation goal    |   ✓    |   -   |
| **C4** | Random seed          |   ✓    |   -   |
| **C5** | Compilation time     |   ✓    |   ✓   |

In addition to the QProv compilation attributes, `q8s.runtime` toolkit collects **fine-grained compiler provenance**.

For each transpiler pass, the following information can be recorded:

| Compiler provenance | Description                                       | Qiskit | Qrisp |
| ------------------- | ------------------------------------------------- | :----: | :---: |
| **Pass index**      | Position of the pass in the transpilation process |   ✓    |   ✓   |
| **Pass name**       | Transpiler pass name                              |   ✓    |   ✓   |
| **Stage**           | Stage of the staged pass manager                  |   ✓    |   -   |
| **Duration**        | Execution time of the pass                        |   ✓    |   ✓   |
| **Circuit depth**   | Circuit depth after the pass                      |   ✓    |   ✓   |
| **Circuit size**    | Circuit size after the pass                       |   ✓    |   ✓   |

This extends QProv's compilation provenance with information about the internal compilation process and enables reconstruction and visualization of a **transpilation timeline**.

**Legend:** ✓ supported · ◐ dependent on QDK/backend/application · — not currently collected

## References

The provenance model implemented by `q8s.runtime` is based on:

> Weder, B., Breitenbücher, U., Leymann, F., and Wild, K.
> _Integrating quantum computing into workflow modeling and execution._
> IET Quantum Communication.

See the QProv publication for the complete provenance model and definitions.

## License

`q8s.runtime` is licensed under the Apache License 2.0.

## Provenance

### Quantum Computer

Quantum Computer provenance describes the characteristics of the quantum computer on which a circuit is executed.

| QProv   | Provenance attribute      | Qiskit | Qrisp |
| ------- | ------------------------- | :----: | :---: |
| **QC1** | Number of qubits          |   ✓    |   ✓   |
| **QC2** | Decoherence times (T1/T2) |   ◐    |   ◐   |
| **QC3** | Qubit connectivity        |   ✓    |   ✓   |
| **QC4** | Gate set                  |   ✓    |   ✓   |
| **QC5** | Gate fidelities           |   ◐    |   ◐   |
| **QC6** | Gate times                |   ◐    |   ◐   |
| **QC7** | Readout fidelities        |   ◐    |   ◐   |

The availability of hardware properties depends on the selected backend and provider. In particular, calibration information such as decoherence times, gate fidelities, and readout fidelities may not be exposed by every backend.

### Execution

Execution provenance captures information generated when a compiled quantum circuit is executed.

| QProv  | Provenance attribute     | Qiskit | Qrisp |
| ------ | ------------------------ | :----: | :---: |
| **E1** | Input data               |   ✓    |   ✓   |
| **E2** | Output data              |   ✓    |   ✓   |
| **E3** | Number of shots          |   ✓    |   ✓   |
| **E4** | Intermediate results     |   ◐    |   ◐   |
| **E5** | Number of iterations     |   ◐    |   ◐   |
| **E6** | Execution time           |   ✓    |   ✓   |
| **E7** | Readout-error mitigation |   ◐    |   ◐   |

Intermediate results and iteration counts are particularly relevant for hybrid and variational quantum algorithms and are available when exposed by the application or QDK.
