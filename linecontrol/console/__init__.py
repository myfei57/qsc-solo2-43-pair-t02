"""HTTP surface: JSON endpoints plus the operator pages."""

from .handlers import Console
from .pages import PageCatalog, default_pages_root
from .response import Response, html_response, json_response
from .router import PathNotFound, Route, Router
from .server import ConsoleServer, build_server

__all__ = [
    "Console",
    "ConsoleServer",
    "PageCatalog",
    "PathNotFound",
    "Response",
    "Route",
    "Router",
    "build_server",
    "default_pages_root",
    "html_response",
    "json_response",
]
