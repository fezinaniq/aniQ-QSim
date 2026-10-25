"""Command line for the Minecraft frontend:  python -m mc <command>

    selftest   check the connection, block I/O, coordinates and lever (run this first)
    hello      place a gold block next to you and say hi in chat
    build      build the workbench (add --at-player to put it in front of you)
    place      lay a circuit onto the workbench as blocks
    compile    read the blocks and print the circuit they describe
    run        compile + simulate + draw once
    labels     redraw the floating labels for whatever is on the board
    clean      remove all floating labels near the workbench (also old stacked ones)
    watch      run whenever the lever is flipped
    demo       the whole pipeline on an in-memory world (no Minecraft needed)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from qengine import QuantumCircuit, draw_circuit, parse_circuit
from qengine.parser import CircuitParseError

from .bridge import BridgeError, FakeBridge, WorldBridge
from .compiler import CompileError, compile_world, read_grid
from .config import Pos, WorkbenchConfig
from .controller import Controller
from .rcon import RconClient
from .socket_bridge import SocketBridge
from .style import ALL_TAGS, Stylist, kill_tag, summon_label, where
from .workbench import build_workbench, place_circuit

ORIGIN_FILE = Path("mc_origin.json")


# ---- connection and origin ---------------------------------------------------------


def add_connection_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=4711, help="RaspberryJuice port")
    p.add_argument("--token", default=None, help="RaspberryJuice auth-token, if you set one")
    p.add_argument("--rcon-port", type=int, default=25575)
    p.add_argument("--rcon-password", default=None, help="or set MC_RCON_PASSWORD")
    p.add_argument("--no-rcon", action="store_true")
    p.add_argument("--lever-mode", choices=("auto", "rcon", "socket"), default="auto")
    p.add_argument("--origin", type=int, nargs=3, metavar=("X", "Y", "Z"),
                   help="block of step 0 / qubit 0 on the circuit layer")
    p.add_argument("--at-player", action="store_true",
                   help="put the workbench just in front of the player (saved for later commands)")





def connect(args: argparse.Namespace) -> SocketBridge:
    """Connect to the socket, and to RCON when possible. Always says what it ended up with,
    because labels, particles and sounds silently depend on RCON."""
    rcon = None
    if not args.no_rcon:
        given = args.rcon_password or os.environ.get("MC_RCON_PASSWORD")
        password = given 
        if password:
            try:
                rcon = RconClient(args.host, args.rcon_port, password)
            except BridgeError as exc:
             print(f"warning: RCON unavailable: {exc}")
        else:
            print("warning: no RCON password given")
    bridge = SocketBridge(
        args.host, args.port, token=args.token or os.environ.get("MC_TOKEN"),
        rcon=rcon, lever_mode=args.lever_mode,
    )
    if rcon is None and not args.no_rcon:
        print("  -> floating labels, particles and sounds are OFF. Set the same value as "
              "rcon.password in server.properties:\n"
              "     PowerShell:  $env:MC_RCON_PASSWORD = \"yourpassword\"\n"
              "     or add:      --rcon-password yourpassword")
    return bridge


def resolve_origin(args: argparse.Namespace, bridge: WorldBridge) -> Pos:
    """--origin wins; else --at-player (and remember it); else the remembered origin."""
    if args.origin:
        origin = tuple(args.origin)
    elif args.at_player:
        px, py, pz = bridge.get_player_tile()
        origin = (px + 3, py, pz)  # on the layer just above the floor, a few blocks ahead
    elif ORIGIN_FILE.exists():
        origin = tuple(json.loads(ORIGIN_FILE.read_text())["origin"])
    else:
        raise SystemExit("No workbench position yet: add --at-player (or --origin X Y Z).")
    ORIGIN_FILE.write_text(json.dumps({"origin": list(origin)}))
    return origin  # type: ignore[return-value]


def make_cfg(args: argparse.Namespace, bridge: WorldBridge) -> WorkbenchConfig:
    return WorkbenchConfig(origin=resolve_origin(args, bridge))


def read_circuit(args: argparse.Namespace) -> QuantumCircuit:
    if args.file:
        text = Path(args.file).read_text()
    elif args.text:
        text = args.text
    else:
        raise SystemExit("give a circuit with --text \"h 0; cnot 0 1\" or --file path.qc")
    return parse_circuit(text)


# ---- commands ----------------------------------------------------------------------


def cmd_hello(args: argparse.Namespace) -> int:
    with connect(args) as bridge:
        x, y, z = bridge.get_player_tile()
        bridge.set_block((x + 2, y, z), "gold_block")
        bridge.say("Hello from Python! The quantum engine is connected.")
        print(f"placed a gold block at {(x + 2, y, z)} and said hello in chat")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    with connect(args) as bridge:
        cfg = make_cfg(args, bridge)
        build_workbench(bridge, cfg, qubits=args.qubits)
        print(f"workbench built at {cfg.origin} with {args.qubits} qubit wire(s); "
              f"lever at {cfg.lever_pos}")
    return 0


def cmd_place(args: argparse.Namespace) -> int:
    circuit = read_circuit(args)
    measure = [int(q) for q in args.measure.split(",")] if args.measure else []
    with connect(args) as bridge:
        cfg = make_cfg(args, bridge)
        cols = place_circuit(bridge, cfg, circuit, measure)
        print(draw_circuit(circuit))
        print(f"placed {len(circuit)} gates in {cols} columns at {cfg.origin}")
    return 0


def cmd_compile(args: argparse.Namespace) -> int:
    with connect(args) as bridge:
        cfg = make_cfg(args, bridge)
        try:
            compiled = compile_world(bridge, cfg)
        except CompileError as err:
            print("Compile error:")
            for d in err.diagnostics:
                print(f"  {d}")
            return 1
        print(draw_circuit(compiled.circuit))
        if compiled.measured:
            print("measured qubits:", ", ".join(f"q{q}" for q in compiled.measured))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    with connect(args) as bridge:
        cfg = make_cfg(args, bridge)
        return 0 if Controller(bridge, cfg).run_once().ok else 1


def cmd_labels(args: argparse.Namespace) -> int:
    with connect(args) as bridge:
        if not bridge.has_commands:
            print("labels need RCON: pass --rcon-password (or set MC_RCON_PASSWORD)")
            return 1
        cfg = make_cfg(args, bridge)
        grid = read_grid(bridge, cfg)
        rows = max((q + 1 for col in grid for q, b in enumerate(col) if b != "air"), default=0)
        stylist = Stylist(bridge, cfg)
        stylist.clear()
        x, y, z = cfg.origin
        probe = bridge.run_command(summon_label((x + 0.5, y + 3, z + 0.5), "TEST", "aqua", "qmc_board"))
        print(f"server reply to a test label: {probe!r}")
        if "summoned" not in probe.lower():
            print("The server rejected the label command. Send me that reply; on Minecraft 1.21.5+ "
                  "try:  $env:MC_TEXT_FORMAT = \"snbt\"")
            return 1
        stylist.clear()
        stylist.board(max(rows, 1))
        stylist.gates(grid)
        print(f"labels redrawn for {rows} qubit row(s)")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """Kill our tagged labels, plus any untagged text displays within `--radius` of the board
    (the stacked holograms an earlier version left behind)."""
    with connect(args) as bridge:
        if not bridge.has_commands:
            print("clean needs RCON: pass --rcon-password (or set MC_RCON_PASSWORD)")
            return 1
        cfg = make_cfg(args, bridge)
        for tag in ALL_TAGS:
            bridge.run_command(kill_tag(tag))
        x, y, z = where(cfg)
        reply = bridge.run_command(
            f"kill @e[type=text_display,x={x},y={y},z={z},distance=..{args.radius}]"
        )
        print(f"cleaned: {reply or 'done'}")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    with connect(args) as bridge:
        cfg = make_cfg(args, bridge)
        ctrl = Controller(bridge, cfg, use_hits=args.hits)
        print(f"watching the lever at {cfg.lever_pos}; Ctrl+C to stop")
        ctrl.watch()
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Everything except Minecraft: build, place, flip the lever, run, show the world as text."""
    circuit = parse_circuit(args.text)
    measure = [int(q) for q in args.measure.split(",")] if args.measure else []
    bridge = FakeBridge()
    cfg = WorkbenchConfig(origin=(10, 0, 10))
    place_circuit(bridge, cfg, circuit, measure)
    print("Workbench from above (= wire, letters are gates, L = lever):\n")
    ox, oy, oz = cfg.origin
    print(bridge.top_view(ox - 3, ox + cfg.max_steps + 1, oz - 1, oz + cfg.max_qubits, oy))
    print("\nFlipping the lever...\n")
    bridge.flip_lever(cfg.lever_pos)
    ctrl = Controller(bridge, cfg, log=print)
    ctrl.poll()
    n = circuit.n_qubits
    width = 2**n * cfg.bar_spacing(n)
    print("\nDisplay wall, seen from the front (bar height = probability):\n")
    print(bridge.front_view(ox, ox + width - 1, oy, oy + cfg.bar_height - 1, cfg.bar_z))
    print("\nChat messages:")
    for line in bridge.chat:
        print(" ", line)
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:  # type: ignore[no-untyped-def]
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 - report every failure, don't stop at the first
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        results.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))

    try:
        bridge = connect(args)
    except BridgeError as exc:
        print(f"[FAIL] connect - {exc}")
        print("Is the server running with the RaspberryJuice plugin (default port 4711)?")
        return 1
    with bridge:
        px, py, pz = bridge.get_player_tile()
        base = (px, py + 3, pz + 3)  # a scratch spot in the air near the player
        bx, by, bz = base
        line = [(bx + i, by, bz) for i in range(3)]
        names = ["gold_block", "iron_block", "emerald_block"]

        def block_roundtrip():  # type: ignore[no-untyped-def]
            bridge.set_block(base, "gold_block")
            got = bridge.get_block(base)
            return got == "gold_block", f"placed gold_block, read back '{got}'"

        def region_order():  # type: ignore[no-untyped-def]
            for p, n in zip(line, names, strict=True):
                bridge.set_block(p, n)
            region = bridge.get_region(line[0], line[-1])
            got = [region[p] for p in line]
            return got == names, f"expected {names}, got {got}"

        def clear_works():  # type: ignore[no-untyped-def]
            bridge.fill(line[0], line[-1], "air")
            got = bridge.get_region(line[0], line[-1])
            return all(v == "air" for v in got.values()), "fill with air"

        def rcon_coords():  # type: ignore[no-untyped-def]
            if not bridge.has_commands:
                return True, "skipped (no RCON password given)"
            bridge.set_block(base, "gold_block")
            reply = bridge.run_command(
                f"execute if block {bx} {by} {bz} minecraft:gold_block"
            )
            bridge.set_block(base, "air")
            if "passed" in reply.lower():
                return True, "socket and RCON agree on coordinates"
            return False, ("RCON does not see the block the socket placed. Set "
                           "'location: ABSOLUTE' in plugins/RaspberryJuice/config.yml and restart. "
                           f"(RCON said: {reply!r})")

        def lever():  # type: ignore[no-untyped-def]
            lp = (bx, by + 2, bz)
            bridge.set_block((bx, by + 1, bz), "stone")
            bridge.set_lever(lp, True)
            on = bridge.lever_powered(lp)
            bridge.set_lever(lp, False)
            off = bridge.lever_powered(lp)
            bridge.fill((bx, by + 1, bz), lp, "air")
            return (on and not off), f"powered read: on={on}, off after reset={off}"

        check("player position", lambda: (True, f"player at {(px, py, pz)}"))
        check("place and read a block", block_roundtrip)
        check("region read order", region_order)
        check("clear with fill", clear_works)
        check("RCON coordinates", rcon_coords)
        check("lever read/write", lever)
        bridge.set_block(base, "air")
        if bridge.has_commands:  # decoration check: informational, never fails the selftest
            bridge.run_command(kill_tag("qmc_test"))
            reply = bridge.run_command(summon_label((bx + 0.5, by + 1, bz + 0.5), "TEST", "aqua", "qmc_test"))
            bridge.run_command(kill_tag("qmc_test"))
            if "summoned" in reply.lower():
                print("[PASS] floating labels (text_display)")
            else:
                print(f"[WARN] floating labels did not spawn (RCON said {reply!r}). The game still works; "
                      "labels may need MC_TEXT_FORMAT=snbt on Minecraft 1.21.5+.")
    failed = [r for r in results if not r[1]]
    print("\nAll checks passed." if not failed else f"\n{len(failed)} check(s) failed.")
    return 1 if failed else 0


