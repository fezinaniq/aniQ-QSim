"""M7 tests: layout (circuit -> blocks), compiler (blocks -> circuit), workbench."""

import random

import pytest

from mc.bridge import FakeBridge
from mc.compiler import CompileError, compile_grid, compile_world, read_grid
from mc.config import DEFAULT_PALETTE, WorkbenchConfig
from mc.layout import circuit_to_grid, schedule
from mc.style import FRAME, POST
from mc.workbench import build_workbench, place_circuit
from qengine import QuantumCircuit, parse_circuit

P = DEFAULT_PALETTE
W = P.block("wire")
G = {t: P.block(t) for t in P.tokens}


def states_equal(a, b, tol=1e-9):
    return all(abs(x - y) < tol for x, y in zip(a.amps, b.amps, strict=True))


# ---- compiler: happy paths -----------------------------------------------------------

def test_bell_from_blocks():
    grid = [[G["h"], W], [G["control"], G["target"]]]
    compiled = compile_grid(grid)
    assert compiled.circuit.instructions == [("h", (0,), ()), ("cnot", (0, 1), ())]
    assert compiled.circuit.n_qubits == 2
    assert compiled.circuit.run().probabilities() == pytest.approx([0.5, 0, 0, 0.5])


def test_control_below_target_and_far_apart():
    grid = [[G["target"], W, G["control"]]]
    qc = compile_grid(grid).circuit
    assert qc.instructions == [("cnot", (2, 0), ())]


def test_swap_pair_and_air_is_identity():
    grid = [[G["swap"], "air", G["swap"]], [W, W, G["x"]]]
    qc = compile_grid(grid).circuit
    assert qc.instructions == [("swap", (0, 2), ()), ("x", (2,), ())]


def test_qubit_count_from_highest_used_row():
    grid = [[W, W, "air", "air", "air"]]
    assert compile_grid(grid).circuit.n_qubits == 2


def test_every_single_qubit_gate_maps():
    for token in ("h", "x", "y", "z", "s", "t"):
        qc = compile_grid([[G[token]]]).circuit
        assert qc.instructions == [(token, (0,), ())]


def test_one_cnot_and_a_gate_in_the_same_column():
    grid = [[G["control"], G["h"], G["target"]]]
    names = [i.name for i in compile_grid(grid).circuit.instructions]
    assert sorted(names) == ["cnot", "h"]


def test_measurement_recorded_and_wire_continues_to_end():
    grid = [[G["h"], W], [G["measure"], G["measure"]]]
    compiled = compile_grid(grid)
    assert compiled.measured == (0, 1)
    assert [i.name for i in compiled.circuit.instructions] == ["h"]


# ---- compiler: validation ------------------------------------------------------------

def msgs(grid):
    with pytest.raises(CompileError) as exc:
        compile_grid(grid)
    return [str(d) for d in exc.value.diagnostics]


def test_empty_workbench():
    assert "empty" in msgs([["air", "air"], ["air", "air"]])[0]
    assert "empty" in msgs([])[0]


def test_unknown_block_reports_position():
    out = msgs([[W, W], [W, "stone"]])
    assert out == ["step 1, qubit 1: unknown block 'stone'"]


def test_unknown_id_block():
    assert "unknown:77" in msgs([["unknown:77"]])[0]


def test_control_without_target_and_vice_versa():
    assert "no target" in msgs([[G["control"], W]])[0]
    assert "no control" in msgs([[W, G["target"]]])[0]


def test_two_controls_rejected():
    out = msgs([[G["control"], G["control"], G["target"]]])
    assert any("more than one CNOT control" in m for m in out)


def test_two_targets_rejected():
    out = msgs([[G["control"], G["target"], G["target"]]])
    assert any("more than one CNOT target" in m for m in out)


def test_swap_needs_exactly_two():
    assert "found 1" in msgs([[G["swap"], W]])[0]
    assert "found 3" in msgs([[G["swap"], G["swap"], G["swap"]]])[0]


def test_row_gap_is_an_error():
    out = msgs([[W, "air", W]])
    assert out == ["qubit 1: this row has no wire, but a higher qubit row is in use"]


def test_gate_after_measurement():
    out = msgs([[G["measure"]], [G["h"]]])
    assert "after the measurement at step 0" in out[0]


def test_double_measurement():
    assert "second measurement" in msgs([[G["measure"]], [G["measure"]]])[0]


def test_all_errors_reported_at_once():
    out = msgs([[G["control"], "stone"], [G["swap"], W]])
    assert len(out) >= 3


# ---- layout --------------------------------------------------------------------------

def test_schedule_packs_columns_like_the_drawing():
    qc = QuantumCircuit(3).h(0).h(2).cnot(0, 1).h(2)
    cols = schedule(qc)
    assert [[i.name for i in c] for c in cols] == [["h", "h"], ["cnot", "h"]]


