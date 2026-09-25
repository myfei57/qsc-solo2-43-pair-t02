"""Step plans and the order check that guards them."""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from ..runtime.errors import OrderViolation, UnknownItem, ValidationError


@dataclass(frozen=True)
class Step:
    name: str
    subsystem: str
    description: str
    requires: Tuple[str, ...] = ()
    gate: str = ""

    def describe(self) -> Dict[str, Any]:
        return {
            "step": self.name,
            "subsystem": self.subsystem,
            "description": self.description,
            "requires": list(self.requires),
            "gate": self.gate,
        }


@dataclass(frozen=True)
class FlowPlan:
    name: str
    title: str
    steps: Tuple[Step, ...] = field(default_factory=tuple)

    def names(self) -> List[str]:
        return [step.name for step in self.steps]

    def index(self, name: str) -> int:
        for position, step in enumerate(self.steps):
            if step.name == name:
                return position
        raise UnknownItem("no such step in this flow", flow=self.name, step=name)

    def step(self, name: str) -> Step:
        return self.steps[self.index(name)]

    def describe(self) -> Dict[str, Any]:
        return {
            "flow": self.name,
            "title": self.title,
            "order": self.names(),
            "steps": [step.describe() for step in self.steps],
        }


class SequencePlanner:
    def __init__(self, plans: Iterable[FlowPlan]) -> None:
        self._plans: Dict[str, FlowPlan] = {}
        for plan in plans:
            if plan.name in self._plans:
                raise ValidationError("duplicate flow name", flow=plan.name)
            if not plan.steps:
                raise ValidationError("a flow must declare at least one step", flow=plan.name)
            self._plans[plan.name] = plan

    def names(self) -> List[str]:
        return sorted(self._plans)

    def plan(self, name: str) -> FlowPlan:
        found = self._plans.get(name)
        if found is None:
            raise UnknownItem("no such flow", flow=name)
        return found

    def prerequisites(self, name: str) -> Dict[str, List[str]]:
        plan = self.plan(name)
        return {step.name: list(step.requires) for step in plan.steps}

    def validate(self, name: str, executed: Sequence[str]) -> None:
        """The recorded execution must be an ordered prefix of the plan."""

        expected = self.plan(name).names()
        for position, step_name in enumerate(executed):
            if position >= len(expected):
                raise OrderViolation(
                    "more steps were executed than the plan declares",
                    flow=name,
                    extra=step_name,
                )
            if expected[position] != step_name:
                raise OrderViolation(
                    "execution order does not follow the plan",
                    flow=name,
                    position=position,
                    expected=expected[position],
                    observed=step_name,
                )

    def describe(self) -> Dict[str, Any]:
        return {"flows": [self._plans[name].describe() for name in self.names()]}
