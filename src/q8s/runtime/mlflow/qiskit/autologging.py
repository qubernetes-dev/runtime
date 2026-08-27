# Copyright 2026 Qubernetes Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

import contextvars
import tempfile
import time
from pathlib import Path

import mlflow
import qiskit
from mlflow.tracking.fluent import ActiveRun
from mlflow.utils.autologging_utils import autologging_integration, safe_patch
from qiskit.circuit import QuantumCircuit
from qiskit.transpiler import StagedPassManager
from qiskit_aer import AerSimulator

from q8s.runtime.mlflow.qiskit.transpiler import (
    find_stage_by_id,
    process_staged_pass_manager,
)
from q8s.runtime.qprov.graphs import plot_transpilation_timeline
from q8s.runtime.qprov.record import (
    CompilationProvenance,
    QProvRecord,
    QuantumCircuitProvenance,
    QuantumComputerProvenance,
)

CONTEXT_NAME = "qiskit_mlflow_autologging_context"

_current_context: contextvars.ContextVar[QProvRecord] = contextvars.ContextVar(
    CONTEXT_NAME,
    default=QProvRecord(
        compilation=CompilationProvenance(
            compiler="qiskit", compiler_version=qiskit.version.VERSION
        )
    ),
)


def get_context() -> QProvRecord:
    ctx = _current_context.get()
    if ctx is None:
        raise RuntimeError("No active autolog context")
    return ctx


@autologging_integration("qiskit")
def autolog(
    # log_passes=True,
    disable=False,
    silent=False,
    extra_tags=None,
) -> None:
    """Enables the Qiskit autologging integration.

    This function is idempotent and can be called multiple times. The integration will
    only be enabled once.
    """

    def patched_staged_pass_manager_run(
        original: StagedPassManager.run,  # type: ignore[no-untyped-def]
        instance: StagedPassManager,
        *args,
        **kwargs,
    ):
        if disable:
            return original(*args, **kwargs)

        print("Qiskit autologging integration is enabled for StagedPassManager.run.")

        start = time.perf_counter()

        circuit: QuantumCircuit = args[0]

        ctx = _current_context.get()

        ctx.circuit = QuantumCircuitProvenance(
            circuit_id=str(id(circuit)),
            name=circuit.name,
            num_qubits=circuit.num_qubits,
            depth=circuit.depth(),
            width=circuit.width(),
            size=circuit.size(),
            gate_counts=dict(circuit.count_ops()),
        )

        if ctx is None or not isinstance(ctx, QProvRecord):
            raise RuntimeError(
                "No active autolog context. Please call transpile() first."
            )

        if not silent:
            print("Logging Qiskit transpilation run to MLflow.")

        kwargs["callback"] = callback

        ctx.compilation.metadata["stages_pass_info"] = process_staged_pass_manager(
            instance
        )

        history = original(instance, *args, **kwargs)

        ctx.compilation.duration_s = time.perf_counter() - start

        return history

    safe_patch(
        "qiskit",
        qiskit.transpiler.StagedPassManager,
        "run",
        patched_staged_pass_manager_run,
        manage_run=False,
        extra_tags=extra_tags,
    )

    def patched_generate_preset_pass_manager(
        original,  # type: ignore[no-untyped-def]
        *args,
        **kwargs,
    ):
        """Patch the generate_preset_pass_manager function to log the backend
        information to the QProvRecord."""

        print(
            "Qiskit autologging integration is enabled for generate_preset_pass_manager."
        )

        run = mlflow.active_run()

        if run is None:
            # noqa: E501
            raise RuntimeError(
                """No active MLflow run. `generate_preset_pass_manager` must be
                called within an active MLflow run."""
            )

        ctx = _current_context.get()

        if ctx is None or not isinstance(ctx, QProvRecord):
            raise RuntimeError(
                "No active autolog context. Please call transpile() first."
            )

        optimization_level = kwargs.get("optimization_level", None)

        if optimization_level is not None:
            ctx.compilation.optimization_level = optimization_level
            mlflow.log_param("optimization_level", optimization_level)

        seed_transpiler = kwargs.get("seed_transpiler", None)

        if seed_transpiler is not None:
            ctx.compilation.seed_transpiler = seed_transpiler
            mlflow.log_param("seed_transpiler", seed_transpiler)

        backend = kwargs.get("backend", None)

        if backend is not None:
            ctx.quantum_computer = QuantumComputerProvenance(
                provider="IQM",
                backend_name=backend.name,
                num_qubits=getattr(backend, "num_qubits", None),
            )
            mlflow.log_param("backend_name", backend.name)

        return original(*args, **kwargs)

    safe_patch(
        "qiskit",
        qiskit.transpiler,
        "generate_preset_pass_manager",
        patched_generate_preset_pass_manager,
        manage_run=False,
        extra_tags=extra_tags,
    )

    def patched_backend_run(original, self, *args, **kwargs):
        job = original(self, *args, **kwargs)

        job_cls = job.__class__

        def patched_result(original_result, job_self, *r_args, **r_kwargs):
            result = original_result(job_self, *r_args, **r_kwargs)

            # log result here
            try:
                result.get_counts()
                # print("counts:", counts)
                # mlflow.log_dict(counts, "qiskit/result_counts.json")
            except Exception:
                pass

            return result

        safe_patch(
            "qiskit",
            job_cls,
            "result",
            patched_result,
        )

        return job

    safe_patch(
        "qiskit",
        AerSimulator,
        "run",
        patched_backend_run,
    )

    def patched_activerun_exit(original, *args, **kwargs):
        """Patch the __exit__ method of ActiveRun to log the QProvRecord to MLflow when
        the run ends."""
        ctx = _current_context.get()

        if ctx is None or not isinstance(ctx, QProvRecord):
            raise RuntimeError(
                "No active autolog context. Please call transpile() first."
            )

        log_to_mlflow(ctx)

        return original(*args, **kwargs)

    safe_patch(
        "qiskit",
        ActiveRun,
        "__exit__",
        patched_activerun_exit,
        manage_run=False,
        extra_tags=extra_tags,
    )


