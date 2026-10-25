"""The run loop: flip the lever -> read blocks -> compile -> simulate -> draw.

Kept separate from the compiler and renderer. Time is injectable (`sleep`) so the
loop can be tested without waiting.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from random import Random

from qengine import QuantumState, draw_circuit, format_state, measure_qubit

from .bridge import BridgeError, WorldBridge
from .compiler import CompiledCircuit, CompileError, compile_grid, read_grid
from .config import WorkbenchConfig
from .renderer import BarRenderer
from .style import Stylist

MAX_CHAT_ERRORS = 4


@dataclass
class RunResult:
    compiled: CompiledCircuit | None = None
    state: QuantumState | None = None
    measured_bits: dict[int, int] | None = None
    error: CompileError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Controller:
    def __init__(
        self,
        bridge: WorldBridge,
        cfg: WorkbenchConfig,
        renderer: BarRenderer | None = None,
        rng: Random | None = None,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval: float = 0.15,
        log: Callable[[str], None] = print,
        use_hits: bool = False,
    ) -> None:
        self.bridge = bridge
        self.cfg = cfg
        self.renderer = renderer or BarRenderer(bridge, cfg)
        self.rng = rng or Random()
        self.sleep = sleep
        self.poll_interval = poll_interval
        self.log = log
        self.use_hits = use_hits
        self._was_powered = False

    # ---- one run -----------------------------------------------------------

    def run_once(self) -> RunResult:
        grid = read_grid(self.bridge, self.cfg)
        Stylist(self.bridge, self.cfg).gates(grid)  # labels follow what is really on the board
        try:
            compiled = compile_grid(grid, self.cfg.palette)
        except CompileError as err:
            self.log("Compile error:")
            for d in err.diagnostics:
                self.log(f"  {d}")
            self.bridge.say("Circuit error:")
            for d in err.diagnostics[:MAX_CHAT_ERRORS]:
                self.bridge.say(str(d))
            if len(err.diagnostics) > MAX_CHAT_ERRORS:
                self.bridge.say(f"...and {len(err.diagnostics) - MAX_CHAT_ERRORS} more")
            return RunResult(error=err)

        circuit = compiled.circuit
        state = circuit.run()
        bits: dict[int, int] | None = None
        if compiled.measured:
            collapsed = state.copy()
            bits = {q: measure_qubit(collapsed, q, self.rng) for q in compiled.measured}

        self.renderer.draw_state(state)
        self.renderer.draw_measurement(bits, circuit.n_qubits)

        self.log(draw_circuit(circuit))
        self.log(format_state(state))
        if bits is not None:
            self.log("measured: " + ", ".join(f"q{q}={b}" for q, b in sorted(bits.items())))
        summary = f"Ran {len(circuit)} gates on {circuit.n_qubits} qubits: {state.ket()}"
        if bits is not None:
            summary += " | measured " + " ".join(f"q{q}={b}" for q, b in sorted(bits.items()))
        self.bridge.say(summary)
        return RunResult(compiled=compiled, state=state, measured_bits=bits)

    # ---- trigger -----------------------------------------------------------

    def triggered(self) -> bool:
        """True exactly once per lever flick (rising edge), or per hit on the lever."""
        powered = self.bridge.lever_powered(self.cfg.lever_pos)
        edge = powered and not self._was_powered
        self._was_powered = powered
        if self.use_hits:
            hits = self.bridge.poll_hits()
            if any(h == self.cfg.lever_pos for h in hits):
                return True
        return edge

    def poll(self) -> RunResult | None:
        """One poll step: if triggered, run once and switch the lever back off."""
        if not self.triggered():
            return None
        result = self.run_once()
        self.bridge.set_lever(self.cfg.lever_pos, False)
        # Trust the world, not our assumption: if the reset didn't take, the lever is still
        # on and must not count as a fresh flick on the next poll.
        self._was_powered = self.bridge.lever_powered(self.cfg.lever_pos)
        return result

    def watch(self, max_polls: int | None = None) -> int:
        """Poll until interrupted (or `max_polls` polls). Returns how many runs happened."""
        runs = polls = 0
        try:
            while max_polls is None or polls < max_polls:
                polls += 1
                try:
                    if self.poll() is not None:
                        runs += 1
                except BridgeError as exc:
                    self.log(f"bridge error: {exc}")
                    raise
                self.sleep(self.poll_interval)
        except KeyboardInterrupt:
            self.log("stopped")
        return runs
