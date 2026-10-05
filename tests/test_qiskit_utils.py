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

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from mlflow.utils import autologging_utils

from q8s.runtime.mlflow.qiskit import utils


class TestCreateAutolog(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.dict(autologging_utils.AUTOLOGGING_INTEGRATIONS))
        stack.enter_context(patch.object(autologging_utils, "revert_patches"))
        self.patch_qiskit = stack.enter_context(patch.object(utils, "_patch_qiskit"))

    def test_factory_defers_patching_until_called_with_defaults(self):
        autolog = utils.create_autolog()

        self.assertEqual(autolog.integration_name, "qiskit")
        self.patch_qiskit.assert_not_called()
        self.assertIsNone(autolog())

        self.patch_qiskit.assert_called_once_with(
            integration_name="qiskit", disable=False, silent=False, extra_tags=None
        )

    def test_custom_integration_forwards_options_and_registers_configuration(self):
        autolog = utils.create_autolog("custom_qiskit")
        tags = {"team": "quantum"}

        autolog(silent=True, extra_tags=tags)

        self.assertEqual(autolog.integration_name, "custom_qiskit")
        self.patch_qiskit.assert_called_once_with(
            integration_name="custom_qiskit",
            disable=False,
            silent=True,
            extra_tags=tags,
        )
        self.assertEqual(
            autologging_utils.AUTOLOGGING_INTEGRATIONS["custom_qiskit"],
            {"disable": False, "silent": True, "extra_tags": tags},
        )

    def test_disabled_autolog_does_not_patch(self):
        autolog = utils.create_autolog()

        self.assertIsNone(autolog(disable=True))

        self.patch_qiskit.assert_not_called()
        self.assertTrue(autologging_utils.get_autologging_config("qiskit", "disable"))

    def test_repeated_calls_can_disable_and_reenable_autologging(self):
        autolog = utils.create_autolog()
        autolog()
        self.patch_qiskit.reset_mock()

        autolog(disable=True)
        self.patch_qiskit.assert_not_called()
        autolog()

        self.patch_qiskit.assert_called_once_with(
            integration_name="qiskit", disable=False, silent=False, extra_tags=None
        )
        self.assertFalse(autologging_utils.get_autologging_config("qiskit", "disable"))


