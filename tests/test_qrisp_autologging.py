import unittest
from unittest.mock import patch

from qrisp import PassManager, QuantumCircuit

import q8s.runtime.mlflow.qrisp.autologging as autologging
from q8s.runtime.qprov.record import CompilationProvenance, QProvRecord

original_run = PassManager.run


class TestAutolog(unittest.TestCase):
    def _patched_run(self):
        with patch.object(autologging, "safe_patch") as safe_patch:
            autologging.autolog(disable=False)

        safe_patch.assert_called_once()
        return safe_patch.call_args.args[3]

    def _make_circuit(self):
        """Creates a simple quantum circuit for testing.

            Returns:
                QuantumCircuit: A simple quantum circuit with 2 qubits and 4 gates.
                         ┌───┐┌───┐
        qb_58: ──■────■──┤ H ├┤ H ├
               ┌─┴─┐┌─┴─┐└───┘└───┘
        qb_59: ┤ X ├┤ X ├──────────
               └───┘└───┘
        """
        from qrisp import QuantumCircuit

        qc = QuantumCircuit(2)
        qc.cx(0, 1)
        qc.cx(0, 1)  # Self-inverse — will be cancelled
        qc.h(0)
        qc.h(0)  # Another self-inverse pair

        return qc

    def _make_pass_manager(self):
        from qrisp import (
            PassManager,
            combine_single_qubit_gates,
            commute_swaps,
            fuse_adjacents,
        )

        pm = PassManager()
        pm += fuse_adjacents
        pm += commute_swaps
        pm += combine_single_qubit_gates

        return pm

    def test_disabled_autolog_does_not_install_patch(self):
        with patch.object(autologging, "safe_patch") as safe_patch:
            autologging.autolog(disable=True)

        safe_patch.assert_not_called()

    def test_enabled_autolog_installs_patch(self):
        with patch.object(autologging, "safe_patch") as safe_patch:
            autologging.autolog(disable=False)

        safe_patch.assert_called_once()

    def test_patch_records_circuit_and_compilation_duration(self):

        try:
            autologging.autolog(disable=False)

            circuit = self._make_circuit()
            pass_manager = self._make_pass_manager()
            context = QProvRecord(compilation=CompilationProvenance(compiler="qrisp"))
            token = autologging._current_context.set(context)

            result = pass_manager.run(circuit)
            autologging._current_context.reset(token)
        finally:
            PassManager.run = original_run

        self.assertIsInstance(result, QuantumCircuit)
        self.assertEqual(context.circuit.circuit_id, str(id(circuit)))
        self.assertEqual(context.circuit.num_qubits, 2)
        self.assertEqual(context.circuit.depth, 4)
        self.assertEqual(context.circuit.width, 2)
        self.assertEqual(context.circuit.gate_counts, {"h": 2, "cx": 2})
        self.assertEqual(len(context.compilation.passes), 3)


if __name__ == "__main__":
    unittest.main()
