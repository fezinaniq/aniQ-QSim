"""M5 tests: text parser, ASCII drawing, CLI, examples."""

import runpy
from pathlib import Path

import pytest

from qengine import (
    CircuitParseError,
    QuantumCircuit,
    circuit_to_text,
    draw_circuit,
    format_histogram,
    format_state,
    parse_circuit,
)
from qengine.cli import DEMOS, main

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


# ---- parser ----------------------------------------------------------------------

def test_parse_bell_with_semicolons():
    qc = parse_circuit("h 0; cnot 0 1")
    assert qc.n_qubits == 2
    assert qc.instructions == [("h", (0,), ()), ("cnot", (0, 1), ())]


def test_parse_lines_comments_case_and_alias():
    qc = parse_circuit("# bell\nH 0   # superposition\n\nCX 0 1\n")
    assert qc.instructions == [("h", (0,), ()), ("cnot", (0, 1), ())]


def test_parse_infers_qubits_from_highest_index():
    assert parse_circuit("x 3").n_qubits == 4


def test_parse_explicit_qubits_can_exceed_usage():
    assert parse_circuit("x 0", n_qubits=5).n_qubits == 5


def test_parse_empty_text_gives_one_qubit_circuit():
    qc = parse_circuit("")
    assert qc.n_qubits == 1 and len(qc) == 0


@pytest.mark.parametrize(
    "text",
    ["foo 0", "h", "h 0 1", "cnot 0", "h zero", "cnot 0 0", "h -1", "h 1.5"],
)
def test_parse_errors(text):
    with pytest.raises(CircuitParseError):
        parse_circuit(text)


def test_parse_error_when_qubit_exceeds_declared_count():
    with pytest.raises(CircuitParseError):
        parse_circuit("h 3", n_qubits=2)


def test_parse_error_mentions_line_number():
    with pytest.raises(CircuitParseError, match="line 2"):
        parse_circuit("h 0\nbogus 1")


def test_text_round_trip():
    original = QuantumCircuit(3).h(0).cnot(0, 2).swap(1, 2).t(1)
    rebuilt = parse_circuit(circuit_to_text(original), 3)
    assert rebuilt.instructions == original.instructions


def test_parsed_circuit_runs_like_built_circuit():
    a = parse_circuit("h 0; cnot 0 1").run()
    b = QuantumCircuit(2).h(0).cnot(0, 1).run()
    assert a.amps == b.amps


# ---- drawing ---------------------------------------------------------------------

def test_draw_bell_ascii_exact():
    qc = QuantumCircuit(2).h(0).cnot(0, 1)
    expected = "q0: -[H]---*----\n           |\nq1: ------(+)---"
    assert draw_circuit(qc, ascii_only=True) == expected


def test_draw_bell_unicode():
    qc = QuantumCircuit(2).h(0).cnot(0, 1)
    out = draw_circuit(qc)
    assert "\u25cf" in out and "\u2295" in out and "[H]" in out


def test_draw_cnot_across_a_middle_wire_shows_crossing():
    out = draw_circuit(QuantumCircuit(3).cnot(0, 2), ascii_only=True).splitlines()
    assert "*" in out[0] and "(+)" in out[4]
    assert "|" in out[2]  # the middle wire is crossed, not used


def test_draw_packs_independent_gates_into_one_column():
    out = draw_circuit(QuantumCircuit(2).h(0).h(1), ascii_only=True).splitlines()
    assert out[0].index("[H]") == out[2].index("[H]")


def test_draw_dependent_gates_use_separate_columns():
    out = draw_circuit(QuantumCircuit(1).h(0).x(0), ascii_only=True)
    assert out.index("[H]") < out.index("[X]")


def test_draw_empty_circuit():
    assert draw_circuit(QuantumCircuit(2), ascii_only=True).startswith("q0: --")


def test_draw_swap():
    out = draw_circuit(QuantumCircuit(2).swap(0, 1), ascii_only=True)
    assert out.count("x") == 2


def test_format_state_hides_zero_rows_and_shows_probabilities():
    state = QuantumCircuit(2).h(0).cnot(0, 1).run()
    out = format_state(state, ascii_only=True)
    assert "|00>" in out and "|11>" in out
    assert "|01>" not in out and "|10>" not in out
    assert "0.500" in out


