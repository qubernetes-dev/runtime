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

from qiskit.passmanager import FlowControllerLinear
from qiskit.transpiler import (
    ConditionalController,
    DoWhileController,
    PassManager,
    StagedPassManager,
)
from qiskit.transpiler.passes import Depth, Size

from q8s.runtime.mlflow.qiskit.transpiler import (
    find_stage_by_id,
    process_pass,
    process_staged_pass_manager,
)


class TestProcessPass(unittest.TestCase):
    def test_pass_updates_existing_list_without_duplicates(self):
        task, existing_task = Depth(), Size()
        stage_info = [id(existing_task)]
        expected = stage_info + [id(task)]

        self.assertIs(process_pass(task, stage_info), stage_info)
        process_pass(task, stage_info)

        self.assertEqual(stage_info, expected)

    def test_nested_controllers_collect_unique_passes_in_order(self):
        depth, size = Depth(), Size()
        task = FlowControllerLinear(
            [
                depth,
                ConditionalController(
                    [DoWhileController([size, depth], do_while=lambda _: False)],
                    condition=lambda _: False,
                ),
            ]
        )

        self.assertEqual(process_pass(task, []), [id(depth), id(size)])

    def test_empty_controller(self):
        self.assertEqual(process_pass(FlowControllerLinear([]), []), [])

    def test_unknown_task_raises(self):
        with self.assertRaisesRegex(ValueError, "Unknown task type"):
            process_pass(object(), [])


class TestProcessStagedPassManager(unittest.TestCase):
    def test_collects_expanded_stages_and_skips_unset_stages(self):
        depth, size = Depth(), Size()
        manager = StagedPassManager(
            stages=["init", "optimization"],
            pre_init=PassManager([depth]),
            init=PassManager([depth, size, depth]),
            post_init=PassManager(),
        )

        self.assertEqual(
            process_staged_pass_manager(manager),
            {
                "pre_init": [id(depth)],
                "init": [id(depth), id(size)],
                "post_init": [],
            },
        )

    def test_manager_without_passes(self):
        self.assertEqual(process_staged_pass_manager(StagedPassManager()), {})


class TestFindStageById(unittest.TestCase):
    def test_returns_first_matching_stage(self):
        stages = {"init": [1, 2], "optimization": [2, 3]}

        self.assertEqual(find_stage_by_id(stages, 2), "init")
        self.assertEqual(find_stage_by_id(stages, 3), "optimization")

    def test_missing_id_returns_none(self):
        self.assertIsNone(find_stage_by_id({"init": [1]}, 2))
        self.assertIsNone(find_stage_by_id({}, 1))


if __name__ == "__main__":
    unittest.main()
