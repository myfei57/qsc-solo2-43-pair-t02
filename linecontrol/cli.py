"""Command line entry points."""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from .console.handlers import Console
from .console.server import build_server
from .hub import ControlHub

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_DATA_DIR = "var"
DEFAULT_CONFIG = "config/linecontrol.json"


def build_parser() -> argparse.ArgumentParser:
    global_options = argparse.ArgumentParser(add_help=False)
    global_options.add_argument(
        "--data-dir", default=DEFAULT_DATA_DIR, help="directory holding the record files"
    )
    global_options.add_argument(
        "--config", default=DEFAULT_CONFIG, help="parameter file applied on a cold start"
    )
    inherited = argparse.ArgumentParser(add_help=False)
    inherited.add_argument("--data-dir", default=argparse.SUPPRESS, help="directory holding the record files")
    inherited.add_argument("--config", default=argparse.SUPPRESS, help="parameter file applied on a cold start")

    parser = argparse.ArgumentParser(
        prog="linecontrol",
        description="line control service",
        parents=[global_options],
    )
    subparsers = parser.add_subparsers(dest="command")

    server = subparsers.add_parser("serve", parents=[inherited], help="run the HTTP console")
    server.add_argument("--host", default=DEFAULT_HOST)
    server.add_argument("--port", type=int, default=DEFAULT_PORT)

    subparsers.add_parser(
        "snapshot", parents=[inherited], help="write a state snapshot next to the record log"
    )
    subparsers.add_parser("state", parents=[inherited], help="print the current machine state")

    flow = subparsers.add_parser("flow", parents=[inherited], help="run one operating flow")
    flow.add_argument("--name", required=True)
    flow.add_argument("--arg", action="append", default=[], help="key=value argument for the flow")

    return parser


def _hub(args: argparse.Namespace) -> ControlHub:
    config = getattr(args, "config", "") or None
    return ControlHub(data_dir=getattr(args, "data_dir", DEFAULT_DATA_DIR), config_path=config)


def _parse_args(values: List[str]) -> Dict[str, Any]:
    parsed: Dict[str, Any] = {}
    for item in values:
        if "=" not in item:
            raise SystemExit("flow arguments must use key=value: " + item)
        key, raw = item.split("=", 1)
        try:
            parsed[key] = json.loads(raw)
        except json.JSONDecodeError:
            parsed[key] = raw
    return parsed


def _emit(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def _run_serve(args: argparse.Namespace) -> int:
    hub = _hub(args)
    restored = hub.restore()
    console = Console(hub)
    server = build_server(console, args.host, args.port)
    _emit(
        {
            "service": "linecontrol",
            "host": args.host,
            "port": server.bound_port,
            "health": "/healthz",
            "restore": restored.describe(),
        }
    )
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _run_snapshot(args: argparse.Namespace) -> int:
    hub = _hub(args)
    hub.restore()
    _emit(hub.write_snapshot())
    return 0


def _run_state(args: argparse.Namespace) -> int:
    hub = _hub(args)
    restored = hub.restore()
    _emit({"restore": restored.describe(), "status": hub.status()})
    return 0


def _run_flow(args: argparse.Namespace) -> int:
    hub = _hub(args)
    hub.restore()
    _emit(hub.run_flow(args.name, _parse_args(args.arg)))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    handlers = {
        "serve": _run_serve,
        "snapshot": _run_snapshot,
        "state": _run_state,
        "flow": _run_flow,
    }
    return handlers[args.command](args)
