import contextvars
import time

import qiskit
from qiskit.circuit import QuantumCircuit
from qiskit.transpiler import StagedPassManager

from mlflow.utils.autologging_utils import autologging_integration, safe_patch

from q8s.runtime.qprov.record import (
    CompilationProvenance,
    QProvRecord,
    QuantumCircuitProvenance,
    QuantumComputerProvenance,
)

CONTEXT_NAME = "qiskit_mlflow_autologging_context"

_current_context = contextvars.ContextVar(CONTEXT_NAME, default={})


def get_context() -> QProvRecord:
    ctx = _current_context.get()
    if ctx is None:
        raise RuntimeError("No active autolog context")
    return ctx


@autologging_integration("qiskit")
def autolog(
    log_passes=True, experiment_name=str, disable=False, silent=False, extra_tags=None
) -> None:
    """
    Enables the Qiskit autologging integration.

    This function is idempotent and can be called multiple times. The integration will only be enabled once.
    """

    record = QProvRecord(
        compilation=CompilationProvenance(
            compiler="qiskit", compiler_version=qiskit.version.VERSION
        )
    )

    _current_context.set(record)

    def _patched_run(
        original: StagedPassManager.run,  # type: ignore[no-untyped-def]
        instance: StagedPassManager,
        *args,
        **kwargs,
    ):
        if disable:
            return original(*args, **kwargs)

        print("Qiskit autologging integration is enabled.")

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

        history = original(instance, *args, **kwargs)

        ctx.compilation.duration_s = time.perf_counter() - start

        return history

    def _patched_generate_preset_pass_manager(
        original,  # type: ignore[no-untyped-def]
        *args,
        **kwargs,
    ):
        print(
            "Qiskit autologging integration is enabled for generate_preset_pass_manager."
        )

        backend = kwargs.get("backend", None)

        print(f"Backend: {backend.name if backend else 'None'}")

        if backend is not None:
            ctx = _current_context.get()

            if ctx is None or not isinstance(ctx, QProvRecord):
                raise RuntimeError(
                    "No active autolog context. Please call transpile() first."
                )

            ctx.quantum_computer = QuantumComputerProvenance(
                provider="IQM",
                backend_name=backend.name,
            )

        return original(*args, **kwargs)

    safe_patch(
        "qiskit",
        qiskit.transpiler.StagedPassManager,
        "run",
        _patched_run,
        manage_run=True,
        extra_tags=extra_tags,
    )

    safe_patch(
        "qiskit",
        qiskit.transpiler,
        "generate_preset_pass_manager",
        _patched_generate_preset_pass_manager,
        manage_run=True,
        extra_tags=extra_tags,
    )


def callback(pass_, dag, time, property_set, count):
    """
    Callback function for logging pass information during transpilation.
    """
    name = pass_.__class__.__name__

    ctx = _current_context.get()

    if ctx is None or not isinstance(ctx, QProvRecord):
        raise RuntimeError("No active autolog context. Please call transpile() first.")

    pass_metadata = {
        "depth": dag.depth(),
        "size": dag.size(),
    }

    ctx.compilation.add_pass(
        pass_name=name,
        pass_index=count,
        pass_duration_s=time,
        pass_metadata=pass_metadata,
    )
