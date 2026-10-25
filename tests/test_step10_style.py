"""M10 tests: tagged labels (no stacking), board dressing, bar labels, effects."""

import pytest

from mc.bridge import FakeBridge
from mc.compiler import compile_world
from mc.config import WorkbenchConfig
from mc.controller import Controller
from mc.renderer import BarRenderer
from mc.style import (
    FLOOR,
    GLOW,
    TAG_BAR,
    TAG_BOARD,
    TAG_GATE,
    Stylist,
    ket_label,
    kill_tag,
    summon_label,
)
from mc.workbench import build_workbench, place_circuit
from qengine import QuantumCircuit, QuantumState

CFG = WorkbenchConfig(origin=(10, 64, 10))


def summons(fb, tag):
    return [c for c in fb.commands if c.startswith("summon") and f'Tags:["{tag}"]' in c]


def texts(cmds):
    return [c.split("text:'")[1].split("'")[0] for c in cmds]


# ---- label command shape ------------------------------------------------------------

def test_summon_label_is_well_formed():
    cmd = summon_label((1.5, 2.25, 3.5), "H", "gold", TAG_GATE, 1.2)
    assert cmd.startswith("summon text_display 1.50 2.25 3.50 {")
    assert cmd.count("{") == cmd.count("}") and cmd.count("[") == cmd.count("]")
    assert '"text":"H"' in cmd and 'Tags:["qmc_gate"]' in cmd and "scale:[1.20f,1.20f,1.20f]" in cmd


def test_summon_label_rejects_text_that_would_break_the_command():
    for bad in ("it's", 'a"b', "a\\b", "{x}", "\u2295"):
        with pytest.raises(ValueError):
            summon_label((0, 0, 0), bad, "white", TAG_GATE)


def test_snbt_text_format(monkeypatch):
    monkeypatch.setenv("MC_TEXT_FORMAT", "snbt")
    cmd = summon_label((0, 0, 0), "H", "gold", TAG_GATE)
    assert 'text:{text:"H",color:"gold",bold:1b}' in cmd


def test_ket_label_is_little_endian_and_padded():
    assert ket_label(1, 2) == "|01>" and ket_label(2, 3) == "|010>" and ket_label(5, 3) == "|101>"


# ---- gate labels: one per gate, never stacking -------------------------------------

def test_one_label_per_gate_and_none_for_wires_or_frame():
    fb = FakeBridge()
    place_circuit(fb, CFG, QuantumCircuit(2).h(0).cnot(0, 1), measure=[1])
    labels = texts(summons(fb, TAG_GATE))
    assert sorted(labels) == sorted(['{"text":"H","color":"gold","bold":true}',
                                     '{"text":"CTRL","color":"red","bold":true}',
                                     '{"text":"NOT","color":"gray","bold":true}',
                                     '{"text":"M","color":"white","bold":true}'])


def test_every_gate_type_gets_a_label():
    fb = FakeBridge()
    qc = QuantumCircuit(2).h(0).x(1).y(0).z(1).s(0).t(1).swap(0, 1)
    place_circuit(fb, CFG, qc)
    names = " ".join(texts(summons(fb, TAG_GATE)))
    for want in ('"H"', '"X"', '"Y"', '"Z"', '"S"', '"T"', '"SWAP"'):
        assert f'"text":{want}' in names


def test_labels_are_replaced_not_stacked():
    """The old bug: every placement summoned a fresh hologram and nothing ever removed them."""
    fb = FakeBridge()
    qc = QuantumCircuit(2).h(0).cnot(0, 1)
    for _ in range(3):
        place_circuit(fb, CFG, qc)
    # simulate the world: a kill command removes every entity with that tag
    alive: dict[str, int] = {}
    for c in fb.commands:
        if c.startswith("kill"):
            alive[c.split("tag=")[1].rstrip("]")] = 0
        elif c.startswith("summon"):
            tag = c.split('Tags:["')[1].split('"')[0]
            alive[tag] = alive.get(tag, 0) + 1
    assert alive[TAG_GATE] == 3          # H, control, target: exactly one set, not three
    assert alive[TAG_BOARD] == 1 + 2 + 1  # title + q0,q1 + RUN
    assert sum(alive.values()) == 3 + 4


def test_running_the_board_refreshes_gate_labels_from_the_real_blocks():
    fb = FakeBridge()
    place_circuit(fb, CFG, QuantumCircuit(1).h(0))
    fb.set_block(CFG.cell(1, 0), "emerald_block")  # the player adds a Z by hand
    fb.commands.clear()
    fb.flip_lever(CFG.lever_pos)
    Controller(fb, CFG, log=lambda *_: None).poll()
    assert fb.commands[0] == kill_tag(TAG_GATE)
    assert len(summons(fb, TAG_GATE)) == 2  # H and the hand-placed Z


