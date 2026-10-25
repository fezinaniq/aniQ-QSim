"""CLI tests: `python -m mc` commands against the fake RaspberryJuice/RCON servers."""

import time

import pytest

from mc.__main__ import main
from tests.fakeservers import FakeJuiceServer, FakeRconServer


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # mc_origin.json lands in the temp dir
    srv = FakeJuiceServer(player=(100, 70, 100))
    yield srv
    srv.close()


def settle(server, quiet=0.1):
    """Wait until the server has stopped receiving (setters have no reply to wait for)."""
    last = -1
    while last != len(server.received):
        last = len(server.received)
        time.sleep(quiet)


def lever_rcon():
    """A fake RCON that remembers the lever state like a real server would."""
    state = {"on": False}

    def respond(cmd):
        if cmd.startswith("setblock") and "lever" in cmd:
            state["on"] = "powered=true" in cmd
            return "Changed the block"
        if "lever[powered=true]" in cmd:
            return "Test passed" if state["on"] else "Test failed"
        return "Test passed"

    return FakeRconServer(responder=respond)


def conn(server):
    return ["--port", str(server.port), "--host", "127.0.0.1"]


def test_selftest_passes_against_a_well_behaved_server(server, capsys):
    assert main(["selftest", *conn(server)]) == 0
    out = capsys.readouterr().out
    assert "All checks passed" in out and "FAIL" not in out


def test_selftest_with_rcon_checks_coordinates(server, capsys):
    rcon = lever_rcon()
    code = main(["selftest", *conn(server), "--rcon-port", str(rcon.port),
                 "--rcon-password", "secret"])
    out = capsys.readouterr().out
    rcon.close()
    assert code == 0 and "socket and RCON agree" in out


def test_selftest_explains_relative_coordinate_mismatch(server, capsys):
    rcon = FakeRconServer(responder=lambda c: "Test failed")
    code = main(["selftest", *conn(server), "--rcon-port", str(rcon.port),
                 "--rcon-password", "secret"])
    out = capsys.readouterr().out
    rcon.close()
    assert code == 1 and "location: ABSOLUTE" in out


def test_selftest_without_a_server(capsys):
    assert main(["selftest", "--port", "1", "--host", "127.0.0.1"]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_hello_places_block_next_to_player(server, capsys):
    assert main(["hello", *conn(server)]) == 0
    assert any("gold" in s or s.startswith("world.setBlock(102,70,100,GOLD_BLOCK") for s in server.received)
    assert server.blocks[(102, 70, 100)] == ("GOLD_BLOCK", 0)


def test_build_at_player_then_place_compile_run(server, capsys):
    assert main(["build", *conn(server), "--at-player", "--qubits", "2"]) == 0
    assert main(["place", *conn(server), "--text", "h 0; cnot 0 1"]) == 0  # origin remembered
    settle(server)
    capsys.readouterr()
    assert main(["compile", *conn(server)]) == 0
    assert "\u2295" in capsys.readouterr().out
    assert main(["run", *conn(server)]) == 0
    settle(server)
    assert any("Ran 2 gates" in c for c in server.chat)
    # bars were drawn (a concrete block somewhere in the world)
    assert any(str(v[0]).endswith("_CONCRETE") for v in server.blocks.values())


def test_compile_reports_errors_and_exits_1(server, capsys):
    main(["build", *conn(server), "--origin", "0", "64", "0", "--qubits", "1"])
    settle(server)
    server.blocks[(3, 64, 0)] = ("STONE", 0)  # stone on the wire
    capsys.readouterr()
    assert main(["compile", *conn(server)]) == 1
    assert "unknown block 'stone'" in capsys.readouterr().out


def test_commands_need_a_position(server, tmp_path):
    with pytest.raises(SystemExit, match="--at-player"):
        main(["compile", *conn(server)])


def test_bad_circuit_text_is_a_clean_error(server, capsys):
    assert main(["place", *conn(server), "--origin", "0", "64", "0", "--text", "bogus 0"]) == 2
    assert "unknown gate" in capsys.readouterr().err


def test_offline_demo_prints_everything(capsys):
    assert main(["demo", "--text", "h 0; cnot 0 1", "--measure", "0,1"]) == 0
    out = capsys.readouterr().out
    assert "Workbench from above" in out and "Display wall" in out and "Ran 2 gates" in out
