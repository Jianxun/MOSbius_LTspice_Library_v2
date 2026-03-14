import json
import os
import re
import sys


EXPECTED_RBUS = 8
EXPECTED_SBUS = 6
HARDWIRED_PORTS = {"BIASN", "BIASP"}


def _warn(message):
    print("Warning: {}".format(message))


def _usage():
    script = os.path.basename(sys.argv[0])
    return (
        "Usage: {} <netlist.net> [output.json] [--pin-number-to-name path] [--pin-name-to-number path] [--size-map path]\n".format(script)
        + "Default output: <netlist_name>_connnections.json (same folder as netlist)\n"
        + "If mapping paths are omitted, script tries local defaults relative to itself.\n"
    )


def _load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def _read_text_auto(path):
    with open(path, "rb") as f:
        data = f.read()

    tried = []
    for encoding in ("utf-8", "utf-16le", "utf-16", "utf-16be"):
        try:
            text = data.decode(encoding)
            if "\x00" in text:
                tried.append("{}(nul-bytes)".format(encoding))
                continue
            return text, encoding
        except UnicodeDecodeError:
            tried.append(encoding)

    raise UnicodeDecodeError(
        "auto",
        b"",
        0,
        1,
        "Unable to decode {} as text (tried {})".format(path, ", ".join(tried)),
    )


def _parse_int_token(token):
    token = token.strip()
    if token.startswith("{") and token.endswith("}"):
        token = token[1:-1].strip()
    if re.fullmatch(r"[+-]?\d+", token):
        return int(token)
    return None


def _parse_param_ints(lines):
    params = {}
    for line in lines:
        s = line.strip()
        if not s.lower().startswith(".param"):
            continue
        body = s[6:].strip()
        for token in body.split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            parsed = _parse_int_token(value)
            if parsed is not None:
                params[key.strip().upper()] = parsed
    return params


def _resolve_m_value(token, params):
    if token is None:
        return None
    parsed = _parse_int_token(token)
    if parsed is not None:
        return parsed

    token = token.strip()
    if token.startswith("{") and token.endswith("}"):
        token = token[1:-1].strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
        return params.get(token.upper())
    return None


def _parse_bus_map(lines):
    out = {}
    pattern = re.compile(r"^\*\s*@((?:R|S)BUS\d+)\s*:\s*(\S+)", re.IGNORECASE)
    for line in lines:
        m = pattern.match(line.strip())
        if not m:
            continue
        out[m.group(1).upper()] = m.group(2)
    return out


def _parse_subckts(lines):
    out = {}
    first_subckt = None
    for idx, line in enumerate(lines, start=1):
        s = line.strip()
        if not s:
            continue
        if s.lower().startswith(".subckt "):
            if first_subckt is None:
                first_subckt = idx
            parts = s.split()
            out[parts[1].lower()] = [p.upper() for p in parts[2:]]
    if first_subckt is None:
        first_subckt = len(lines) + 1
    return out, first_subckt


def _parse_top_instances(lines, stop_line):
    out = []
    m_pattern = re.compile(r"\bm\s*=\s*([^\s]+)", re.IGNORECASE)
    for idx in range(1, stop_line):
        s = lines[idx - 1].strip()
        if not s or not s.startswith("X"):
            continue

        parts = s.split()
        if len(parts) < 3:
            _warn("line {}: malformed instance line '{}'".format(idx, s))
            continue

        instance_name = parts[0][1:]
        tokens = []
        for token in parts[1:]:
            if token.lower() == "params:":
                break
            tokens.append(token)

        if len(tokens) < 2:
            _warn("line {}: not enough tokens in instance '{}'".format(idx, instance_name))
            continue

        m_match = m_pattern.search(s)
        out.append(
            {
                "line": idx,
                "instance": instance_name,
                "subckt": tokens[-1].lower(),
                "nodes": tokens[:-1],
                "m_token": m_match.group(1) if m_match else None,
            }
        )
    return out


def _canonical_device_name(instance_name):
    if instance_name in ("CC1_N",):
        return "CC_N"
    if instance_name in ("CC1_P",):
        return "CC_P"
    if instance_name in ("OTA_NMOS",):
        return "OTA_N"
    if instance_name in ("OTA_PMOS",):
        return "OTA_P"
    return instance_name


def _is_mosbius_device(device_name):
    if re.fullmatch(r"DCC\d+_[NP]_[LR]", device_name):
        return True
    if re.fullmatch(r"DINV\d+_[LR]", device_name):
        return True
    return device_name in ("CC_N", "CC_P", "OTA_N", "OTA_P")


