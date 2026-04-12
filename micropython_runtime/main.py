import sys
import os

_f = globals().get("__file__") or (sys.argv[0] if sys.argv else "")
_here = _f.rsplit("/", 1)[0] if "/" in _f else os.getcwd()
sys.path.insert(0, _here + "/mosbius")
from driver import MOSbiusV2Driver

# User-editable settings.
PIN_EN = 18
PIN_CLK = 17
PIN_DATA = 16
T_CLK_HALF_CYCLE_US = 10
CONFIG_FILE = "config.json"


def main():
    if sys.implementation.name == "micropython":
        from machine import Pin

        pin_en = Pin(PIN_EN, Pin.OUT)
        pin_clk = Pin(PIN_CLK, Pin.OUT)
        pin_data = Pin(PIN_DATA, Pin.OUT)
    else:
        pin_en = pin_clk = pin_data = None

    config_path = CONFIG_FILE if CONFIG_FILE.startswith("/") else _here + "/" + CONFIG_FILE
    pin_map_path = _here + "/mosbius/pin_name_to_sw_matrix_pin_number.json"

    driver = MOSbiusV2Driver(
        pin_en=pin_en,
        pin_clk=pin_clk,
        pin_data=pin_data,
        t_clk_half_cycle_us=T_CLK_HALF_CYCLE_US,
        config_file=config_path,
        pin_map_path=pin_map_path,
    )
    print("Using config: {}".format(driver.config_path))
    driver.program_from_config()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
