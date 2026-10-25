"""M9 tests: phase colours, probability bars, diffing, read-out, lamps."""

import math

import pytest

from mc.bridge import FakeBridge
from mc.colors import WHEEL, phase_block, phase_slot, reference_amplitude
from mc.config import WorkbenchConfig
from mc.renderer import BarRenderer, bar_height
from qengine import QuantumCircuit, QuantumState

CFG = WorkbenchConfig(origin=(0, 64, 0))
Y0 = CFG.origin[1]


def bar_blocks(fb, i, n):
    """Blocks of bar i from the floor layer upward, until the first gap."""
    out, level = [], 0
    while True:
        b = fb.blocks.get((CFG.bar_x(i, n), Y0 + level, CFG.bar_z))
        if b is None:
            return out
        out.append(b)
        level += 1


# ---- colours -------------------------------------------------------------------------

def test_wheel_has_twelve_distinct_colours():
    assert len(WHEEL) == 12 and len(set(WHEEL)) == 12


def test_phase_landmarks():
    assert phase_block(1) == "red_concrete"
    assert phase_block(1j) == "lime_concrete"
    assert phase_block(-1) == "light_blue_concrete"
    assert phase_block(-1j) == "magenta_concrete"


def test_opposite_phases_are_far_apart_on_the_wheel():
    for k in range(12):
        a = complex(math.cos(k * math.pi / 6), math.sin(k * math.pi / 6))
        assert (phase_slot(-a) - phase_slot(a)) % 12 == 6


def test_phase_is_relative_to_a_reference():
    assert phase_block(1j, reference=1j) == "red_concrete"
    assert reference_amplitude([0j, 0j, -0.5j, 0.5]) == -0.5j
    assert reference_amplitude([0j, 0j]) == 1 + 0j


# ---- heights -------------------------------------------------------------------------

def test_bar_height_rules():
    assert bar_height(1.0, 10) == 10
    assert bar_height(0.5, 10) == 5
    assert bar_height(0.0, 10) == 0
    assert bar_height(0.004, 10) == 0      # too small to see
    assert bar_height(0.01, 10) == 1       # tiny but visible: at least one block
    assert bar_height(1.0000001, 10) == 10  # never taller than the wall


# ---- drawing -------------------------------------------------------------------------

def test_bell_state_shows_two_bars_of_height_five():
    fb = FakeBridge()
    state = QuantumCircuit(2).h(0).cnot(0, 1).run()
    BarRenderer(fb, CFG).draw_state(state)
    assert len(bar_blocks(fb, 0, 2)) == 5 and len(bar_blocks(fb, 3, 2)) == 5
    assert bar_blocks(fb, 1, 2) == [] and bar_blocks(fb, 2, 2) == []
    assert set(bar_blocks(fb, 0, 2)) == {"red_concrete"}


def test_minus_sign_shows_as_a_different_colour():
    fb = FakeBridge()
    state = QuantumCircuit(1).x(0).h(0).run()  # (|0> - |1>)/sqrt2
    BarRenderer(fb, CFG).draw_state(state)
    assert bar_blocks(fb, 0, 1)[0] == "red_concrete"
    assert bar_blocks(fb, 1, 1)[0] == "light_blue_concrete"


def test_global_phase_does_not_change_colours():
    fb = FakeBridge()
    state = QuantumCircuit(1).y(0).run()  # i|1>: pure global phase on a basis state
    BarRenderer(fb, CFG).draw_state(state)
    assert set(bar_blocks(fb, 1, 1)) == {"red_concrete"}


def test_certain_state_fills_the_wall():
    fb = FakeBridge()
    BarRenderer(fb, CFG).draw_state(QuantumState(2))
    assert len(bar_blocks(fb, 0, 2)) == CFG.bar_height


def test_redrawing_the_same_state_writes_nothing():
    fb = FakeBridge()
    r = BarRenderer(fb, CFG)
    state = QuantumCircuit(3).h(0).h(1).h(2).run()
    r.draw_state(state)
    sets, fills = fb.set_calls, fb.fill_calls
    r.draw_state(state)
    assert (fb.set_calls, fb.fill_calls) == (sets, fills)


def test_only_changed_bars_are_touched_and_each_costs_at_most_two_fills():
    fb = FakeBridge()
    r = BarRenderer(fb, CFG)
    r.draw_state(QuantumCircuit(2).h(0).run())            # |00>, |01>
    fills = fb.fill_calls
    r.draw_state(QuantumCircuit(2).h(0).h(1).run())       # four equal bars
    assert fb.fill_calls - fills <= 2 * 2                  # two bars changed
    assert len(bar_blocks(fb, 2, 2)) == len(bar_blocks(fb, 3, 2)) == 3


def test_bars_shrink_and_vanish():
    fb = FakeBridge()
    r = BarRenderer(fb, CFG)
    r.draw_state(QuantumState(1))                          # |0> full height
    r.draw_state(QuantumCircuit(1).h(0).run())             # 5 and 5
    assert len(bar_blocks(fb, 0, 1)) == 5
    r.draw_state(QuantumCircuit(1).x(0).run())             # |1>
    assert bar_blocks(fb, 0, 1) == [] and len(bar_blocks(fb, 1, 1)) == CFG.bar_height


def test_changing_qubit_count_clears_old_bars():
    fb = FakeBridge()
    r = BarRenderer(fb, CFG)
    r.draw_state(QuantumCircuit(3).h(0).h(1).h(2).run())
    r.draw_state(QuantumState(1))
    assert bar_blocks(fb, 4, 3) == [] and bar_blocks(fb, 7, 3) == []
    assert len(bar_blocks(fb, 0, 1)) == CFG.bar_height


def test_five_qubit_state_fits_with_tight_spacing():
    fb = FakeBridge()
    BarRenderer(fb, CFG).draw_state(QuantumState(5))
    assert CFG.bar_spacing(5) == 1 and CFG.bar_spacing(4) == 2
    assert len(bar_blocks(fb, 0, 5)) == CFG.bar_height


def test_too_many_qubits_for_the_display():
    r = BarRenderer(FakeBridge(), WorkbenchConfig(max_qubits=2))
    with pytest.raises(ValueError):
        r.draw_state(QuantumState(3))


def test_readout_shows_the_bitstring_under_each_bar():
    fb = FakeBridge()
    BarRenderer(fb, CFG).draw_state(QuantumState(3))
    ground = Y0 - 1
    for i in range(8):
        for q in range(3):
            want = "white_concrete" if (i >> q) & 1 else "black_concrete"
            assert fb.blocks[(CFG.bar_x(i, 3), ground, CFG.bar_z + 1 + q)] == want


# ---- lamps ---------------------------------------------------------------------------

def test_lamps_on_off_and_cleared():
    fb = FakeBridge()
    r = BarRenderer(fb, CFG)
    lamp = lambda q: fb.blocks.get((CFG.lamp_x(q), Y0 - 1, CFG.lamp_z))
    r.draw_measurement({0: 1, 1: 0}, 2)
    assert lamp(0) == "glowstone" and lamp(1) == "gray_concrete"
    r.draw_measurement({0: 0}, 2)
    assert lamp(0) == "gray_concrete" and lamp(1) is None
    r.draw_measurement(None, 2)
    assert lamp(0) is None


def test_lamp_redraw_is_free():
    fb = FakeBridge()
    r = BarRenderer(fb, CFG)
    r.draw_measurement({0: 1}, 1)
    calls = fb.set_calls
    r.draw_measurement({0: 1}, 1)
    assert fb.set_calls == calls
