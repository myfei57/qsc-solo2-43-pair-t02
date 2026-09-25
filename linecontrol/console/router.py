"""A small deterministic path router."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..runtime.errors import UnknownItem


class PathNotFound(UnknownItem):
    code = "path_not_found"


Handler = Callable[[Dict[str, str], Dict[str, str], Dict[str, Any]], Any]


def _split(path: str) -> List[str]:
    return [segment for segment in path.strip("/").split("/") if segment]


@dataclass(frozen=True)
class Route:
    method: str
    pattern: str
    handler: Handler

    def match(self, method: str, path: str) -> Optional[Dict[str, str]]:
        if method != self.method:
            return None
        pattern_parts = _split(self.pattern)
        path_parts = _split(path)
        if len(pattern_parts) != len(path_parts):
            return None
        captured: Dict[str, str] = {}
        for expected, actual in zip(pattern_parts, path_parts):
            if expected.startswith("{") and expected.endswith("}"):
                captured[expected[1:-1]] = actual
            elif expected != actual:
                return None
        return captured


class Router:
    def __init__(self) -> None:
        self._routes: List[Route] = []

    def add(self, method: str, pattern: str, handler: Handler) -> None:
        self._routes.append(Route(method=method.upper(), pattern=pattern, handler=handler))

    def resolve(self, method: str, path: str) -> Tuple[Handler, Dict[str, str]]:
        for route in self._routes:
            captured = route.match(method.upper(), path)
            if captured is not None:
                return route.handler, captured
        raise PathNotFound("no route for this path", method=method.upper(), path=path)

    def routes(self) -> List[Dict[str, str]]:
        return [{"method": route.method, "pattern": route.pattern} for route in self._routes]

    def describe(self) -> Dict[str, Any]:
        return {"count": len(self._routes), "routes": self.routes()}