def _ordered_buses():
    buses = []
    for i in range(1, EXPECTED_RBUS + 1):
        buses.append("RBUS{}".format(i))
    for i in range(1, EXPECTED_SBUS + 1):
        buses.append("SBUS{}".format(i))
    return buses


def _derive_output_path(netlist_path):
    folder = os.path.dirname(os.path.abspath(netlist_path))
    stem = os.path.splitext(os.path.basename(netlist_path))[0]
    return os.path.join(folder, "{}_connnections.json".format(stem))


def _first_existing(paths):
    for path in paths:
        if os.path.exists(path):
            return path
    return paths[0] if paths else None


def _parse_args(argv):
    if len(argv) < 2:
        raise ValueError("missing netlist path")

    size_map_path = None
    pin_number_to_name_path = None
    pin_name_to_number_path = None
    positionals = []

    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in ("-h", "--help"):
            print(_usage())
            raise SystemExit(0)

        if arg.startswith("--size-map="):
            size_map_path = arg.split("=", 1)[1].strip()
        elif arg == "--size-map":
            if i + 1 >= len(argv):
                raise ValueError("Missing value for --size-map")
            size_map_path = argv[i + 1].strip()
            i += 1
        elif arg.startswith("--pin-number-to-name="):
            pin_number_to_name_path = arg.split("=", 1)[1].strip()
        elif arg == "--pin-number-to-name":
            if i + 1 >= len(argv):
                raise ValueError("Missing value for --pin-number-to-name")
            pin_number_to_name_path = argv[i + 1].strip()
            i += 1
        elif arg.startswith("--pin-name-to-number="):
            pin_name_to_number_path = arg.split("=", 1)[1].strip()
        elif arg == "--pin-name-to-number":
            if i + 1 >= len(argv):
                raise ValueError("Missing value for --pin-name-to-number")
            pin_name_to_number_path = argv[i + 1].strip()
            i += 1
        else:
            positionals.append(arg)
        i += 1

    if len(positionals) < 1:
        raise ValueError("missing netlist path")
    if len(positionals) > 2:
        raise ValueError("Too many positional arguments")

    netlist_path = positionals[0]
    output_path = positionals[1] if len(positionals) == 2 else _derive_output_path(netlist_path)
    return netlist_path, output_path, size_map_path, pin_number_to_name_path, pin_name_to_number_path