def test_format_state_show_zero():
    state = QuantumCircuit(2).h(0).cnot(0, 1).run()
    assert "|01>" in format_state(state, show_zero=True, ascii_only=True)


def test_format_state_truncates_big_states():
    qc = QuantumCircuit(5)
    for q in range(5):
        qc.h(q)
    out = format_state(qc.run(), max_rows=8, ascii_only=True)
    assert "and 24 more" in out
    assert len(out.splitlines()) == 9


def test_format_state_complex_amplitude():
    state = QuantumCircuit(1).h(0).s(0).run()
    assert "i" in format_state(state, ascii_only=True)


def test_format_histogram_percentages_and_bars():
    out = format_histogram({"00": 250, "11": 750}, width=20, ascii_only=True)
    assert "25.0%" in out and "75.0%" in out
    lines = out.splitlines()
    assert lines[1].count("#") == 20
    assert lines[0].count("#") == round(20 * 250 / 750)


# ---- CLI -------------------------------------------------------------------------

def test_cli_run_bell(capsys):
    assert main(["run", "h 0; cnot 0 1", "--seed", "1", "--ascii"]) == 0
    out = capsys.readouterr().out
    assert "Circuit: 2 qubits, 2 gates" in out
    assert "(|00" in out and "/\u221a2" in out
    assert "Sampling 1000 shots, seed 1" in out


def test_cli_run_is_reproducible(capsys):
    main(["run", "h 0; cnot 0 1", "--seed", "5"])
    first = capsys.readouterr().out
    main(["run", "h 0; cnot 0 1", "--seed", "5"])
    assert capsys.readouterr().out == first


def test_cli_no_shots(capsys):
    assert main(["run", "x 0", "-n", "2", "--shots", "0"]) == 0
    assert "Sampling" not in capsys.readouterr().out


def test_cli_reference_method_same_state(capsys):
    main(["run", "h 0; cnot 0 1", "--shots", "0", "--method", "fast"])
    fast = capsys.readouterr().out
    main(["run", "h 0; cnot 0 1", "--shots", "0", "--method", "reference"])
    assert capsys.readouterr().out == fast


def test_cli_file(capsys):
    assert main(["run", "--file", str(EXAMPLES / "bell.qc"), "--shots", "0"]) == 0
    assert "(|00" in capsys.readouterr().out


def test_cli_errors_return_code_2(capsys):
    assert main(["run", "bogus 0"]) == 2
    assert main(["run", "h 0; cnot 0 5", "-n", "2"]) == 2
    assert main(["run"]) == 2
    assert main(["run", "--file", "no_such_file.qc"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_list(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for name in DEMOS:
        assert name in out


@pytest.mark.parametrize("name", sorted(DEMOS))
def test_cli_every_demo_runs(name, capsys):
    assert main(["demo", name, "--shots", "100", "--seed", "1"]) == 0
    assert "Final state" in capsys.readouterr().out


def test_cli_ghz_demo_with_n(capsys):
    assert main(["demo", "ghz", "-n", "4", "--shots", "0"]) == 0
    out = capsys.readouterr().out
    assert "|0000" in out and "|1111" in out


# ---- examples ----------------------------------------------------------------------

@pytest.mark.parametrize("script", ["bell.py", "ghz.py", "grover_2q.py"])
def test_example_scripts_run(script, capsys):
    runpy.run_path(str(EXAMPLES / script), run_name="__main__")
    assert capsys.readouterr().out.strip()


@pytest.mark.parametrize("marked", ["00", "01", "10", "11"])
def test_grover_2q_finds_every_marked_state(marked):
    module = runpy.run_path(str(EXAMPLES / "grover_2q.py"))
    state = module["grover_2q"](marked).run()
    probs = state.probabilities()
    assert probs[int(marked, 2)] == pytest.approx(1.0)
    assert state.is_normalized()


def test_grover_rejects_bad_marked():
    module = runpy.run_path(str(EXAMPLES / "grover_2q.py"))
    with pytest.raises(ValueError):
        module["grover_2q"]("2")
