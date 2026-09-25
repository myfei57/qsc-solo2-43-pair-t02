"""Route table and endpoint implementations."""

from typing import Any, Dict, Optional

from ..contracts import (
    baseline_generation,
    close_generation,
    contract_table,
    frequency_generation,
    load_generation,
    phase_generation,
    release_generation,
    start_generation,
)
from ..runtime.errors import ControlError, ValidationError
from .health import health_response
from .meta import service_meta
from .pages import PageCatalog
from .response import Response, html_response, json_response
from .router import PathNotFound, Router

SCOPES = ("visible", "pending", "discarded", "tombstones", "all")


class Console:
    def __init__(self, hub, pages_root: Any = None) -> None:
        self._hub = hub
        self._pages = PageCatalog(pages_root)
        self._router = Router()
        self._register()

    @property
    def hub(self):
        return self._hub

    @property
    def pages(self) -> PageCatalog:
        return self._pages

    def dispatch(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Response:
        try:
            handler, params = self._router.resolve(method, path)
        except PathNotFound as exc:
            return json_response(exc.status, exc.to_payload())
        try:
            return handler(params, query or {}, body or {})
        except ControlError as exc:
            return json_response(exc.status, exc.to_payload())
        except (ValueError, TypeError) as exc:
            return json_response(400, {"error": "bad_request", "message": str(exc)})

    def _register(self) -> None:
        add = self._router.add
        add("GET", "/healthz", self._health)
        add("GET", "/api/meta", self._meta)
        add("GET", "/api/contracts", self._contracts)
        add("GET", "/api/state", self._state)
        add("GET", "/api/state/alarms", self._alarms)
        add("GET", "/api/config", self._config_get)
        add("POST", "/api/config", self._config_set)
        add("GET", "/api/store/records", self._records)
        add("GET", "/api/audit", self._audit)
        add("GET", "/api/audit/stats", self._audit_stats)
        add("GET", "/api/flows", self._flows)
        add("GET", "/api/flows/{name}", self._flow_detail)
        add("POST", "/api/flows/{name}/run", self._flow_run)
        add("GET", "/api/lube", self._lube)
        add("POST", "/api/lube/pressure", self._lube_pressure)
        add("POST", "/api/lube/acknowledge", self._lube_acknowledge)
        add("POST", "/api/lube/latch/clear", self._lube_clear)
        add("GET", "/api/engine", self._engine)
        add("POST", "/api/engine/crank", self._engine_crank)
        add("POST", "/api/engine/start", self._engine_start)
        add("POST", "/api/engine/stop", self._engine_stop)
        add("GET", "/api/sync", self._sync)
        add("POST", "/api/sync/baseline", self._sync_baseline)
        add("POST", "/api/sync/persist", self._sync_persist)
        add("POST", "/api/sync/commit", self._sync_commit)
        add("POST", "/api/sync/confirm", self._sync_confirm)
        add("GET", "/api/breaker", self._breaker)
        add("POST", "/api/breaker/close", self._breaker_close)
        add("POST", "/api/breaker/open", self._breaker_open)
        add("POST", "/api/breaker/trip", self._breaker_trip)
        add("POST", "/api/breaker/latch/release", self._breaker_release)
        add("GET", "/api/gov", self._gov)
        add("POST", "/api/gov/adjust", self._gov_adjust)
        add("GET", "/api/load", self._load)
        add("POST", "/api/load/adjust", self._load_adjust)
        add("POST", "/api/load/share", self._load_share)
        add("GET", "/api/avr", self._avr)
        add("POST", "/api/avr/excite", self._avr_excite)
        add("POST", "/api/avr/deexcite", self._avr_deexcite)
        add("GET", "/api/fuel", self._fuel)
        add("POST", "/api/fuel/deliver", self._fuel_deliver)
        add("GET", "/api/metrics", self._metrics)
        add("POST", "/api/snapshot", self._snapshot)
        add("GET", "/", self._page_overview)
        add("GET", "/overview", self._page_overview)
        add("GET", "/operations", self._page_operations)
        add("GET", "/audit", self._page_audit)
        add("GET", "/api/routes", self._routes)

    def _number(self, body: Dict[str, Any], key: str, required: bool = True, default: float = 0.0) -> float:
        if key not in body or body[key] is None:
            if required:
                raise ValidationError("field is required", field=key)
            return float(default)
        value = body[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError("field must be numeric", field=key)
        return float(value)

    def _text(self, body: Dict[str, Any], key: str, default: Optional[str] = None) -> str:
        if key not in body or body[key] is None:
            if default is None:
                raise ValidationError("field is required", field=key)
            return default
        value = body[key]
        if not isinstance(value, str) or not value:
            raise ValidationError("field must be a non empty string", field=key)
        return value

    def _health(self, params, query, body) -> Response:
        return health_response(self._hub)

    def _meta(self, params, query, body) -> Response:
        return json_response(200, service_meta(self._hub, self._pages))

    def _routes(self, params, query, body) -> Response:
        payload = self._router.describe()
        payload["pages"] = self._pages.describe()
        return json_response(200, payload)

    def _contracts(self, params, query, body) -> Response:
        registry = self._hub.registry
        return json_response(
            200,
            {
                "contracts": contract_table(),
                "generations": {
                    "baseline": baseline_generation(registry),
                    "phase": phase_generation(registry),
                    "frequency": frequency_generation(registry),
                    "close": close_generation(registry),
                    "release": release_generation(registry),
                    "start": start_generation(registry),
                    "load": load_generation(registry),
                },
                "key_generations": registry.generations(),
            },
        )

    def _state(self, params, query, body) -> Response:
        return json_response(200, self._hub.view.describe())

    def _alarms(self, params, query, body) -> Response:
        scope = query.get("scope", "current")
        if scope == "historical":
            entries = self._hub.projector.alarms()
        elif scope == "current":
            entries = self._hub.view.alarms()
        else:
            raise ValidationError("unknown alarm scope", scope=scope)
        return json_response(200, {"scope": scope, "alarms": [item.describe() for item in entries]})

    def _config_get(self, params, query, body) -> Response:
        registry = self._hub.registry
        return json_response(
            200,
            {
                "revision": registry.revision,
                "parameters": registry.snapshot(),
                "generations": registry.generations(),
            },
        )

    def _config_set(self, params, query, body) -> Response:
        key = self._text(body, "key")
        value = self._number(body, "value")
        return json_response(200, self._hub.set_parameter(key, value))

    def _records(self, params, query, body) -> Response:
        scope = query.get("scope", "visible")
        if scope not in SCOPES:
            raise ValidationError("unknown record scope", scope=scope)
        log = self._hub.log
        source = {
            "visible": log.visible,
            "pending": log.pending,
            "discarded": log.discarded,
            "tombstones": log.tombstones,
            "all": log.records,
        }[scope]()
        batch = query.get("batch", "")
        kind = query.get("kind", "")
        selected = [record for record in source if (not batch or record.batch_id == batch)]
        selected = [record for record in selected if (not kind or record.kind == kind)]
        return json_response(
            200,
            {
                "scope": scope,
                "watermark": log.watermark,
                "tail": log.max_seq(),
                "records": [record.describe() for record in selected],
            },
        )

    def _audit(self, params, query, body) -> Response:
        entries = self._hub.audit_query(
            action=query.get("action", ""),
            outcome=query.get("outcome", ""),
            batch_id=query.get("batch", ""),
        )
        return json_response(200, {"count": len(entries), "entries": entries})

    def _audit_stats(self, params, query, body) -> Response:
        return json_response(200, self._hub.metrics_report())

    def _flows(self, params, query, body) -> Response:
        payload = self._hub.planner.describe()
        payload["flow_params"] = self._hub.flow_params()
        return json_response(200, payload)

    def _flow_detail(self, params, query, body) -> Response:
        name = params["name"]
        plan = self._hub.planner.plan(name)
        payload = plan.describe()
        payload["prerequisites"] = self._hub.planner.prerequisites(name)
        payload["required_arguments"] = self._hub.flow_params().get(name, [])
        return json_response(200, payload)

    def _flow_run(self, params, query, body) -> Response:
        name = params["name"]
        arguments = body.get("params") if isinstance(body.get("params"), dict) else body
        return json_response(200, self._hub.run_flow(name, dict(arguments)))

    def _lube(self, params, query, body) -> Response:
        return json_response(200, self._hub.lube.status())

    def _lube_pressure(self, params, query, body) -> Response:
        self._hub.build_pressure(self._number(body, "bar"))
        return json_response(200, self._hub.lube.status())

    def _lube_acknowledge(self, params, query, body) -> Response:
        self._hub.acknowledge_lube()
        return json_response(200, self._hub.lube.status())

    def _lube_clear(self, params, query, body) -> Response:
        self._hub.clear_lube_latch()
        return json_response(200, self._hub.lube.status())

    def _engine(self, params, query, body) -> Response:
        return json_response(200, self._hub.engine.status())

    def _engine_crank(self, params, query, body) -> Response:
        self._hub.crank()
        return json_response(200, self._hub.engine.status())

    def _engine_start(self, params, query, body) -> Response:
        self._hub.start_engine()
        return json_response(200, self._hub.engine.status())

    def _engine_stop(self, params, query, body) -> Response:
        self._hub.stop_engine()
        return json_response(200, self._hub.engine.status())

    def _sync(self, params, query, body) -> Response:
        return json_response(200, self._hub.sync.status())

    def _sync_baseline(self, params, query, body) -> Response:
        ttl = body.get("ttl_ticks")
        result = self._hub.calibrate(
            self._number(body, "phase_deg"),
            self._number(body, "freq_hz"),
            int(ttl) if isinstance(ttl, (int, float)) and not isinstance(ttl, bool) else None,
        )
        return json_response(200, result)

    def _sync_persist(self, params, query, body) -> Response:
        return json_response(200, self._hub.persist_sync(self._text(body, "batch")))

    def _sync_commit(self, params, query, body) -> Response:
        return json_response(200, self._hub.commit_sync(self._text(body, "batch")))

    def _sync_confirm(self, params, query, body) -> Response:
        return json_response(200, self._hub.confirm_frequency(self._number(body, "measured_hz")))

    def _breaker(self, params, query, body) -> Response:
        return json_response(200, self._hub.breaker.status())

    def _breaker_close(self, params, query, body) -> Response:
        result = self._hub.close_breaker(
            self._text(body, "batch"),
            self._text(body, "ticket"),
            self._number(body, "phase_deg"),
        )
        return json_response(200, result)

    def _breaker_open(self, params, query, body) -> Response:
        return json_response(200, self._hub.open_breaker(self._text(body, "reason", "operator open")))

    def _breaker_trip(self, params, query, body) -> Response:
        return json_response(200, self._hub.trip_breaker(self._text(body, "reason", "protection trip")))

    def _breaker_release(self, params, query, body) -> Response:
        self._hub.release_breaker_latch()
        return json_response(200, self._hub.breaker.status())

    def _gov(self, params, query, body) -> Response:
        return json_response(200, self._hub.gov.status())

    def _gov_adjust(self, params, query, body) -> Response:
        result = self._hub.adjust_governor(
            self._number(body, "target_hz"), self._text(body, "ticket")
        )
        return json_response(200, result)

    def _load(self, params, query, body) -> Response:
        return json_response(200, self._hub.load.status())

    def _load_adjust(self, params, query, body) -> Response:
        return json_response(200, self._hub.adjust_load(self._number(body, "kw")))

    def _load_share(self, params, query, body) -> Response:
        units = int(self._number(body, "units"))
        return json_response(200, self._hub.share_load(self._number(body, "total_kw"), units))

    def _avr(self, params, query, body) -> Response:
        return json_response(200, self._hub.avr.status())

    def _avr_excite(self, params, query, body) -> Response:
        voltage = body.get("voltage")
        value = float(voltage) if isinstance(voltage, (int, float)) and not isinstance(voltage, bool) else None
        return json_response(200, self._hub.excite(value))

    def _avr_deexcite(self, params, query, body) -> Response:
        return json_response(200, self._hub.deexcite())

    def _fuel(self, params, query, body) -> Response:
        return json_response(200, self._hub.fuel.status())

    def _fuel_deliver(self, params, query, body) -> Response:
        return json_response(200, self._hub.deliver_fuel(self._number(body, "liters")))

    def _metrics(self, params, query, body) -> Response:
        return json_response(200, self._hub.metrics_report())

    def _snapshot(self, params, query, body) -> Response:
        return json_response(200, self._hub.write_snapshot())

    def _page_overview(self, params, query, body) -> Response:
        return html_response(self._pages.read("overview"))

    def _page_operations(self, params, query, body) -> Response:
        return html_response(self._pages.read("operations"))

    def _page_audit(self, params, query, body) -> Response:
        return html_response(self._pages.read("audit"))