def test_labels_on_a_failed_compile_still_match_the_board():
    fb = FakeBridge()
    build_workbench(fb, CFG, qubits=1)
    fb.set_block(CFG.cell(0, 0), "redstone_block")  # control with no target
    fb.commands.clear()
    fb.flip_lever(CFG.lever_pos)
    result = Controller(fb, CFG, log=lambda *_: None).poll()
    assert result is not None and not result.ok
    assert len(summons(fb, TAG_GATE)) == 1


def test_no_rcon_means_no_labels_and_no_errors():
    class NoCommands(FakeBridge):
        has_commands = False
    fb = NoCommands()
    place_circuit(fb, CFG, QuantumCircuit(2).h(0).cnot(0, 1))
    assert fb.commands == []
    assert compile_world(fb, CFG).circuit.n_qubits == 2


def test_a_failing_command_never_breaks_a_run():
    from mc.bridge import BridgeError

    class Flaky(FakeBridge):
        def run_command(self, cmd):
            raise BridgeError("boom")
    fb = Flaky()
    place_circuit(fb, CFG, QuantumCircuit(2).h(0).cnot(0, 1))
    fb.flip_lever(CFG.lever_pos)
    assert Controller(fb, CFG, log=lambda *_: None).poll().ok


# ---- board dressing -----------------------------------------------------------------

def test_board_is_dressed_but_compiles_the_same():
    fb = FakeBridge()
    place_circuit(fb, CFG, QuantumCircuit(2).h(0).cnot(0, 1))
    x, y, z = CFG.origin
    assert fb.blocks[(x + 3, y - 1, z)] == GLOW                 # lit bed under the used wires
    assert fb.blocks[(x + 3, y - 1, z + 3)] == FLOOR            # dark floor under unused rows
    assert fb.blocks[(x - 1, y - 1, z)] == FLOOR                # floor under the frame
    assert fb.blocks[CFG.cell(5, 0)] == CFG.palette.block("wire")
    assert compile_world(fb, CFG).circuit.instructions == QuantumCircuit(2).h(0).cnot(0, 1).instructions


def test_wire_is_glass():
    assert CFG.palette.block("wire") == "light_blue_stained_glass"


# ---- bar labels and effects ---------------------------------------------------------

def draw_bell(fb):
    r = BarRenderer(fb, CFG)
    r.draw_state(QuantumCircuit(2).h(0).cnot(0, 1).run())
    return r


def test_only_visible_bars_get_a_label_with_name_and_percent():
    fb = FakeBridge()
    draw_bell(fb)
    labels = texts(summons(fb, TAG_BAR))
    assert len(labels) == 2
    assert '"text":"|00> 50%"' in labels[0] and '"text":"|11> 50%"' in labels[1]


def test_bar_labels_are_replaced_on_every_draw():
    fb = FakeBridge()
    r = draw_bell(fb)
    r.draw_state(QuantumCircuit(2).x(0).run())
    cmds = [c for c in fb.commands if f"tag={TAG_BAR}" in c or f'Tags:["{TAG_BAR}"]' in c]
    last_kill = max(i for i, c in enumerate(cmds) if c.startswith("kill"))
    assert [c.startswith("summon") for c in cmds[last_kill + 1:]] == [True]  # one bar: |01> 100%
    assert '"text":"|01> 100%"' in cmds[-1]


def test_particles_scale_with_probability_and_sit_over_the_bars():
    fb = FakeBridge()
    r = BarRenderer(fb, CFG)
    r.draw_state(QuantumCircuit(2).h(0).run())            # 50/50 on |00> and |01>
    fb.commands.clear()
    r.draw_state(QuantumCircuit(2).h(0).run())            # same state again: effects still play
    parts = [c for c in fb.commands if c.startswith("particle")]
    assert len(parts) == 2 and all(p.endswith("force") for p in parts)
    assert any(c.startswith("playsound") for c in fb.commands)


def test_particle_count_grows_with_probability():
    fb = FakeBridge()
    st = Stylist(fb, CFG)
    skew = QuantumState(1)
    skew.amps = [0.9 ** 0.5 + 0j, 0.1 ** 0.5 + 0j]
    fb.commands.clear()
    st.effects(skew, {0: 9, 1: 1})
    counts = [int(c.split()[-2]) for c in fb.commands if c.startswith("particle")]
    assert counts[0] > counts[1]


def test_pedestals_under_every_bar_slot():
    fb = FakeBridge()
    draw_bell(fb)
    y = CFG.origin[1] - 1
    for i in range(4):
        assert fb.blocks[(CFG.bar_x(i, 2), y, CFG.bar_z)] == "sea_lantern"
