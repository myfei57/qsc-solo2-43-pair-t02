"""Executes a plan step by step and refuses to skip ahead."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..planner.plan import SequencePlanner, Step
from ..runtime.errors import ControlError, OrderViolation


@dataclass(frozen=True)
class StepResult:
    name: str
    status: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def describe(self) -> Dict[str, Any]:
        return {"step": self.name, "status": self.status, "detail": dict(self.detail)}


@dataclass(frozen=True)
class FlowOutcome:
    flow: str
    status: str
    results: Tuple[StepResult, ...]
    error: Optional[ControlError] = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def failed_step(self) -> str:
        for result in self.results:
            if result.status == "failed":
                return result.name
        return ""

    def describe(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "flow": self.flow,
            "status": self.status,
            "steps": [result.describe() for result in self.results],
        }
        if self.error is not None:
            payload["error"] = self.error.to_payload()
            payload["failed_step"] = self.failed_step()
        return payload


class FlowRunner:
    def __init__(self, planner: SequencePlanner) -> None:
        self._planner = planner

    def run(self, name: str, handler: Callable[[Step, Dict[str, Any]], Optional[Dict[str, Any]]]) -> FlowOutcome:
        plan = self._planner.plan(name)
        results: List[StepResult] = []
        executed: List[str] = []
        context: Dict[str, Any] = {}
        for step in plan.steps:
            try:
                detail = handler(step, context)
            except ControlError as exc:
                results.append(StepResult(step.name, "failed", exc.to_payload()))
                return FlowOutcome(flow=name, status="failed", results=tuple(results), error=exc)
            if detail is None:
                results.append(StepResult(step.name, "skipped", {}))
                continue
            executed.append(step.name)
            context[step.name] = dict(detail)
            results.append(StepResult(step.name, "ok", dict(detail)))
        try:
            self._planner.validate(name, executed)
        except OrderViolation as exc:
            results.append(StepResult("plan.validate", "failed", exc.to_payload()))
            return FlowOutcome(flow=name, status="failed", results=tuple(results), error=exc)
        results.append(StepResult("plan.validate", "ok", {"executed": executed}))
        return FlowOutcome(flow=name, status="ok", results=tuple(results))
