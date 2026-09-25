"""Generation tagged parameter registry."""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from ..runtime.errors import GenerationMismatch, UnknownParameter
from .schema import PARAMETER_SPECS, ParameterSpec, spec as lookup_spec
from .validate import validate_overrides, validate_value


@dataclass(frozen=True)
class Parameter:
    key: str
    value: float
    generation: int
    updated_tick: int
    spec: ParameterSpec

    def describe(self) -> dict:
        return {
            "key": self.key,
            "value": self.value,
            "generation": self.generation,
            "updated_tick": self.updated_tick,
            "unit": self.spec.unit,
            "label": self.spec.label,
        }


class ParameterRegistry:
    """Every write bumps the generation of that single key."""

    def __init__(self, declared: Iterable[ParameterSpec] = PARAMETER_SPECS) -> None:
        self._specs: Dict[str, ParameterSpec] = {item.key: item for item in declared}
        self._values: Dict[str, float] = {}
        self._generations: Dict[str, int] = {}
        self._updated: Dict[str, int] = {}
        self._revision = 0
        for key, target in self._specs.items():
            self._values[key] = target.default
            self._generations[key] = 0
            self._updated[key] = 0

    @property
    def revision(self) -> int:
        return self._revision

    def keys(self) -> List[str]:
        return sorted(self._specs)

    def require(self, key: str) -> ParameterSpec:
        target = self._specs.get(key)
        if target is None:
            raise UnknownParameter("parameter is not registered", key=key)
        return target

    def get(self, key: str) -> Parameter:
        target = self.require(key)
        return Parameter(
            key=key,
            value=self._values[key],
            generation=self._generations[key],
            updated_tick=self._updated[key],
            spec=target,
        )

    def value(self, key: str) -> float:
        return self.get(key).value

    def integral(self, key: str) -> int:
        return int(self.value(key))

    def generation(self, key: str) -> int:
        return self.get(key).generation

    def generations(self) -> Dict[str, int]:
        return {key: self._generations[key] for key in sorted(self._generations)}

    def set(self, key: str, value: float, tick: int = 0) -> Parameter:
        target = self.require(key)
        numeric = validate_value(target, value)
        self._values[key] = numeric
        self._generations[key] += 1
        self._updated[key] = int(tick)
        self._revision += 1
        return self.get(key)

    def apply_overrides(self, mapping: Dict[str, float], tick: int = 0) -> List[Parameter]:
        checked = validate_overrides(mapping)
        return [self.set(key, value, tick) for key, value in sorted(checked.items())]

    def check_generation(self, key: str, generation: int) -> None:
        current = self._generations[key]
        if current != generation:
            raise GenerationMismatch(
                "parameter generation has moved on",
                key=key,
                expected=current,
                observed=generation,
            )

    def combine(self, keys: Iterable[str]) -> int:
        """Generation of a contract that depends on several parameters."""

        total = 0
        for key in keys:
            total += self.generation(key)
        return total

    def snapshot(self) -> Dict[str, dict]:
        return {key: self.get(key).describe() for key in sorted(self._specs)}

    def find(self, key: str) -> Optional[Parameter]:
        if key not in self._specs:
            return None
        return self.get(key)


def spec(key: str) -> ParameterSpec:
    return lookup_spec(key)
