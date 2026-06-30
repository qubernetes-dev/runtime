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

    def _patched_run(
        original: StagedPassManager.run,  # type: ignore[no-untyped-def]
        instance: StagedPassManager,
        *args,
        **kwargs,
    ):
        print("Qiskit autologging integration is enabled.")

        start = time.perf_counter()

        circuit: QuantumCircuit = args[0]

        ctx = _current_context.get()

        if ctx is None or not isinstance(ctx, QProvRecord):
            _initialize_context(circuit)
            ctx = _current_context.get()

        if disable:
            return original(*args, **kwargs)

        if not silent:
            print("Logging Qiskit transpilation run to MLflow.")

        kwargs["callback"] = callback

        history = original(instance, *args, **kwargs)

        ctx.compilation.duration_s = time.perf_counter() - start

        return history

    safe_patch(
        "qiskit",
        qiskit.transpiler.StagedPassManager,
        "run",
        _patched_run,
        manage_run=True,
        extra_tags=extra_tags,
    )


def callback(pass_, dag, time, property_set, count):
    name = pass_.__class__.__name__
    print(
        f"Pass {count:03d}: {name}, Time: {time:.6f}s, Depth: {dag.depth()}, Size: {dag.size()}"
    )


def _initialize_context(circuit: QuantumCircuit) -> None:
    """
    Initializes the autologging context for a Qiskit transpilation run.

    This function is called at the beginning of a transpilation run to set up the context for logging.
    """
    print("Initializing Qiskit autologging context.")

    record = QProvRecord(
        circuit=QuantumCircuitProvenance(
            circuit_id=str(id(circuit)),
            name=circuit.name,
            num_qubits=circuit.num_qubits,
            depth=circuit.depth(),
            width=circuit.width(),
            size=circuit.size(),
            gate_counts=dict(circuit.count_ops()),
        ),
        compilation=CompilationProvenance(
            compiler="qiskit", compiler_version=qiskit.version.VERSION
        ),
    )

    _current_context.set(record)
