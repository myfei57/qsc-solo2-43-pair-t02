"""Health responses for the probe endpoint."""

from .response import Response, json_response


def health_response(hub) -> Response:
    report = hub.probe.run()
    return json_response(report.status_code, report.describe())
