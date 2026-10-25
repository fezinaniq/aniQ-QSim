"""M8 tests: lever trigger and controller loop (no real waiting)."""

import random

from mc.bridge import FakeBridge
from mc.config import WorkbenchConfig
from mc.controller import Controller
from mc.workbench import build_workbench, place_circuit
from qengine import parse_circuit

CFG = WorkbenchConfig(origin=(10, 64, 10))


def make(circuit="h 0; cnot 0 1", measure=()):
    fb = FakeBridge()
    place_circuit(fb, CFG, parse_circuit(circuit), measure)
    logs: list[str] = []
    ctrl = Controller(fb, CFG, rng=random.Random(1), sleep=lambda s: None, log=logs.append)
    return fb, ctrl, logs


def test_no_run_until_the_lever_is_flipped():
    fb, ctrl, _ = make()
    assert ctrl.poll() is None
    assert ctrl.poll() is None
    assert fb.chat == []


def test_flip_runs_once_and_resets_lever():
    fb, ctrl, _ = make()
    fb.flip_lever(CFG.lever_pos)
    result = ctrl.poll()
    assert result is not None and result.ok
    assert result.state.probabilities() == [0.5, 0, 0, 0.5] or abs(
        result.state.probabilities()[0] - 0.5
    ) < 1e-9
    assert fb.chat, "the run should announce itself in chat"
    assert not fb.lever_powered(CFG.lever_pos)
    assert ctrl.poll() is None  # lever is back off: nothing more happens


def test_one_flick_is_one_run_even_if_reset_fails():
    fb, ctrl, _ = make()
    fb.set_lever = lambda pos, powered: None  # type: ignore[method-assign]  # reset does nothing
    fb.flip_lever(CFG.lever_pos)
    assert ctrl.poll() is not None
    assert ctrl.poll() is None  # still powered, but that is not a new flick
    assert ctrl.poll() is None


def test_two_flicks_two_runs():
    fb, ctrl, _ = make()
    runs = 0
    for _ in range(2):
        fb.flip_lever(CFG.lever_pos)
        runs += ctrl.poll() is not None
    assert runs == 2


def test_hit_on_lever_triggers_when_enabled():
    fb, ctrl, _ = make()
    ctrl.use_hits = True
    fb.hits.append((0, 0, 0))
    assert ctrl.poll() is None
    fb.hits.append(CFG.lever_pos)
    assert ctrl.poll() is not None


def test_hits_ignored_by_default():
    fb, ctrl, _ = make()
    fb.hits.append(CFG.lever_pos)
    assert ctrl.poll() is None


def test_run_draws_bars_and_chats_summary():
    fb, ctrl, _ = make()
    ctrl.run_once()
    assert any("Ran 2 gates on 2 qubits" in m for m in fb.chat)
    # bars for |00> and |11> exist, |01> and |10> do not
    top = CFG.origin[1] + 4
    assert fb.blocks[(CFG.bar_x(0, 2), top, CFG.bar_z)].endswith("concrete")
    assert fb.blocks[(CFG.bar_x(3, 2), top, CFG.bar_z)].endswith("concrete")
    assert (CFG.bar_x(1, 2), CFG.origin[1], CFG.bar_z) not in fb.blocks


def test_compile_errors_go_to_chat_and_log_not_exceptions():
    fb, ctrl, logs = make()
    fb.set_block(CFG.cell(5, 0), "stone")
    result = ctrl.run_once()
    assert not result.ok and result.state is None
    assert any("unknown block 'stone'" in m for m in fb.chat)
    assert any("Compile error" in line for line in logs)
    assert not any(p[2] == CFG.bar_z and fb.blocks[p].endswith("concrete") for p in fb.blocks)


def test_many_errors_are_truncated_in_chat():
    fb = FakeBridge()
    build_workbench(fb, CFG, qubits=1)
    for step in range(8):
        fb.set_block(CFG.cell(step, 0), "stone")
    Controller(fb, CFG, log=lambda s: None).run_once()
    assert any("more" in m for m in fb.chat)
    assert len(fb.chat) <= 7


def test_measurement_lamps_light_for_one_collapsed_outcome():
    fb, ctrl, _ = make(measure=[0, 1])
    result = ctrl.run_once()
    b0, b1 = result.measured_bits[0], result.measured_bits[1]
    assert b0 == b1  # Bell state: outcomes always agree
    lamp = lambda q: fb.blocks.get((CFG.lamp_x(q), CFG.origin[1] - 1, CFG.lamp_z))
    expected = "glowstone" if b0 else "gray_concrete"
    assert lamp(0) == expected and lamp(1) == expected
    # the bars still show the full distribution (pre-measurement)
    assert (CFG.bar_x(0, 2), CFG.origin[1], CFG.bar_z) in fb.blocks
    assert (CFG.bar_x(3, 2), CFG.origin[1], CFG.bar_z) in fb.blocks


def test_measurement_outcomes_follow_the_born_rule():
    _fb, ctrl, _ = make("h 0", measure=[0])
    ones = sum(ctrl.run_once().measured_bits[0] for _ in range(400))
    assert 140 < ones < 260


def test_deterministic_x_measurement():
    _fb, ctrl, _ = make("x 0", measure=[0])
    assert ctrl.run_once().measured_bits == {0: 1}


def test_watch_counts_runs_and_sleeps_between_polls():
    fb, ctrl, _ = make()
    sleeps: list[float] = []

    def sleep(s):
        sleeps.append(s)
        if len(sleeps) == 2:
            fb.flip_lever(CFG.lever_pos)  # a player flips it during the second wait

    ctrl.sleep = sleep
    assert ctrl.watch(max_polls=5) == 1
    assert len(sleeps) == 5 and set(sleeps) == {ctrl.poll_interval}


def test_rerun_after_editing_the_blocks_changes_the_result():
    fb, ctrl, _ = make("h 0")
    first = ctrl.run_once().state.probabilities()
    place_circuit(fb, CFG, parse_circuit("x 0"))
    second = ctrl.run_once().state.probabilities()
    assert first[0] == first[1] == max(first) and second == [0, 1]