class TestPatchQiskit(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.safe_patch = stack.enter_context(patch.object(utils, "safe_patch"))
        self.version = stack.enter_context(
            patch.object(utils, "version", return_value="1.2.3")
        )
        self.context_factory = stack.enter_context(
            patch.object(utils.contextvars, "ContextVar")
        )
        self.active_run = stack.enter_context(patch.object(utils.mlflow, "active_run"))
        self.log_param = stack.enter_context(patch.object(utils.mlflow, "log_param"))
        self.log_record = stack.enter_context(patch.object(utils, "log_to_mlflow"))
        stack.enter_context(patch("builtins.print"))
        self.install()

    def install(self, **kwargs):
        self.safe_patch.reset_mock()
        utils._patch_qiskit("qiskit", **kwargs)
        self.record = self.context_factory.call_args.kwargs["default"]
        self.context_factory.return_value.get.return_value = self.record
        self.patches = {
            (entry.args[1], entry.args[2]): entry.args[3]
            for entry in self.safe_patch.call_args_list
        }

    def test_registers_patches_and_initializes_provenance(self):
        tags = {"team": "quantum"}
        self.install(extra_tags=tags)

        self.version.assert_called_with("qiskit")
        self.assertEqual(
            self.context_factory.call_args.args,
            ("qiskit_mlflow_autologging_context",),
        )
        self.assertEqual(self.record.compilation.compiler, "qiskit")
        self.assertEqual(self.record.compilation.compiler_version, "1.2.3")
        self.assertEqual(
            set(self.patches),
            {
                (utils.StagedPassManager, "run"),
                (utils.qiskit.transpiler, "generate_preset_pass_manager"),
                (utils.AerSimulator, "run"),
                (utils.ActiveRun, "__exit__"),
            },
        )
        for entry in self.safe_patch.call_args_list:
            self.assertEqual(entry.args[0], "qiskit")
            if entry.args[1] is not utils.AerSimulator:
                self.assertEqual(
                    entry.kwargs, {"manage_run": False, "extra_tags": tags}
                )

    def test_pass_manager_records_circuit_duration_and_callback_pass(self):
        circuit = utils.QuantumCircuit(2, name="bell")
        circuit.h(0)
        circuit.cx(0, 1)
        manager = Mock()
        transpiler_pass = Mock()
        dag = Mock()
        dag.depth.return_value = 3
        dag.size.return_value = 4
        stages = {"example": "stage information"}

        for as_list in (False, True):
            with self.subTest(as_list=as_list):
                self.install(silent=True)
                circuits = [circuit] if as_list else circuit
                original = Mock(return_value="transpiled")
                with (
                    patch.object(utils.time, "perf_counter", side_effect=[10, 12.5]),
                    patch.object(
                        utils, "process_staged_pass_manager", return_value=stages
                    ) as process,
                    patch.object(
                        utils, "find_stage_by_id", return_value="routing"
                    ) as find,
                ):
                    result = self.patches[utils.StagedPassManager, "run"](
                        original, manager, circuits, num_processes=1
                    )
                    callback = original.call_args.kwargs["callback"]
                    original.assert_called_once_with(
                        manager, circuits, num_processes=1, callback=callback
                    )
                    callback(transpiler_pass, dag, 0.25, {}, 2)
                    process.assert_called_once_with(manager)
                    find.assert_called_once_with(stages, id(transpiler_pass))

                self.assertEqual(result, "transpiled")
                provenance = self.record.circuit
                self.assertEqual(provenance.circuit_id, str(id(circuit)))
                self.assertEqual(provenance.name, "bell")
                self.assertEqual(provenance.num_qubits, 2)
                self.assertEqual(provenance.depth, 2)
                self.assertEqual(provenance.width, 2)
                self.assertEqual(provenance.size, 2)
                self.assertEqual(provenance.gate_counts, {"h": 1, "cx": 1})
                self.assertEqual(self.record.compilation.duration_s, 2.5)
                self.assertEqual(
                    self.record.compilation.metadata["stages_pass_info"], stages
                )
                (recorded_pass,) = self.record.compilation.passes
                self.assertEqual(
                    recorded_pass.pass_name, type(transpiler_pass).__name__
                )
                self.assertEqual(recorded_pass.pass_index, 2)
                self.assertEqual(recorded_pass.pass_duration_s, 0.25)
                self.assertEqual(
                    recorded_pass.pass_metadata,
                    {"depth": 3, "size": 4, "stage": "routing"},
                )
                self.context_factory.return_value.get.return_value = None
                with self.assertRaisesRegex(RuntimeError, "No active autolog context"):
                    callback(transpiler_pass, dag, 0.25, {}, 3)

    def test_disabled_pass_manager_skips_provenance(self):
        self.install(disable=True)
        original = Mock()
        result = self.patches[utils.StagedPassManager, "run"](
            original, Mock(), "circuit", callback="callback"
        )
        original.assert_called_once_with("circuit", callback="callback")
        self.assertIs(result, original.return_value)
        self.assertIsNone(self.record.circuit)

    def test_preset_manager_records_options_including_zero(self):
        backend = SimpleNamespace(name="simulator", num_qubits=5)
        original = Mock()
        result = self.patches[utils.qiskit.transpiler, "generate_preset_pass_manager"](
            original, optimization_level=0, seed_transpiler=0, backend=backend
        )
        original.assert_called_once_with(
            optimization_level=0, seed_transpiler=0, backend=backend
        )
        self.assertIs(result, original.return_value)
        self.assertEqual(self.record.compilation.optimization_level, 0)
        self.assertEqual(self.record.compilation.seed_transpiler, 0)
        self.assertEqual(self.record.quantum_computer.backend_name, "simulator")
        self.assertEqual(self.record.quantum_computer.num_qubits, 5)
        self.log_param.assert_has_calls(
            [
                call("optimization_level", 0),
                call("seed_transpiler", 0),
                call("backend_name", "simulator"),
            ]
        )

    def test_preset_manager_without_options_does_not_log_parameters(self):
        original = Mock()
        result = self.patches[utils.qiskit.transpiler, "generate_preset_pass_manager"](
            original
        )
        original.assert_called_once_with()
        self.assertIs(result, original.return_value)
        self.log_param.assert_not_called()
        self.assertIsNone(self.record.quantum_computer)

    def test_preset_manager_requires_active_run(self):
        self.active_run.return_value = None
        original = Mock()
        with self.assertRaisesRegex(RuntimeError, "No active MLflow run"):
            self.patches[utils.qiskit.transpiler, "generate_preset_pass_manager"](
                original
            )
        original.assert_not_called()

    def test_preset_manager_and_run_exit_reject_invalid_context(self):
        for context in (None, object()):
            for key in (
                (utils.qiskit.transpiler, "generate_preset_pass_manager"),
                (utils.ActiveRun, "__exit__"),
            ):
                with self.subTest(context=context, target=key):
                    self.context_factory.return_value.get.return_value = context
                    original = Mock()
                    with self.assertRaisesRegex(
                        RuntimeError, "No active autolog context"
                    ):
                        self.patches[key](original)
                    original.assert_not_called()
        self.log_record.assert_not_called()

    def test_backend_run_patches_result_and_preserves_return_values(self):
        backend, job = Mock(), Mock()
        original = Mock(return_value=job)
        result = self.patches[utils.AerSimulator, "run"](
            original, backend, "circuit", shots=100
        )
        original.assert_called_once_with(backend, "circuit", shots=100)
        self.assertIs(result, job)
        registration = self.safe_patch.call_args
        self.assertEqual(registration.args[:3], ("qiskit", type(job), "result"))
        patched_result = registration.args[3]
        for error in (None, ValueError("No counts")):
            with self.subTest(error=error):
                counts_result = Mock()
                counts_result.get_counts.side_effect = error
                original_result = Mock(return_value=counts_result)
                self.assertIs(
                    patched_result(original_result, job, "argument", timeout=5),
                    counts_result,
                )
                original_result.assert_called_once_with(job, "argument", timeout=5)
                counts_result.get_counts.assert_called_once_with()

    def test_run_exit_logs_record_before_delegating(self):
        original = Mock(
            side_effect=lambda *args: self.log_record.assert_called_once_with(
                self.record
            )
        )
        run = Mock()
        self.patches[utils.ActiveRun, "__exit__"](original, run, None, None, None)
        original.assert_called_once_with(run, None, None, None)


if __name__ == "__main__":
    unittest.main()
