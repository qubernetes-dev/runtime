import mlflow
from mqt.bench import BenchmarkLevel, get_benchmark
from q8s.runtime.mlflow.qiskit import autolog

autolog()

from iqm.qiskit_iqm.fake_backends.fake_aphrodite import IQMFakeAphrodite
from qiskit.transpiler import generate_preset_pass_manager

mlflow.set_experiment("qubernetes-transpilation")

qc = get_benchmark(
    benchmark="qft",
    level=BenchmarkLevel.ALG,
    circuit_size=10,
)

backend = IQMFakeAphrodite()

manager = generate_preset_pass_manager(
    optimization_level=3,
    backend=backend,
)

with mlflow.start_run():

    tqc = manager.run(qc)

    job = backend.run(tqc, shots=1024, memory=True)

    result = job.result()

    result.get_counts()
