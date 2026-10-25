# Phase 2: Minecraft setup and first run

The engine (`qengine/`) never touches Minecraft. Everything in `mc/` goes through one
interface, `WorldBridge`, so all of it is tested offline with an in-memory world
(`FakeBridge`) and with fake servers that speak the real wire protocols over TCP.
**The one thing the test suite cannot prove is how your real server behaves.**
`python -m mc selftest` is the check for that. Run it first, and fix whatever it flags.

## 1. Server

1. **Paper (Java Edition).** Use a Paper build the plugin below supports, and the Java version
   that Paper build needs. The RaspberryJuice fork's README says it runs on Paper 26.2 / Java 25
   and down through Paper 1.21 (Java 21). Check its releases page before you pick, and pin the
   exact versions in this README once you have a working pair.
2. **Plugin: the maintained fork** `sakebomb/RaspberryJuice` (2.x). Do *not* use the 2017
   CurseForge build (1.11): it only supports Minecraft 1.12. Put the jar in `plugins/` and start
   the server once so it writes `plugins/RaspberryJuice/config.yml`.
3. **Edit `plugins/RaspberryJuice/config.yml`:**
   - `location: ABSOLUTE`. **Important.** The default is `RELATIVE` (coordinates relative to the
     world spawn). RCON and vanilla commands use absolute coordinates, so with `RELATIVE` the
     socket and RCON would disagree about where blocks are. `selftest` checks this.
   - `hostname: localhost`, `port: 4711` (the defaults). If you set an `auth-token`, pass
     `--token` (or the `MC_TOKEN` environment variable).
4. **Edit `server.properties`:** `enable-rcon=true`, `rcon.port=25575`, `rcon.password=<something>`,
   `gamemode=creative`, `difficulty=peaceful`, `spawn-monsters=false`, and a flat world
   (`level-type=minecraft\:flat`, or `flat` on older versions). RCON is optional but recommended
   (reliable lever reading, and commands for particles later).
5. Restart, join the server, stand somewhere flat.

## 2. First run

```bash
python -m mc selftest --rcon-password YOUR_PASSWORD     # all PASS? continue
python -m mc build --at-player --qubits 2 --rcon-password YOUR_PASSWORD
python -m mc place --text "h 0; cnot 0 1" --rcon-password YOUR_PASSWORD
python -m mc watch --rcon-password YOUR_PASSWORD        # now flip the lever in the game
```

(`export MC_RCON_PASSWORD=...` once, and you can drop the flag.) The workbench position is
remembered in `mc_origin.json`, so only the first command needs `--at-player`.

No Minecraft handy? `python -m mc demo` runs the whole pipeline on an in-memory world and prints
the workbench and the bars as text.

Other commands: `labels` (redraw the floating labels for whatever is on the board), `clean` (remove all floating labels near the workbench, including old untagged ones), `hello` (place a block and greet in chat), `compile` (print the circuit your blocks
describe), `run` (one run without the lever), `watch --hits` (also trigger by right-clicking the
lever with a sword).

## 3. Building circuits by hand

Time runs along **x** (step 0 on the left), qubits along **z** (row 0 = q0), all on one layer.
A wire is a light blue stained glass block (lit from below); replace a wire block with a gate block to place the gate.

| Block | Meaning |
|---|---|
| Light blue stained glass | wire (identity). Air also counts as identity. (Boards built with the old diamond-block wire must be rebuilt: `python -m mc build`) |
| Gold block | H |
| Iron block | X |
| Red sandstone | Y |
| Emerald block | Z |
| Lapis block | S |
| Purpur block | T |
| Redstone block + coal block, same column | CNOT (redstone = control, coal = target) |
| Two quartz blocks, same column | SWAP |
| Observer | measure this qubit (ends its wire; read out at the end of the run) |
| Lever | RUN |

Mistakes (unknown block, control without target, gap in the qubit rows, a gate after a
measurement, ...) are reported in chat and in the terminal, all at once, and nothing is drawn.

## 4. What you see

Beyond the +z edge of the workbench: one bar per basis state, height = probability, colour = phase
(a minus sign turns a bar light blue; phases are relative to the first nonzero amplitude, so global
phase never shows). Under each bar a white/black grid spells its bitstring, qubit 0 nearest the bar.
A row of lamps shows one collapsed measurement outcome for qubits with an observer block
(glowstone = 1, grey = 0).

### Labels and effects

With RCON connected, every gate block gets a small floating label (`H`, `X`, `CTRL`, `NOT`, `SWAP`, `M`, ...),
each qubit row is named `q0`, `q1`, ..., the lever is tagged `RUN`, and every visible bar gets a
`|01> 50%` label. Each run also sparkles above the bars (more particles = higher probability) and plays a chime.
Without RCON all of this is skipped and the blocks still work.

Labels are tagged entities (`qmc_board`, `qmc_gate`, `qmc_bar`). Redrawing kills the old ones first, so they
never pile up. If you have stacked holograms from an older version, run `python -m mc clean` once.
If labels show raw `{...}` text, your Minecraft is 1.21.5 or newer: set `MC_TEXT_FORMAT=snbt`.
`selftest` reports whether labels spawn (`[PASS]` / `[WARN]`; a warning never fails the selftest).

## 5. Where this differs from the original plan, and why

- **Palette.** The socket only understands legacy numeric block ids, so copper, amethyst and
  netherite are replaced by legacy blocks (red sandstone for Y, purpur for T, coal for the CNOT
  target, quartz for SWAP). Every palette block also needs its own id, because reading returns ids
  only. Change the palette in `mc/config.py`; the constructor validates it.
- **No `mcpi` dependency.** `mc/socket_bridge.py` and `mc/rcon.py` are small socket clients written
  from scratch, so the project still has zero dependencies. They sit behind `WorldBridge`, so a
  different backend can be swapped in without touching the compiler or renderer.
- **Layer.** The circuit layer sits one block above the ground (rows without a wire are just
  air), instead of replacing the floor.
- **Measurement.** The engine has no mid-circuit measurement, so an observer block ends a wire and
  the readout happens at the end of the run.
- **Lamps.** Glowstone vs grey concrete rather than redstone lamps (a lit lamp with no power turns
  itself off).

## 6. If something fails

| Symptom | Likely cause |
|---|---|
| `cannot reach the RaspberryJuice socket` | server off, wrong port, plugin not loaded, firewall |
| `RCON does not see the block the socket placed` | `location: RELATIVE` in the plugin config |
| `RCON login rejected` | `--rcon-password` differs from `rcon.password` |
| `lever read/write` fails with RCON but passes without | RCON reply text differs on your version; use `--lever-mode socket` and tell me what `selftest` printed |
| `region read order` fails | the plugin returns `getBlocks` differently than assumed; send me the output |
| `unknown block 'unknown:NN'` while compiling | a block with no mapping in `mc/blocks.py` is on the layer |
| `unknown block 'diamond_block'` while compiling | old board: the wire is now light blue stained glass; rebuild with `python -m mc build` |
| labels missing or showing `{...}` | no RCON, or Minecraft 1.21.5+: see "Labels and effects" |
| duplicate floating labels | left over from an older version: `python -m mc clean` |
