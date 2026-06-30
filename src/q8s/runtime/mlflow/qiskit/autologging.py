import contextvars
import tempfile
import time
from pathlib import Path

from mlflow.tracking.fluent import ActiveRun
import qiskit
from qiskit.circuit import QuantumCircuit
from qiskit.transpiler import StagedPassManager
from qiskit_aer import AerSimulator

from mlflow.utils.autologging_utils import autologging_integration, safe_patch

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
    """
    Enables the Qiskit autologging integration.

    This function is idempotent and can be called multiple times. The integration will only be enabled once.
    """

    def patched_run(
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

        history = original(instance, *args, **kwargs)

        ctx.compilation.duration_s = time.perf_counter() - start

        return history

    safe_patch(
        "qiskit",
        qiskit.transpiler.StagedPassManager,
        "run",
        patched_run,
        manage_run=False,
        extra_tags=extra_tags,
    )

    def patched_generate_preset_pass_manager(
        original,  # type: ignore[no-untyped-def]
        *args,
        **kwargs,
    ):
        """
        Patch the generate_preset_pass_manager function to log the backend information to the QProvRecord.
        """
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
                num_qubits=getattr(backend, "num_qubits", None),
            )

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
                counts = result.get_counts()
                print("counts:", counts)
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
        """
        Patch the __exit__ method of ActiveRun to log the QProvRecord to MLflow when the run ends.
        """
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

    print(
        f"Pass {count:03d}: {name}, Time: {time:.6f}s, Depth: {dag.depth()}, Size: {dag.size()}"
    )


def log_to_mlflow(record: QProvRecord):
    """
    Logs the QProvRecord to MLflow.
    """
    import mlflow

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

        mlflow.log_artifacts(tmp)
