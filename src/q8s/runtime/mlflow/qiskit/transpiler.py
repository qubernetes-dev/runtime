from qiskit.transpiler import (
    ConditionalController,
    DoWhileController,
    StagedPassManager,
)
from qiskit.passmanager import FlowControllerLinear, GenericPass


def process_pass(
    task: (
        GenericPass | ConditionalController | DoWhileController | FlowControllerLinear
    ),
    stage_info: list[int],
):
    """
    Recursively process a pass or controller and collect the IDs of all passes in the stage_info list.
    Args:
        task: The pass or controller to process.
        stage_info: A list to collect the IDs of all passes.
    Returns:
        The updated stage_info list containing the IDs of all passes."""
    if (
        isinstance(task, ConditionalController)
        or isinstance(task, DoWhileController)
        or isinstance(task, FlowControllerLinear)
    ):
        for sub_pass in task.tasks:
            process_pass(sub_pass, stage_info)
    elif isinstance(task, GenericPass):
        if id(task) not in stage_info:
            stage_info.append(id(task))
    else:
        raise ValueError(f"Unknown task type: {type(task)}")

    return stage_info


def process_staged_pass_manager(manager: StagedPassManager) -> dict[str, list[int]]:
    """
    Process a StagedPassManager and return a dictionary containing the stage names and their corresponding pass IDs.
    Args:
        manager (StagedPassManager): The StagedPassManager to process.
    Returns:
        dict: A dictionary mapping stage names to lists of pass IDs.
    """
    stages_pass_info = {}

    for stage in manager.expanded_stages:
        stage_pm = getattr(manager, stage, None)
        if stage_pm is None:
            continue

        stages_pass_info[stage] = process_pass(stage_pm.to_flow_controller(), [])

    return stages_pass_info


def find_stage_by_id(stage_pass_info: dict[str, list[int]], pass_id: int) -> str | None:
    """
    Find the stage name corresponding to a given pass ID in the staged pass manager.
    Args:
        stage_pass_info (dict): A dictionary mapping stage names to lists of pass IDs.
        pass_id (int): The ID of the pass to find.
    Returns:
        str | None: The name of the stage containing the pass ID, or None if not found.
    """
    for stage, pass_ids in stage_pass_info.items():
        if pass_id in pass_ids:
            return stage
    return None
