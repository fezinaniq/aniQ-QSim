# Quantum Minecraft

A quantum computer simulator written from scratch in pure Python (no Qiskit, Cirq or
PennyLane), driven and visualized live inside Minecraft.

> **Status:** engine (M0-M5) and Minecraft frontend (M6-M9: bridge, workbench compiler,
> lever controller, probability bars with phase colours) are written and tested offline.
> Floating labels, a lit glass board, bar labels and particle effects are in (needs RCON).
> Still to do: step-through animation, Bloch sphere (M10), prebuilt algorithm worlds
> (M11), polish (M12). Roadmap: `docs/QUANTUM_MINECRAFT_PLAN.md`. Minecraft setup:
> `docs/PHASE2_SETUP.md`.

## Quick start

```bash
python -m qengine demo bell                  # built-in Bell state demo
python -m qengine run "h 0; cnot 0 1" --seed 1
python -m qengine run --file examples/bell.qc --shots 2000
python -m qengine demo ghz -n 5
python -m qengine list                       # all demos
python examples/grover_2q.py                 # Grover's search on 2 qubits
pytest                                       # run the test suite
python -m mc demo                            # Minecraft pipeline on an in-memory world
python -m mc selftest                        # check a real server (see docs/PHASE2_SETUP.md)
python -m mc clean                           # remove stacked floating labels from older versions
```

Use `--ascii` if your terminal garbles the box-drawing characters.

## Circuit text format

One instruction per line or separated by `;`. `#` starts a comment.

```
h 0
cnot 0 1     # control first, then target
swap 0 2
```

Gates: `h x y z s t cnot swap` (`cx` is an alias for `cnot`).

## Use it as a library

```python
from qengine import QuantumCircuit

qc = QuantumCircuit(2).h(0).cnot(0, 1)
print(qc.run())                 # (|00> + |11>)/sqrt(2)
print(qc.sample(1000, seed=1))  # {'00': 473, '11': 527}
```

## Conventions

- **Little-endian qubit order:** qubit 0 is the least significant bit. Index 5 = `0b101` =
  `|q2 q1 q0>` = `|101>`.
- Numeric tolerance for checks: `1e-9`.
- Two ways to apply gates, tested to agree: `run("reference")` builds full 2^N x 2^N operators
  with Kronecker products; `run("fast")` updates amplitude pairs in place, O(2^N) per gate.

## Layout

```
qengine/     standalone engine, zero Minecraft imports
  linalg.py    matvec, matmul, kron, dagger, is_unitary
  gates.py     H X Y Z S T CNOT SWAP matrices
  state.py     QuantumState
  operators.py full-size operators (reference path)
  fastpath.py  in-place gate application
  circuit.py   QuantumCircuit
  measure.py   probabilities, measurement, collapse, sampling
  parser.py    text <-> circuit
  draw.py      ASCII diagrams, state tables, histograms
  cli.py       python -m qengine
mc/          Minecraft frontend (talks to the world only through WorldBridge)
  blocks.py    block names <-> legacy ids
  config.py    palette, workbench geometry
  bridge.py    WorldBridge interface + in-memory FakeBridge
  socket_bridge.py  RaspberryJuice socket client (from scratch)
  rcon.py      RCON client (from scratch)
  layout.py    circuit -> block grid
  compiler.py  block grid -> circuit, with validation
  workbench.py build the board, place circuits as blocks
  colors.py    phase -> block colour
  style.py     floating labels (tagged, never stacked), board dressing, particles
  renderer.py  state -> probability bars, read-out, lamps
  controller.py lever polling and the run loop
  __main__.py  python -m mc ...
tests/       pytest suite
examples/    bell, ghz, grover_2q
docs/        plan and write-ups
```
