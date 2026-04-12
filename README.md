# MOSbius V2 LTspice Library

LTspice symbol/subcircuit library for the MOSbius V2 chip, plus tooling to convert a schematic netlist into a chip configuration file.

## Repo contents

| Path | Description |
|---|---|
| `*.asc` / `*.asy` | LTspice subcircuit schematics and symbols |
| `transistor_models_tsmc025_public.inc` | TSMC 0.25 µm transistor models |
| `netlist_to_config.py` | Converts a `.net` netlist to a `_config.json` for the runtime |
| `micropython_runtime/` | MicroPython driver for programming the chip over a Raspberry Pi Pico |

## Workflow

### 1. Design in LTspice

Start from `template_mosbius_v2_all_devices.asc` — it has all chip devices pre-placed with `m=1` defaults and the bus comment block ready to fill in:

```
* @RBUS1: vtune
* @RBUS2: vbp
...
```

Set each bus to the net name it should connect to, or `nc` to leave it unconnected. Adjust `m=` values for sizing, then export the netlist (`.net`) from LTspice.

### 2. Generate the config

```sh
python3 netlist_to_config.py your_circuit.net
```

Outputs `your_circuit_config.json` next to the netlist. No dependencies beyond the Python standard library.

### 3. Program the chip

See [`micropython_runtime/README.md`](micropython_runtime/README.md).
