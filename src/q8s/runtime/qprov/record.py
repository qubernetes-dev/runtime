from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from dataclasses_json import dataclass_json


@dataclass
class QuantumCircuitProvenance:
    circuit_id: str
    name: str | None = None
    num_qubits: int | None = None
    depth: int | None = None
    width: int | None = None
    size: int | None = None
    gate_counts: dict[str, int] = field(default_factory=dict)
    qasm: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuantumComputerProvenance:
    provider: str
    backend_name: str
    backend_version: str | None = None
    num_qubits: int | None = None
    basis_gates: list[str] = field(default_factory=list)
    coupling_map: list[tuple[int, int]] = field(default_factory=list)
    simulator: bool | None = None
    calibration_timestamp: datetime | None = None
    qubit_properties: dict[str, Any] = field(default_factory=dict)
    gate_errors: dict[str, Any] = field(default_factory=dict)
    readout_errors: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PassProvenance:
    pass_name: str
    pass_index: int
    pass_type: str | None = None
    pass_duration_s: float | None = None
    pass_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompilationProvenance:
    compiler: str = "qiskit"
    compiler_version: str | None = None
    optimization_level: int | None = None
    initial_layout: Any | None = None
    final_layout: Any | None = None
    routing_method: str | None = None
    translation_method: str | None = None
    scheduling_method: str | None = None
    seed_transpiler: int | None = None
    input_depth: int | None = None
    output_depth: int | None = None
    input_gate_counts: dict[str, int] = field(default_factory=dict)
    output_gate_counts: dict[str, int] = field(default_factory=dict)
    duration_s: float | None = None
    passes: list[PassProvenance] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_pass(
        self,
        pass_name: str,
        pass_index: int,
        pass_type: str | None = None,
        pass_duration_s: float | None = None,
        pass_metadata: dict[str, Any] | None = None,
    ):
        if pass_metadata is None:
            pass_metadata = {}
        self.passes.append(
            PassProvenance(
                pass_name=pass_name,
                pass_index=pass_index,
                pass_type=pass_type,
                pass_duration_s=pass_duration_s,
                pass_metadata=pass_metadata,
            )
        )


@dataclass_json
@dataclass
class ExecutionProvenance:
    execution_id: str = field(default_factory=lambda: str(uuid4()))
    job_id: str | None = None
    shots: int | None = None
    status: str | None = None
    submit_time: datetime | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    queue_time_s: float | None = None
    execution_time_s: float | None = None
    counts: dict[str, int] = field(default_factory=dict)
    result_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass_json
@dataclass
class QProvRecord:
    circuit: QuantumCircuitProvenance | None = None
    quantum_computer: QuantumComputerProvenance | None = None
    compilation: CompilationProvenance | None = None
    execution: ExecutionProvenance | None = None
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        metadata={"dataclasses_json": {"encoder": lambda dt: dt.isoformat()}},
    )
    record_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, **kwargs) -> str:
        return dataclass_json.dumps(self, **kwargs)
