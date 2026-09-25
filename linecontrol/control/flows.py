"""The start, parallel and stop sequences expressed as ordered plans."""

from typing import Dict

from ..planner.plan import FlowPlan, Step

FLOW_START = "start"
FLOW_PARALLEL = "parallel"
FLOW_STOP = "stop"


def start_flow() -> FlowPlan:
    return FlowPlan(
        name=FLOW_START,
        title="bring the unit up to speed",
        steps=(
            Step("lube.pressure", "lube", "establish oil pressure before anything turns"),
            Step(
                "engine.crank",
                "engine",
                "turn the unit against established pressure",
                requires=("lube.pressure",),
                gate="oil pressure established and latch clear",
            ),
            Step(
                "engine.start",
                "engine",
                "release the unit to running speed",
                requires=("engine.crank",),
                gate="crank completed on the same pressure",
            ),
        ),
    )


def parallel_flow() -> FlowPlan:
    return FlowPlan(
        name=FLOW_PARALLEL,
        title="match, close and load the unit",
        steps=(
            Step("sync.baseline", "sync", "take the phase and frequency baseline"),
            Step(
                "sync.persist",
                "sync",
                "append the sync result for the batch",
                requires=("sync.baseline",),
                gate="baseline inside its lifetime and generation",
            ),
            Step(
                "sync.commit",
                "sync",
                "commit the watermark so the result becomes visible",
                requires=("sync.persist",),
                gate="a pending sync result exists for the batch",
            ),
            Step(
                "sync.confirm",
                "sync",
                "compare the measured frequency and raise a confirmation",
                requires=("sync.commit",),
                gate="committed sync result and a live baseline",
            ),
            Step(
                "breaker.close",
                "breaker",
                "close the line breaker on the confirmed phase",
                requires=("sync.confirm",),
                gate="committed sync result plus an unexpired confirmation",
            ),
            Step(
                "load.adjust",
                "load",
                "take up load inside the unit capacity",
                requires=("breaker.close",),
                gate="closed breaker",
            ),
        ),
    )


def stop_flow() -> FlowPlan:
    return FlowPlan(
        name=FLOW_STOP,
        title="take the unit off the line",
        steps=(
            Step("breaker.open", "breaker", "open the line breaker first"),
            Step(
                "avr.deexcite",
                "avr",
                "remove excitation once the unit is off the line",
                requires=("breaker.open",),
                gate="open breaker",
            ),
            Step(
                "engine.stop",
                "engine",
                "stop the prime mover last",
                requires=("avr.deexcite",),
                gate="excitation removed",
            ),
        ),
    )


def default_plans() -> Dict[str, FlowPlan]:
    plans = (start_flow(), parallel_flow(), stop_flow())
    return {plan.name: plan for plan in plans}
