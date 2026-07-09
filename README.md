# q8s.runtime

A runtime library for q8s workloads.

## Installation

You can install the q8s.runtime library using pip:

```bash
pip install q8s.runtime
```

## Features

### Qiskit autologging to MLflow

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
