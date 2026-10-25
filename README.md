# aniQ-QSim

[![CI](https://github.com/fezinaniq/aniQ-QSim/actions/workflows/ci.yml/badge.svg)](https://github.com/fezinaniq/aniQ-QSim/actions/workflows/ci.yml)

A quantum circuit simulator written from scratch in pure Python, with **no dependencies**
(no NumPy, Qiskit, Cirq or PennyLane). Run circuits from the **command line**, from **text
files**, or as a **Python library**. An optional **Minecraft frontend** lets you build and
watch circuits inside the game.

It is built for learning: the code is small and readable, so you can see exactly how state
vectors, gates, entanglement and measurement work.

![CLI demo](docs/demo-cli.gif)

## Install

```bash
git clone https://github.com/fezinaniq/aniQ-QSim.git
cd aniQ-QSim
pip install -e .
```

Requires Python 3.11 or newer. Add `".[dev]"` instead of `.` if you want to run the tests.

## Quick start

```bash
qengine demo bell --seed 1
```

```
Circuit: 2 qubits, 2 gates
q0: ─[H]───●────
           │
q1: ───────⊕────

Final state: (|00⟩ + |11⟩)/√2
|00⟩  amp          +0.7071  P  0.500  ███████████████
|11⟩  amp          +0.7071  P  0.500  ███████████████

Sampling 1000 shots, seed 1:
|00⟩     473   47.3%  ███████████████████████████
|11⟩     527   52.7%  ██████████████████████████████
```

More commands:

```bash
qengine list                                  # list the built-in demos
qengine demo ghz -n 5                         # 5-qubit GHZ state
qengine run "h 0; cnot 0 1" --shots 2000      # run a circuit written inline
qengine run --file examples/bell.qc           # run a circuit from a file
python examples/grover_2q.py                  # Grover's search on 2 qubits
```

Built-in demos: `bell`, `ghz`, `swap`, `uniform`. Add `--ascii` if your terminal garbles the
box-drawing characters, and `--shots 0` to skip sampling and print exact probabilities.

## Circuit file format

One instruction per line, or several separated by `;`. A `#` starts a comment.

```
# Bell state
h 0
cnot 0 1      # control first, then target
swap 0 2
```

Gates: `h x y z s t cnot swap` (`cx` is an alias for `cnot`). The number of qubits is
inferred from the highest index you use, or set it with `-n`.

## Use it as a library

```python
from qengine import QuantumCircuit

qc = QuantumCircuit(2).h(0).cnot(0, 1)
print(qc.run())                 # (|00⟩ + |11⟩)/√2
print(qc.sample(1000, seed=1))  # {'00': 473, '11': 527}
```

## Minecraft frontend (optional)

The `mc/` package shows the same engine inside Minecraft. You place blocks on a workbench
to build a circuit, flip a lever, and probability bars rise on a display wall. The engine
never imports any Minecraft code, so everything above works without it.

```bash
python -m mc demo        # try the whole pipeline with no Minecraft needed
python -m mc selftest    # check a real server connection
```

Server setup (Paper plus the RaspberryJuice plugin) is in
[`docs/PHASE2_SETUP.md`](docs/PHASE2_SETUP.md). To use the RCON features (floating labels,
particles), set your server's password first:

```bash
export MC_RCON_PASSWORD="your-password"        # PowerShell: $env:MC_RCON_PASSWORD = "..."
```

Uses [RaspberryJuice](https://github.com/zhuowei/RaspberryJuice) on the server side.
Not affiliated with Mojang or Microsoft.

## How it compares with Qiskit

aniQ-QSim is a small learning tool, not a replacement for a full framework.

|  | aniQ-QSim | Qiskit |
|---|---|---|
| Dependencies | none | many |
| Code you can read in an afternoon | yes | no |
| Gates | H X Y Z S T CNOT SWAP | large library, custom gates |
| Noise models, real hardware | no | yes |
| Optimizers, algorithms library | no | yes |

It simulates ideal state vectors only. A 16-qubit circuit runs in a fraction of a second
and an 18-qubit one in about a second, but time and memory double with every extra qubit.

## Conventions

- **Little-endian qubit order:** qubit 0 is the least significant bit. Index 5 = `0b101` =
  `|q2 q1 q0⟩` = `|101⟩`.
- Two ways to apply gates, tested to agree: `run("reference")` builds full 2^N x 2^N
  operators with Kronecker products, and `run("fast")` updates amplitude pairs in place,
  O(2^N) per gate.
- Numeric tolerance for checks: `1e-9`.

## Project layout

```
qengine/     the simulator (standalone, no Minecraft imports)
  gates.py     gate matrices          circuit.py   QuantumCircuit
  state.py     QuantumState           measure.py   probabilities, collapse, sampling
  fastpath.py  in-place gates         parser.py    text <-> circuit
  operators.py full-size operators    draw.py      ASCII diagrams and histograms
  cli.py       the qengine command
mc/          Minecraft frontend (talks to the world only through WorldBridge)
tests/       pytest suite (run with: pytest)
examples/    bell, ghz, grover_2q and step-by-step demos
docs/        setup guide and design notes
```

## Roadmap

Step-through animation, a Bloch sphere view, and prebuilt algorithm worlds in Minecraft.

## License

MIT. See [LICENSE](LICENSE).
