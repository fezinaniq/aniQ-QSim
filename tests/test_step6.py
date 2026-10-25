"""M6 tests: block table, FakeBridge, socket bridge and RCON over real TCP."""

import pytest

from mc.blocks import LEGACY, glyph, legacy, name_from_id
from mc.bridge import BridgeError, FakeBridge, ascii_safe
from mc.config import DEFAULT_PALETTE, Palette, WorkbenchConfig
from mc.rcon import RconClient
from mc.socket_bridge import SocketBridge
from tests.fakeservers import FakeJuiceServer, FakeRconServer


@pytest.fixture
def juice():
    server = FakeJuiceServer()
    yield server
    server.close()


@pytest.fixture
def bridge(juice):
    b = SocketBridge("127.0.0.1", juice.port)
    yield b
    b.close()


# ---- blocks / palette ----------------------------------------------------------------

def test_every_palette_block_has_a_material_and_reads_back_by_name():
    for token, block in DEFAULT_PALETTE.tokens.items():
        bid, _ = legacy(block)
        assert name_from_id(bid) == block, token


def test_palette_rejects_duplicates_and_concrete():
    tokens = dict(DEFAULT_PALETTE.tokens)
    tokens["h"] = tokens["x"]
    with pytest.raises(ValueError, match="different"):
        Palette(tokens)
    tokens = dict(DEFAULT_PALETTE.tokens)
    tokens["h"] = "white_concrete"
    with pytest.raises(ValueError, match="cannot be used"):
        Palette(tokens)


def test_unknown_names_and_ids():
    assert name_from_id(9999) == "unknown:9999"
    with pytest.raises(KeyError, match="no material mapping"):
        legacy("copper_block")


def test_concrete_colors_are_distinct_materials():
    mats = {LEGACY[n][0] for n in LEGACY if n.endswith("_concrete")}
    datas = {LEGACY[n][1] for n in LEGACY if n.endswith("_concrete")}
    assert len(mats) == 16 and datas == {0}


def test_glyphs_are_single_characters():
    assert all(len(glyph(n)) == 1 for n in LEGACY)


def test_ascii_safe():
    assert ascii_safe("(|00\u27e9, \u221a2)\nnext") == "[|00>; sqrt2] next"


# ---- config geometry -----------------------------------------------------------------

def test_cell_and_corners():
    cfg = WorkbenchConfig(origin=(10, 64, 20), max_steps=12, max_qubits=5)
    assert cfg.cell(3, 2) == (13, 64, 22)
    assert cfg.grid_min == (10, 64, 20) and cfg.grid_max == (21, 64, 24)
    assert cfg.lever_pos[0] < cfg.origin[0]


def test_config_validation():
    with pytest.raises(ValueError):
        WorkbenchConfig(max_qubits=6)


# ---- FakeBridge ----------------------------------------------------------------------

def test_fake_bridge_blocks_and_region():
    fb = FakeBridge()
    fb.set_block((1, 2, 3), "gold_block")
    fb.fill((0, 0, 0), (1, 0, 0), "iron_block")
    assert fb.get_block((1, 2, 3)) == "gold_block"
    region = fb.get_region((0, 0, 0), (2, 0, 0))
    assert region == {(0, 0, 0): "iron_block", (1, 0, 0): "iron_block", (2, 0, 0): "air"}
    fb.set_block((1, 2, 3), "air")
    assert fb.get_block((1, 2, 3)) == "air"


def test_fake_bridge_lever():
    fb = FakeBridge()
    pos = (0, 0, 0)
    assert not fb.lever_powered(pos)
    fb.set_lever(pos, False)
    fb.flip_lever(pos)
    assert fb.lever_powered(pos)
    fb.set_lever(pos, False)
    assert not fb.lever_powered(pos)


# ---- SocketBridge over TCP -----------------------------------------------------------

def test_set_get_roundtrip(bridge, juice):
    bridge.set_block((1, 64, 2), "gold_block")
    assert bridge.get_block((1, 64, 2)) == "gold_block"
    assert juice.blocks[(1, 64, 2)] == ("GOLD_BLOCK", 0)
    assert bridge.get_block((9, 9, 9)) == "air"


def test_concrete_goes_out_as_its_own_material(bridge, juice):
    bridge.set_block((0, 0, 0), "red_concrete")
    bridge.get_block((0, 0, 0))  # sync: the setter has no reply
    assert juice.blocks[(0, 0, 0)] == ("RED_CONCRETE", 0)


def test_fill_is_one_command(bridge, juice):
    before = len(juice.received)
    bridge.fill((0, 0, 0), (4, 0, 2), "diamond_block")
    bridge.get_block((0, 0, 0))  # forces the server to have processed the fill
    assert len(juice.received) - before == 2
    assert juice.blocks[(4, 0, 2)] == ("DIAMOND_BLOCK", 0)


def test_get_region_returns_every_block_keyed_by_position(bridge):
    bridge.set_block((0, 5, 0), "gold_block")
    bridge.set_block((2, 5, 1), "iron_block")
    region = bridge.get_region((0, 5, 0), (2, 5, 1))
    assert len(region) == 6
    assert region[(0, 5, 0)] == "gold_block" and region[(2, 5, 1)] == "iron_block"
    assert region[(1, 5, 0)] == "air"


def test_get_region_tolerates_trailing_comma(bridge, juice):
    juice.trailing_comma = True
    bridge.set_block((1, 0, 0), "lapis_block")
    assert bridge.get_region((0, 0, 0), (2, 0, 0))[(1, 0, 0)] == "lapis_block"


