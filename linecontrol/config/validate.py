"""Type coercion and bound checks for parameter values."""

from typing import Any, Dict

from ..runtime.errors import OutOfRange, ValidationError
from .schema import ParameterSpec, spec


def coerce(target: ParameterSpec, value: Any) -> float:
    if isinstance(value, bool):
        raise ValidationError("boolean is not a parameter value", key=target.key, value=value)
    if not isinstance(value, (int, float)):
        raise ValidationError("parameter value must be a number", key=target.key, value=value)
    if target.integral:
        if float(value) != int(value):
            raise ValidationError("parameter expects a whole number", key=target.key, value=value)
        return float(int(value))
    return float(value)


def validate_value(target: ParameterSpec, value: Any) -> float:
    numeric = coerce(target, value)
    if numeric < target.low or numeric > target.high:
        raise OutOfRange(
            "parameter value is outside its declared bounds",
            key=target.key,
            value=numeric,
            low=target.low,
            high=target.high,
        )
    return numeric


def validate_overrides(mapping: Dict[str, Any]) -> Dict[str, float]:
    checked: Dict[str, float] = {}
    for key, value in mapping.items():
        checked[key] = validate_value(spec(key), value)
    return checked
