"""Application wiring: one object owns every subsystem for a data directory."""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .audit.journal import AuditJournal
from .audit.stats import summarize
from .avr.service import ExcitationService
from .breaker.service import BreakerService
from .config.parameters import ParameterRegistry
from .config.schema import load_overrides
from .confirm.ticket import TicketRegistry
from .control.flows import FLOW_PARALLEL, FLOW_START, FLOW_STOP, default_plans
from .control.runner import FlowOutcome, FlowRunner
from .engine.service import EngineService
from .fuel.service import FuelService
from .gov.service import GovernorService
from .load.service import LoadService
from .lube.service import LubeService
from .metrics.counters import MetricRegistry
from .metrics.report import operation_report
from .planner.plan import SequencePlanner, Step
from .probe.probe import HealthProbe
from .runtime.clock import VirtualClock
from .runtime.errors import ControlError, ValidationError
from .runtime.ids import IdSequencer
from .state.projection import StateProjector
from .state.snapshot import RestoreResult, StateSnapshotter
from .state.view import MachineView
from .store.kinds import KIND_CONFIG_PARAM
from .store.log import AppendOnlyLog
from .sync.service import SyncService

ACTOR = "operator"

RECORD_FILE = "records.jsonl"
AUDIT_FILE = "audit.jsonl"
SNAPSHOT_FILE = "state.snapshot.json"

FLOW_PARAMS: Dict[str, List[str]] = {
    FLOW_START: ["pressure_bar"],
    FLOW_PARALLEL: ["batch", "measured_hz", "phase_deg", "load_kw"],
    FLOW_STOP: [],
}


