import contextvars
import time
from importlib.metadata import version

from mlflow.utils.autologging_utils import autologging_integration, safe_patch
from qrisp import PassManager, QuantumCircuit

from q8s.runtime.qprov.record import (
    CompilationProvenance,
    QProvRecord,
    QuantumCircuitProvenance,
)

CONTEXT_NAME = "qrisp_mlflow_autologging_context"
_current_context: contextvars.ContextVar[QProvRecord] = contextvars.ContextVar(
    CONTEXT_NAME,
    default=QProvRecord(
        compilation=CompilationProvenance(
            compiler="qrisp", compiler_version=version("qrisp")
        )
    ),
)


def get_context() -> QProvRecord:
    ctx = _current_context.get()
    if ctx is None:
        raise RuntimeError("No active autolog context")
    return ctx


@autologging_integration("qrisp")
def autolog(
    disable=False,
    silent=False,
) -> None:
    """Enables autologging for QRISPs."""

    def patched_pass_manager_run(
        original,  # type: ignore[no-untyped-def]
        instance,
        *args,
        **kwargs,
    ):
        """Patched version of PassManager.run that logs the execution of passes and
        their provenance."""

        print("QRISPs autologging integration is enabled for PassManager.run.")

        ctx = _current_context.get()

        circuit: QuantumCircuit = args[0]

        ctx.circuit = QuantumCircuitProvenance(
            circuit_id=str(id(circuit)),
            num_qubits=circuit.num_qubits(),
            depth=circuit.depth(),
            width=len(circuit.qubits),
            gate_counts=circuit.count_ops(),
        )

        for circuit_pass in instance._passes:
            print(
                f"Executing pass: {circuit_pass.__name__} with args: {args}, kwargs: {kwargs} "
            )

        start = time.perf_counter()

        history = original(instance, *args, **kwargs)

        end = time.perf_counter()

        ctx.compilation.duration_s = end - start

        print(ctx.to_json(indent=2))

        return history

    if disable:
        return

    safe_patch("qrisp", PassManager, "run", patched_pass_manager_run)