def callback(pass_, dag, time, property_set, count):
    """Callback function for logging pass information during transpilation."""
    name = pass_.__class__.__name__

    ctx = _current_context.get()

    if ctx is None or not isinstance(ctx, QProvRecord):
        raise RuntimeError("No active autolog context. Please call transpile() first.")

    pass_metadata = {
        "depth": dag.depth(),
        "size": dag.size(),
        "stage": find_stage_by_id(
            ctx.compilation.metadata["stages_pass_info"], id(pass_)
        ),
    }

    ctx.compilation.add_pass(
        pass_name=name,
        pass_index=count,
        pass_duration_s=time,
        pass_metadata=pass_metadata,
    )


def log_to_mlflow(record: QProvRecord):
    """Logs the QProvRecord to MLflow."""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        transpilation_timeline = tmp / "transpilation_timeline.png"

        qprov_file = tmp / "qprov_record.json"
        qprov_file.write_text(record.to_json(indent=2, sort_keys=True))

        fig = plot_transpilation_timeline(list(record.compilation.passes))
        fig.savefig(transpilation_timeline, bbox_inches="tight")

        run = mlflow.active_run()
        if run is None:
            raise RuntimeError("No active MLflow run. Please start a run first.")

        passes = sorted(record.compilation.passes, key=lambda p: p.pass_index)

        mlflow.log_metric("passes_count", len(passes))
        mlflow.log_metric("transpilation_duration", record.compilation.duration_s)
        mlflow.log_metric(
            "circuit_depth", passes[-1].pass_metadata.get("depth", 0) if passes else 0
        )
        mlflow.log_metric(
            "circuit_size", passes[-1].pass_metadata.get("size", 0) if passes else 0
        )

        mlflow.log_artifacts(tmp)