def _safe_detail(mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Audit entries only carry values that survive a JSON round trip."""

    scalar = (str, int, float, bool)
    safe: Dict[str, Any] = {}
    for key, value in mapping.items():
        if value is None or isinstance(value, scalar):
            safe[str(key)] = value
        elif isinstance(value, dict):
            safe[str(key)] = {
                str(inner_key): inner
                for inner_key, inner in value.items()
                if inner is None or isinstance(inner, scalar)
            }
        elif isinstance(value, (list, tuple)):
            safe[str(key)] = [item for item in value if item is None or isinstance(item, scalar)]
        else:
            safe[str(key)] = str(value)
    return safe


class ControlHub:
    """Owns the record store, the tuned parameters and every process subsystem."""

    def __init__(self, data_dir: Any = "var", config_path: Optional[Any] = None) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.clock = VirtualClock()
        self.ids = IdSequencer()
        self.registry = ParameterRegistry()
        self.metrics = MetricRegistry()

        overrides: Dict[str, Any] = {}
        if config_path is not None:
            overrides = load_overrides(Path(config_path))
        if overrides:
            self.registry.apply_overrides(overrides, self.clock.tick)

        self.log = AppendOnlyLog(self.data_dir / RECORD_FILE, self.ids, "REC")
        self.audit_log = AppendOnlyLog(self.data_dir / AUDIT_FILE, self.ids, "AUD")
        resume_tick = max(
            [record.tick for record in self.log.records()]
            + [record.tick for record in self.audit_log.records()],
            default=0,
        )
        if resume_tick > 0:
            self.clock.advance(resume_tick)
        self.tickets = TicketRegistry(self.ids)
        self.projector = StateProjector(self.log)
        self.view = MachineView(self.log, self.projector)
        self.journal = AuditJournal(self.audit_log, self.clock)
        self.snapshots = StateSnapshotter(
            self.log, self.audit_log, self.clock, self.registry, self.data_dir / SNAPSHOT_FILE
        )

        self.lube = LubeService(self.log, self.clock, self.registry, self.view)
        self.engine = EngineService(self.log, self.clock, self.registry, self.view, self.lube)
        self.sync = SyncService(self.log, self.clock, self.registry, self.projector, self.tickets)
        self.load = LoadService(self.log, self.clock, self.registry, self.view, self.view.closed)
        self.breaker = BreakerService(
            self.log, self.clock, self.registry, self.view, self.tickets, self.sync, self.view.load_kw
        )
        self.gov = GovernorService(
            self.log, self.clock, self.registry, self.view, self.tickets, self.view.closed
        )
        self.avr = ExcitationService(
            self.log, self.clock, self.registry, self.view, self.view.running, self.view.closed
        )
        self.fuel = FuelService(self.log, self.clock, self.registry)

        self.planner = SequencePlanner(default_plans().values())
        self.runner = FlowRunner(self.planner)
        self.probe = HealthProbe(self.log, self.audit_log, self.snapshots.path)

        if not self.log.records() and overrides:
            self._record_config(overrides)

    def _record_config(self, overrides: Dict[str, Any]) -> None:
        for key in sorted(overrides):
            self.log.append(
                KIND_CONFIG_PARAM,
                generation=self.registry.generation(key),
                payload={"key": key, "value": self.registry.value(key), "source": "config"},
                tick=self.clock.tick,
            )
        self.log.commit(tick=self.clock.tick)

    def command(self, action: str, operation: Callable[[], Any], batch_id: str = "") -> Any:
        """One audited, clock advancing command."""

        self.clock.advance()
        self.metrics.incr("command.total")
        try:
            detail = operation()
        except ControlError as exc:
            failure = dict(exc.detail)
            failure["message"] = exc.message
            self.journal.record(action, ACTOR, exc.code, batch_id, _safe_detail(failure))
            self.journal.commit()
            self.metrics.incr("command.rejected")
            raise
        payload = detail if isinstance(detail, dict) else {"result": detail}
        self.journal.record(action, ACTOR, "ok", batch_id, _safe_detail(payload))
        self.journal.commit()
        self.metrics.incr("command.ok")
        return detail

    def restore(self) -> RestoreResult:
        result = self.snapshots.restore()
        self.view.invalidate()
        self.metrics.gauge("restore.replayed", result.replayed)
        return result

    def write_snapshot(self) -> Dict[str, Any]:
        path = self.snapshots.write()
        payload = self.snapshots.capture()
        self.metrics.incr("snapshot.written")
        return {"path": str(path), "watermark": payload.watermark, "tick": payload.tick}

    def flow_params(self) -> Dict[str, List[str]]:
        return {name: list(keys) for name, keys in FLOW_PARAMS.items()}

    def require_params(self, name: str, params: Dict[str, Any]) -> None:
        if name not in FLOW_PARAMS:
            raise ValidationError("unknown flow", flow=name)
        missing = [key for key in FLOW_PARAMS[name] if key not in params]
        if missing:
            raise ValidationError("flow is missing required arguments", flow=name, missing=missing)

    def build_pressure(self, pressure_bar: float) -> Dict[str, Any]:
        return self.command("lube.pressure", lambda: self.lube.build_pressure(pressure_bar))

    def acknowledge_lube(self) -> Dict[str, Any]:
        return self.command("lube.acknowledge", self.lube.acknowledge)

    def clear_lube_latch(self) -> Dict[str, Any]:
        return self.command("lube.latch.clear", self.lube.clear_latch)

    def crank(self) -> Dict[str, Any]:
        return self.command("engine.crank", self.engine.crank)

    def start_engine(self) -> Dict[str, Any]:
        return self.command("engine.start", self.engine.start)

    def stop_engine(self) -> Dict[str, Any]:
        return self.command("engine.stop", self.engine.stop)

    def calibrate(self, phase_deg: float, freq_hz: float, ttl_ticks: Optional[int] = None) -> Dict[str, Any]:
        return self.command(
            "sync.baseline",
            lambda: self.sync.calibrate(phase_deg, freq_hz, ttl_ticks).describe(),
        )

    def persist_sync(self, batch_id: str) -> Dict[str, Any]:
        return self.command("sync.persist", lambda: self.sync.persist(batch_id), batch_id)

    def commit_sync(self, batch_id: str) -> Dict[str, Any]:
        return self.command("sync.commit", lambda: self.sync.commit(batch_id), batch_id)

    def confirm_frequency(self, measured_hz: float) -> Dict[str, Any]:
        return self.command("sync.confirm", lambda: self.sync.confirm_frequency(measured_hz))

    def close_breaker(self, batch_id: str, ticket_id: str, phase_deg: float) -> Dict[str, Any]:
        return self.command(
            "breaker.close",
            lambda: self.breaker.close(batch_id, ticket_id, phase_deg),
            batch_id,
        )

    def open_breaker(self, reason: str) -> Dict[str, Any]:
        return self.command("breaker.open", lambda: self.breaker.open(reason))

    def trip_breaker(self, reason: str) -> Dict[str, Any]:
        return self.command("breaker.trip", lambda: self.breaker.trip(reason))

    def release_breaker_latch(self) -> Dict[str, Any]:
        return self.command("breaker.latch.release", self.breaker.release_latch)

    def adjust_governor(self, target_hz: float, ticket_id: str) -> Dict[str, Any]:
        return self.command("gov.adjust", lambda: self.gov.adjust(target_hz, ticket_id))

    def adjust_load(self, load_kw: float) -> Dict[str, Any]:
        return self.command("load.adjust", lambda: self.load.adjust(load_kw))

    def share_load(self, total_kw: float, units: int) -> Dict[str, Any]:
        return self.command("load.share", lambda: self.load.share(total_kw, units))

    def excite(self, voltage: Optional[float] = None) -> Dict[str, Any]:
        return self.command("avr.excite", lambda: self.avr.excite(voltage))

    def deexcite(self) -> Dict[str, Any]:
        return self.command("avr.deexcite", self.avr.deexcite)

    def deliver_fuel(self, liters: float) -> Dict[str, Any]:
        return self.command("fuel.deliver", lambda: self.fuel.deliver(liters))

    def set_parameter(self, key: str, value: Any) -> Dict[str, Any]:
        def apply() -> Dict[str, Any]:
            parameter = self.registry.set(key, value, self.clock.tick)
            record = self.log.append(
                KIND_CONFIG_PARAM,
                generation=parameter.generation,
                payload={"key": parameter.key, "value": parameter.value, "source": "command"},
                tick=self.clock.tick,
            )
            self.log.commit(tick=self.clock.tick)
            return {
                "parameter": parameter.describe(),
                "record": record.record_id,
                "watermark": self.log.watermark,
            }

        return self.command("config.set", apply)

    def _start_handler(self, params: Dict[str, Any]):
        pressure = float(params["pressure_bar"])

        def handler(step: Step, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if step.name == "lube.pressure":
                return self.lube.build_pressure(pressure)
            if step.name == "engine.crank":
                return self.engine.crank()
            if step.name == "engine.start":
                return self.engine.start()
            return None

        return handler

    def _parallel_handler(self, params: Dict[str, Any]):
        batch = str(params["batch"])
        measured = float(params["measured_hz"])
        phase = float(params["phase_deg"])
        load_kw = float(params["load_kw"])
        ttl = params.get("ttl_ticks")
        reference_phase = float(params.get("reference_phase_deg", 0.0))
        nominal_hz = float(self.registry.value("gov.target_hz"))

        def handler(step: Step, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if step.name == "sync.baseline":
                return self.sync.calibrate(reference_phase, nominal_hz, ttl).describe()
            if step.name == "sync.persist":
                return self.sync.persist(batch)
            if step.name == "sync.commit":
                return self.sync.commit(batch)
            if step.name == "sync.confirm":
                return self.sync.confirm_frequency(measured)
            if step.name == "breaker.close":
                ticket = str(results["sync.confirm"]["ticket"])
                return self.breaker.close(batch, ticket, phase)
            if step.name == "load.adjust":
                return self.load.adjust(load_kw)
            return None

        return handler

    def _stop_handler(self, params: Dict[str, Any]):
        reason = str(params.get("reason", "operator stop"))

        def handler(step: Step, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if step.name == "breaker.open":
                return self.breaker.open(reason)
            if step.name == "avr.deexcite":
                return self.avr.deexcite()
            if step.name == "engine.stop":
                return self.engine.stop()
            return None

        return handler

    def run_flow(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.require_params(name, params)
        builders = {
            FLOW_START: self._start_handler,
            FLOW_PARALLEL: self._parallel_handler,
            FLOW_STOP: self._stop_handler,
        }
        handler = builders[name](params)
        batch_id = str(params.get("batch", ""))

        def execute() -> Dict[str, Any]:
            outcome: FlowOutcome = self.runner.run(name, handler)
            if not outcome.ok:
                if outcome.error is None:
                    raise ValidationError("flow failed without a reported reason", flow=name)
                raise outcome.error
            return outcome.describe()

        return self.command("flow." + name, execute, batch_id)

    def audit_query(self, action: str = "", outcome: str = "", batch_id: str = "") -> List[Dict[str, Any]]:
        entries = self.journal.entries()
        selected = []
        for entry in entries:
            if action and entry.action != action:
                continue
            if outcome and entry.outcome != outcome:
                continue
            if batch_id and entry.batch_id != batch_id:
                continue
            selected.append(entry.describe())
        return selected

    def metrics_report(self) -> Dict[str, Any]:
        return operation_report(
            self.metrics,
            summarize(self.journal.entries()),
            self.tickets.summary(self.clock.tick),
        )

    def status(self) -> Dict[str, Any]:
        return {
            "state": self.view.describe(),
            "clock": {"tick": self.clock.tick, "step": self.clock.step, "stamp": self.clock.stamp()},
            "config_revision": self.registry.revision,
            "store": self.log.summary(),
            "audit": summarize(self.journal.entries()).describe(),
            "confirmations": self.tickets.summary(self.clock.tick),
            "subsystems": {
                "lube": self.lube.status(),
                "engine": self.engine.status(),
                "sync": self.sync.status(),
                "breaker": self.breaker.status(),
                "gov": self.gov.status(),
                "load": self.load.status(),
                "avr": self.avr.status(),
                "fuel": self.fuel.status(),
            },
        }
