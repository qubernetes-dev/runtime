import time
import json
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Any

import mlflow
from qiskit import QuantumCircuit
import qiskit
from qiskit.transpiler import StagedPassManager, generate_preset_pass_manager
from qiskit.transpiler.passes import TrivialLayout

from q8s.runtime.mlflow.qiskit.autologging import get_context


@dataclass
class MLflowTranspilationManager:
    tracking_uri: str
    experiment_name: str = "qiskit-transpilation"
    optimization_level: int = 1
    backend: Any | None = None
    basis_gates: list[str] | None = None
    coupling_map: Any | None = None

    def __post_init__(self):
        mlflow.set_tracking_uri(self.tracking_uri)
        mlflow.set_experiment(self.experiment_name)

    def transpile(
        self, circuit: QuantumCircuit, run_name: str | None = None
    ) -> QuantumCircuit:
        with mlflow.start_run(run_name=run_name):
            self._log_input(circuit)

            mlflow.log_params(
                {
                    "optimization_level": self.optimization_level,
                    "backend": getattr(self.backend, "name", None) or str(self.backend),
                    "basis_gates": json.dumps(self.basis_gates),
                    "num_qubits_input": circuit.num_qubits,
                }
            )

            pass_manager: StagedPassManager = generate_preset_pass_manager(
                optimization_level=self.optimization_level,
                # layout_method=TrivialLayout,
                backend=self.backend,
                basis_gates=self.basis_gates,
                coupling_map=self.coupling_map,
            )

            pass_times = {}

            def callback(pass_, dag, time, property_set, count):
                name = pass_.__class__.__name__
                pass_times[f"{count:03d}_{name}"] = time
                mlflow.log_metric(f"pass_time_{name}", time, step=count)
                mlflow.log_metric(f"pass_depth_{name}", dag.depth(), step=count)
                mlflow.log_metric(f"pass_size_{name}", dag.size(), step=count)

            start = time.perf_counter()
            transpiled = pass_manager.run(circuit)
            elapsed = time.perf_counter() - start

            self._log_output(circuit, transpiled, elapsed)
            self._log_artifacts(circuit, transpiled)

            return transpiled

    def _log_input(self, circuit: QuantumCircuit):
        mlflow.log_metrics(
            {
                "input_depth": circuit.depth(),
                "input_size": circuit.size(),
                "input_width": circuit.width(),
                "input_num_qubits": circuit.num_qubits,
                "input_num_clbits": circuit.num_clbits,
            }
        )

        for gate, count in circuit.count_ops().items():
            mlflow.log_metric(f"input_gate_{gate}", count)

    def _log_output(
        self,
        original: QuantumCircuit,
        transpiled: QuantumCircuit,
        elapsed: float,
    ):
        mlflow.log_metrics(
            {
                "transpilation_time_s": elapsed,
                "output_depth": transpiled.depth(),
                "output_size": transpiled.size(),
                "output_width": transpiled.width(),
                "output_num_qubits": transpiled.num_qubits,
                "output_num_clbits": transpiled.num_clbits,
                "depth_delta": transpiled.depth() - original.depth(),
                "size_delta": transpiled.size() - original.size(),
            }
        )

        for gate, count in transpiled.count_ops().items():
            mlflow.log_metric(f"output_gate_{gate}", count)

    def _log_artifacts(self, original: QuantumCircuit, transpiled: QuantumCircuit):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            input_qasm = tmp / "input_circuit.qasm"
            output_qasm = tmp / "transpiled_circuit.qasm"
            summary = tmp / "transpilation_summary.json"
            qprov = tmp / "qprov_record.json"

            try:
                input_qasm.write_text(original.qasm())
                output_qasm.write_text(transpiled.qasm())
            except AttributeError as e:
                from qiskit.qasm3 import dumps

                input_qasm.write_text(dumps(original))
                output_qasm.write_text(dumps(transpiled))

            summary.write_text(
                json.dumps(
                    {
                        "input": {
                            "depth": original.depth(),
                            "size": original.size(),
                            "count_ops": dict(original.count_ops()),
                        },
                        "output": {
                            "depth": transpiled.depth(),
                            "size": transpiled.size(),
                            "count_ops": dict(transpiled.count_ops()),
                        },
                    },
                    indent=2,
                )
            )

            # record = QProvRecord(
            #     circuit=QuantumCircuitProvenance(
            #         circuit_id=str(id(original)),
            #         name=original.name,
            #         num_qubits=original.num_qubits,
            #         depth=original.depth(),
            #         width=original.width(),
            #         size=original.size(),
            #         gate_counts=dict(original.count_ops()),
            #     ),
            #     compilation=CompilationProvenance(
            #         compiler="qiskit",
            #         compiler_version=qiskit.version.VERSION,
            #         optimization_level=self.optimization_level,
            #     ),
            # )

            ctx = get_context()

            qprov.write_text(ctx.to_json(indent=2, sort_keys=True))

            mlflow.log_artifacts(tmp)