# ---- entry point -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m mc", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, func, help_: str, connection: bool = True):  # type: ignore[no-untyped-def]
        p = sub.add_parser(name, help=help_)
        if connection:
            add_connection_args(p)
        p.set_defaults(func=func)
        return p

    add("selftest", cmd_selftest, "check connection, block I/O, coordinates, lever")
    add("hello", cmd_hello, "place a block next to you and greet in chat")
    p = add("build", cmd_build, "build the workbench")
    p.add_argument("--qubits", type=int, default=3)
    for name, func, text in (("place", cmd_place, "place a circuit as blocks"),):
        p = add(name, func, text)
        p.add_argument("--text")
        p.add_argument("--file")
        p.add_argument("--measure", help="comma list of qubits to put a measurement block on")
    add("compile", cmd_compile, "print the circuit the blocks describe")
    add("run", cmd_run, "compile, simulate and draw once")
    add("labels", cmd_labels, "redraw floating labels for the blocks on the board")
    p = add("clean", cmd_clean, "remove floating labels near the workbench")
    p.add_argument("--radius", type=int, default=80)
    p = add("watch", cmd_watch, "run whenever the lever is flipped")
    p.add_argument("--hits", action="store_true", help="also trigger on sword-hits on the lever")
    p = add("demo", cmd_demo, "offline demo on an in-memory world", connection=False)
    p.add_argument("--text", default="h 0; cnot 0 1")
    p.add_argument("--measure", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except BridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (CircuitParseError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
