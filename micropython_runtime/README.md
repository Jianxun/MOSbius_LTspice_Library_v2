# MOSbius V2 MicroPython Runtime

## Setup

Copy the entire contents of `micropython_runtime/` to the root of the Pico filesystem:

```
main.py
mosbius/
config.json          ← or your own config file(s)
```

## User Configuration

Edit `main.py` to match your hardware wiring and select a config file:

| Constant | Description |
|---|---|
| `PIN_EN` | GPIO pin number for enable |
| `PIN_CLK` | GPIO pin number for clock |
| `PIN_DATA` | GPIO pin number for data |
| `T_CLK_HALF_CYCLE_US` | Clock half-cycle period in microseconds |
| `CONFIG_FILE` | Config file to load (see below) |

## Using Multiple Configs

You can upload multiple config files to the Pico and switch between them by changing `CONFIG_FILE` in `main.py`:

```python
CONFIG_FILE = "pll_config.json"      # or "lna_config.json", "configs/lab1.json", etc.
```

Config files are generated from LTspice netlists using `netlist_to_config.py` on the host.

## Run Flow

When `main.py` runs:

1. Loads `CONFIG_FILE`
2. Validates config
3. Builds 2008-bit bitstream
4. Programs MOSbius by shifting out the bitstream

On desktop Python, steps 1–3 run normally but GPIO programming is skipped.
