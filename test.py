import q8s.runtime
from mqt.bench import BenchmarkLevel, get_benchmark

from iqm.qiskit_iqm.fake_backends.fake_aphrodite import IQMFakeAphrodite

from q8s.runtime.mlflow.qiskit import autolog
from q8s.runtime.tracking import MLflowTranspilationManager

autolog()

print("q8s.runtime version:", q8s.runtime.__version__)

qc = get_benchmark(
    benchmark="ghz",
    level=BenchmarkLevel.ALG,
    circuit_size=12,
)

backend = IQMFakeAphrodite()

manager = MLflowTranspilationManager(
    tracking_uri="http://127.0.0.1:5000",
    experiment_name="qubernetes-transpilation",
    optimization_level=3,
    backend=backend,
)

tqc = manager.transpile(qc, run_name="qft-8-opt3")
