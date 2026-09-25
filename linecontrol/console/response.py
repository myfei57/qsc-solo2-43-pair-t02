"""Response objects shared by the router and the socket server."""

import json
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Response:
    status: int
    content_type: str
    body: str

    def as_json(self) -> Dict[str, Any]:
        return json.loads(self.body)


def json_response(status: int, payload: Dict[str, Any]) -> Response:
    return Response(
        status=status,
        content_type="application/json; charset=utf-8",
        body=json.dumps(payload, sort_keys=True, indent=2),
    )


def html_response(body: str, status: int = 200) -> Response:
    return Response(status=status, content_type="text/html; charset=utf-8", body=body)