def main():
    try:
        netlist_path, output_path, size_map_arg, pin_number_to_name_arg, pin_name_to_number_arg = _parse_args(sys.argv)
    except ValueError as e:
        print("Error: {}".format(e))
        print(_usage())
        raise SystemExit(1)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(base_dir)

    default_size_map_path = _first_existing(
        [
            os.path.join(base_dir, "V2", "tools", "chip_config_data", "device_name_to_sizing_registers.json"),
            os.path.join(base_dir, "tools", "chip_config_data", "device_name_to_sizing_registers.json"),
            os.path.join(base_dir, "chip_config_data", "device_name_to_sizing_registers.json"),
            os.path.join(parent_dir, "V2", "tools", "chip_config_data", "device_name_to_sizing_registers.json"),
        ]
    )
    default_pin_number_to_name_path = _first_existing(
        [
            os.path.join(base_dir, "pin_number_to_name.json"),
            os.path.join(base_dir, "V2", "tools", "chip_config_data", "pin_number_to_name.json"),
            os.path.join(base_dir, "tools", "chip_config_data", "pin_number_to_name.json"),
            os.path.join(base_dir, "chip_config_data", "pin_number_to_name.json"),
            os.path.join(parent_dir, "pin_number_to_name.json"),
            os.path.join(parent_dir, "V2", "tools", "chip_config_data", "pin_number_to_name.json"),
        ]
    )

    size_map_path = size_map_arg or default_size_map_path
    pin_number_to_name_path = pin_number_to_name_arg or default_pin_number_to_name_path
    pin_name_to_number_path = pin_name_to_number_arg

    expected_devices = None
    size_map_used = None
    if size_map_path and os.path.exists(size_map_path):
        expected_devices = set(_load_json(size_map_path).keys())
        size_map_used = size_map_path
    elif size_map_arg:
        raise ValueError("size map path not found: '{}'".format(size_map_arg))
    else:
        _warn("size map not found; device completeness checks disabled")

    name_to_number = None
    terminal_map_used = None
    if pin_name_to_number_path and os.path.exists(pin_name_to_number_path):
        name_to_number = _load_json(pin_name_to_number_path)
        terminal_map_used = pin_name_to_number_path
    elif pin_name_to_number_arg:
        raise ValueError("pin-name-to-number map path not found: '{}'".format(pin_name_to_number_arg))
    elif pin_number_to_name_path and os.path.exists(pin_number_to_name_path):
        number_to_name = _load_json(pin_number_to_name_path)
        name_to_number = {str(name): int(number) for number, name in number_to_name.items()}
        terminal_map_used = pin_number_to_name_path
    elif pin_number_to_name_arg:
        raise ValueError("pin-number-to-name map path not found: '{}'".format(pin_number_to_name_arg))
    else:
        _warn("pin terminal map not found; output terminals will not be annotated with '#<pin>'")

    valid_terminals = set(name_to_number.keys()) if name_to_number is not None else None

    text, encoding = _read_text_auto(netlist_path)
    lines = text.splitlines()
    params = _parse_param_ints(lines)
    bus_map = _parse_bus_map(lines)
    subckts, first_subckt = _parse_subckts(lines)
    instances = _parse_top_instances(lines, first_subckt)

    net_to_terminals = {}
    for inst in instances:
        line = inst["line"]
        instance_name = inst["instance"]
        device_name = _canonical_device_name(instance_name)
        if not _is_mosbius_device(device_name):
            continue
        subckt = inst["subckt"]
        nodes = inst["nodes"]
        ports = subckts.get(subckt)

        if ports is None:
            _warn("line {}: subckt '{}' for instance '{}' not found".format(line, subckt, instance_name))
            continue
        if len(ports) != len(nodes):
            _warn(
                "line {}: instance '{}' has {} nodes but subckt '{}' defines {} ports".format(
                    line, instance_name, len(nodes), subckt, len(ports)
                )
            )
            continue

        for port, net in zip(ports, nodes):
            if port in HARDWIRED_PORTS:
                continue
            terminal = "{}_{}".format(device_name, port)
            if valid_terminals is not None and terminal not in valid_terminals:
                continue
            if name_to_number is not None and terminal in name_to_number:
                annotated = "{}#{}".format(terminal, name_to_number[terminal])
            else:
                annotated = terminal
            net_to_terminals.setdefault(net, set()).add(annotated)

    connections = {}
    for bus in _ordered_buses():
        mapped_net = bus_map.get(bus)
        if mapped_net is None:
            _warn("bus '{}' missing in comment map; defaulting to nc".format(bus))
            connections[bus] = []
            continue
        if mapped_net.lower() == "nc":
            connections[bus] = []
            continue
        terminals = sorted(net_to_terminals.get(mapped_net, set()))
        if not terminals:
            _warn("bus '{}' maps to net '{}' but resolves to no terminals".format(bus, mapped_net))
        connections[bus] = terminals

    sizes = {}
    seen_devices = set()
    for inst in instances:
        device_name = _canonical_device_name(inst["instance"])
        if expected_devices is not None:
            if device_name not in expected_devices:
                continue
        elif not _is_mosbius_device(device_name):
            continue
        seen_devices.add(device_name)

        value = _resolve_m_value(inst["m_token"], params)
        if value is None:
            if inst["m_token"] is None:
                _warn("line {}: device '{}' has no m= value; size defaults to 0 downstream".format(inst["line"], device_name))
            else:
                _warn(
                    "line {}: unable to resolve m='{}' for device '{}'; size defaults to 0 downstream".format(
                        inst["line"], inst["m_token"], device_name
                    )
                )
            continue
        sizes[device_name] = value

    if expected_devices is not None:
        for missing in sorted(expected_devices - seen_devices):
            _warn("expected device '{}' not found in top-level netlist".format(missing))

    output = {
        "connections": connections,
        "sizes": {k: sizes[k] for k in sorted(sizes.keys())},
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")

    print(
        "Wrote {} from {} (encoding={}, instances={}, nonempty_buses={}, sizes={})".format(
            output_path,
            netlist_path,
            encoding,
            len(instances),
            sum(1 for v in connections.values() if v),
            len(sizes),
        )
    )
    if size_map_used:
        print("Size map: {}".format(size_map_used))
    if terminal_map_used:
        print("Terminal map: {}".format(terminal_map_used))


if __name__ == "__main__":
    main()