def test_two_cnots_never_share_a_column():
    qc = QuantumCircuit(4).cnot(0, 1).cnot(2, 3)
    assert len(schedule(qc)) == 2


def test_two_swaps_never_share_a_column():
    qc = QuantumCircuit(4).swap(0, 1).swap(2, 3)
    assert len(schedule(qc)) == 2


def test_circuit_to_grid_bell():
    grid = circuit_to_grid(parse_circuit("h 0; cnot 0 1"))
    assert grid == [[G["h"], W], [G["control"], G["target"]]]


def test_measure_goes_after_last_gate():
    grid = circuit_to_grid(parse_circuit("h 0; cnot 0 1"), measure=[0, 1])
    assert grid[2] == [G["measure"], G["measure"]]
    assert compile_grid(grid).measured == (0, 1)


def test_measure_out_of_range():
    with pytest.raises(ValueError):
        circuit_to_grid(parse_circuit("h 0"), measure=[3])


def test_round_trip_random_circuits_preserve_the_state():
    rng = random.Random(7)
    singles = ["h", "x", "y", "z", "s", "t"]
    for _ in range(60):
        n = rng.randint(1, 5)
        qc = QuantumCircuit(n)
        for _ in range(rng.randint(1, 14)):
            if n > 1 and rng.random() < 0.4:
                a, b = rng.sample(range(n), 2)
                qc.add(rng.choice(["cnot", "swap"]), a, b)
            else:
                qc.add(rng.choice(singles), rng.randrange(n))
        back = compile_grid(circuit_to_grid(qc)).circuit
        assert back.n_qubits == n  # untouched trailing qubits keep their wire rows
        assert states_equal(qc.run(), back.run())


# ---- workbench + world ---------------------------------------------------------------

CFG = WorkbenchConfig(origin=(10, 64, 10))


def test_build_workbench_lays_wires_frame_and_lever():
    fb = FakeBridge()
    build_workbench(fb, CFG, qubits=3)
    for step in range(CFG.max_steps):
        for q in range(3):
            assert fb.blocks[CFG.cell(step, q)] == W
        for q in range(3, CFG.max_qubits):
            assert CFG.cell(step, q) not in fb.blocks
    assert fb.blocks[CFG.lever_pos] == "lever" and not fb.lever_powered(CFG.lever_pos)
    assert fb.blocks[(9, 64, 9)] == POST  # frame corner post, outside the scanned grid
    assert fb.blocks[(9, 65, 9)] == POST  # posts are two high
    assert fb.blocks[(10, 64, 9)] == FRAME  # frame edge


def test_build_workbench_is_idempotent_and_resets():
    fb = FakeBridge()
    build_workbench(fb, CFG, qubits=2)
    fb.set_block(CFG.cell(4, 1), "gold_block")
    build_workbench(fb, CFG, qubits=2)
    assert fb.blocks[CFG.cell(4, 1)] == W


def test_bare_workbench_compiles_to_empty_circuit():
    fb = FakeBridge()
    build_workbench(fb, CFG, qubits=2)
    compiled = compile_world(fb, CFG)
    assert len(compiled.circuit) == 0 and compiled.circuit.n_qubits == 2


def test_place_then_compile_matches():
    fb = FakeBridge()
    qc = parse_circuit("h 0; cnot 0 1; cnot 1 2; x 2; swap 0 2")
    cols = place_circuit(fb, CFG, qc)
    assert cols >= 3
    back = compile_world(fb, CFG).circuit
    assert states_equal(qc.run(), back.run())


def test_place_clears_a_previous_circuit():
    fb = FakeBridge()
    place_circuit(fb, CFG, parse_circuit("h 0; h 1; h 2; h 0; h 1"))
    place_circuit(fb, CFG, parse_circuit("x 0"))
    back = compile_world(fb, CFG).circuit
    assert [i.name for i in back.instructions] == ["x"] and back.n_qubits == 1


def test_place_rejects_oversized_circuits():
    fb = FakeBridge()
    with pytest.raises(ValueError, match="qubits"):
        place_circuit(fb, CFG, QuantumCircuit(6))
    long = QuantumCircuit(1)
    for _ in range(13):
        long.h(0)
    with pytest.raises(ValueError, match="columns"):
        place_circuit(fb, CFG, long)


def test_reading_the_grid_is_one_region_call():
    fb = FakeBridge()
    build_workbench(fb, CFG, qubits=2)
    before = fb.get_calls
    grid = read_grid(fb, CFG)
    assert fb.get_calls - before == 1
    assert len(grid) == CFG.max_steps and len(grid[0]) == CFG.max_qubits


def test_placed_circuit_with_measurement_end_to_end():
    fb = FakeBridge()
    place_circuit(fb, CFG, parse_circuit("h 0; cnot 0 1"), measure=[0, 1])
    compiled = compile_world(fb, CFG)
    assert compiled.measured == (0, 1)
