from backend.app.agent.schemas.planner import PlannerInput, PlannerResult
from backend.app.agent.services.task_planner import TaskPlanner


class PlannerNode:
    def __init__(self, planner: TaskPlanner | None = None) -> None:
        self._planner = planner or TaskPlanner()

    def run(self, planner_input: PlannerInput) -> PlannerResult:
        return self._planner.create(planner_input)