def test_get_region_with_swapped_corners(bridge):
    bridge.set_block((0, 0, 0), "gold_block")
    assert bridge.get_region((2, 0, 1), (0, 0, 0))[(0, 0, 0)] == "gold_block"


def test_unknown_block_is_reported_by_id(bridge, juice):
    juice.blocks[(0, 0, 0)] = ("STONE", 0)
    juice.blocks[(1, 0, 0)] = (777, 0)
    region = bridge.get_region((0, 0, 0), (1, 0, 0))
    assert region[(0, 0, 0)] == "stone" and region[(1, 0, 0)] == "unknown:777"


def test_player_tile_and_chat(bridge, juice):
    assert bridge.get_player_tile() == (5, 70, 5)
    bridge.say("Ran 2 gates: (|00\u27e9 + |11\u27e9)/\u221a2")
    bridge.get_block((0, 0, 0))  # sync
    assert juice.chat == ["Ran 2 gates: [|00> + |11>]/sqrt2"]


def test_poll_hits(bridge, juice):
    assert bridge.poll_hits() == []
    juice.hits = [(1, 2, 3), (4, 5, 6)]
    assert bridge.poll_hits() == [(1, 2, 3), (4, 5, 6)]
    assert bridge.poll_hits() == []


def test_lever_via_socket_data_bit(bridge, juice):
    pos = (3, 64, 3)
    bridge.set_lever(pos, False)
    bridge.get_block(pos)
    assert juice.blocks[pos] == ("LEVER", 5)
    assert not bridge.lever_powered(pos)
    juice.blocks[pos] = ("LEVER", 13)  # a player flipped it: powered bit (8) set
    assert bridge.lever_powered(pos)
    bridge.set_lever(pos, False)
    assert not bridge.lever_powered(pos)


def test_stale_reply_lines_do_not_desync_reads(bridge, juice):
    bridge._send("bogus.command()")  # server answers "Fail", nobody reads it
    juice.blocks[(0, 0, 0)] = ("GOLD_BLOCK", 0)
    import time
    time.sleep(0.05)
    assert bridge.get_block((0, 0, 0)) == "gold_block"


def test_server_fail_raises(bridge):
    with pytest.raises(BridgeError, match="refused"):
        bridge._ask("bogus.command()")


def test_unreachable_server():
    with pytest.raises(BridgeError, match="cannot reach"):
        SocketBridge("127.0.0.1", 1, timeout=0.3)


def test_positions_must_be_int_triples(bridge):
    with pytest.raises(ValueError):
        bridge.get_block((1.5, 0, 0))


def test_auth_token_sent_first(juice):
    b = SocketBridge("127.0.0.1", juice.port, token="abc")
    b.get_block((0, 0, 0))
    assert juice.received[0] == "auth(abc)"
    b.close()


def test_placing_blocks_never_sends_commands(juice):
    """Regression: set_block used to summon a hologram over RCON for every gate placed."""
    srv = FakeRconServer()
    b = SocketBridge("127.0.0.1", juice.port, rcon=RconClient("127.0.0.1", srv.port, "secret"))
    for name in ("gold_block", "iron_block", "redstone_block", "coal_block", "emerald_block"):
        b.set_block((0, 0, 0), name)
    b.get_block((0, 0, 0))  # sync
    assert srv.commands == []
    b.close()
    srv.close()


def test_no_rcon_means_no_commands(bridge):
    assert not bridge.has_commands
    with pytest.raises(BridgeError, match="RCON"):
        bridge.run_command("say hi")


# ---- RCON ----------------------------------------------------------------------------

def test_rcon_login_and_command():
    srv = FakeRconServer(responder=lambda c: f"ran: {c}")
    client = RconClient("127.0.0.1", srv.port, "secret")
    assert client.command("list") == "ran: list"
    assert srv.commands == ["list"]
    client.close()
    srv.close()


def test_rcon_wrong_password():
    srv = FakeRconServer()
    with pytest.raises(BridgeError, match="rejected"):
        RconClient("127.0.0.1", srv.port, "nope")
    srv.close()


def test_rcon_unreachable():
    with pytest.raises(BridgeError, match="cannot reach"):
        RconClient("127.0.0.1", 1, "x", timeout=0.3)


def test_lever_via_rcon_uses_modern_state(juice):
    srv = FakeRconServer(
        responder=lambda c: "Test passed" if "powered=true" in c else "Test failed"
    )
    rcon = RconClient("127.0.0.1", srv.port, "secret")
    b = SocketBridge("127.0.0.1", juice.port, rcon=rcon)
    assert b.has_commands
    assert b.lever_powered((1, 2, 3))
    b.set_lever((1, 2, 3), False)
    assert srv.commands[0] == "execute if block 1 2 3 minecraft:lever[powered=true]"
    assert srv.commands[1] == "setblock 1 2 3 minecraft:lever[face=floor,facing=north,powered=false]"
    b.close()
    srv.close()


def test_lever_rcon_failed_test(juice):
    srv = FakeRconServer(responder=lambda c: "Test failed")
    b = SocketBridge("127.0.0.1", juice.port, rcon=RconClient("127.0.0.1", srv.port, "secret"))
    assert not b.lever_powered((0, 0, 0))
    b.close()
    srv.close()


def test_lever_mode_rcon_without_rcon(juice):
    b = SocketBridge("127.0.0.1", juice.port, lever_mode="rcon")
    with pytest.raises(BridgeError):
        b.lever_powered((0, 0, 0))
    b.close()
