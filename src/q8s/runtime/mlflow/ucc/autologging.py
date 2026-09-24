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
from importlib.metadata import version

from mlflow.utils.autologging_utils import autologging_integration

from q8s.runtime.mlflow.qiskit.autologging import autolog as qiskit_autolog
from q8s.runtime.qprov.record import CompilationProvenance, QProvRecord

CONTEXT_NAME = "ucc_mlflow_autologging_context"
_current_context: contextvars.ContextVar[QProvRecord] = contextvars.ContextVar(
    CONTEXT_NAME,
    default=QProvRecord(
        compilation=CompilationProvenance(
            compiler="ucc", compiler_version=version("ucc")
        )
    ),
)


def get_context() -> QProvRecord:
    ctx = _current_context.get()
    if ctx is None:
        raise RuntimeError("No active autolog context")
    return ctx


@autologging_integration("ucc")
def autolog(
    disable=False,
    silent=False,
) -> None:
    """Enables autologging for ucc."""

    if disable:
        return

    qiskit_autolog()
