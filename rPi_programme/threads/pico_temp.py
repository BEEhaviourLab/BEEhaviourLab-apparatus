import json
import os
import statistics
import time
from datetime import datetime, time as dt_time

import serial
from serial.tools import list_ports


DEFAULT_PICO_PORT = "/dev/ttyACM0"
SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 2.0
HYSTERESIS_BAND = 0.25
LOG_INTERVAL_SECONDS = 30
SECONDS_PER_DAY = 24 * 60 * 60


def _parse_clock(value):
    """Parse HH:MM or HH:MM:SS into datetime.time."""
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value.strip(), fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid time value: {value!r}")


def _time_to_seconds(clock_time):
    return (
        clock_time.hour * 3600
        + clock_time.minute * 60
        + clock_time.second
    )


def _seconds_to_time(total_seconds):
    total_seconds = total_seconds % SECONDS_PER_DAY
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return dt_time(hours, minutes, seconds)


def _format_time(clock_time):
    return clock_time.strftime("%H:%M:%S")


def get_cycle_duration(config):
    """Nominal seconds per replicate: recording length plus inter-segment gap."""
    return int(config["Rec_time"]) + int(config["spaces"])


def get_elapsed_experiment_seconds(config, replicate):
    """
    Elapsed experiment time at the start of a replicate.

    Replicate 1 begins at experiment_start_time with zero elapsed time.
    Each prior replicate advances the clock by Rec_time + spaces.
    """
    if replicate < 1:
        raise ValueError("replicate must be >= 1")
    return (replicate - 1) * get_cycle_duration(config)


def get_virtual_experiment_clock(config, replicate):
    """
    Simulated clock time for this replicate, anchored at experiment_start_time.

    Example: experiment_start_time 12:00, Rec_time 60, spaces 840 (15 min/cycle)
      replicate 1  -> 12:00
      replicate 25 -> 18:00  (night begins)
      replicate 49 -> 00:00 next virtual day
    """
    start = _parse_clock(config["experiment_start_time"])
    elapsed = get_elapsed_experiment_seconds(config, replicate)
    virtual_seconds = _time_to_seconds(start) + elapsed
    return _seconds_to_time(virtual_seconds), elapsed


def _is_night(virtual_time, night_start, day_start):
    """Night spans from night_start until day_start (may cross midnight)."""
    if night_start < day_start:
        return night_start <= virtual_time < day_start
    return virtual_time >= night_start or virtual_time < day_start


def get_experiment_phase(config, replicate):
    """Return 'day' or 'night' for the simulated clock at this replicate."""
    virtual_time, _ = get_virtual_experiment_clock(config, replicate)
    night_start = _parse_clock(config["night_start_time"])
    day_start = _parse_clock(config["day_start_time"])
    if _is_night(virtual_time, night_start, day_start):
        return "night"
    return "day"


def get_effective_setpoint(config, replicate):
    """
    Return plate setpoint (deg C) from config and replicate number.

    Uses a virtual experiment timeline:
      experiment_start_time + (replicate - 1) * (Rec_time + spaces)

    Night periods (night_start_time -> day_start_time on that virtual clock)
    subtract day_night_temp_variation from target_temp.
    """
    base_temp = float(config["target_temp"])
    variation = float(config["day_night_temp_variation"])

    if get_experiment_phase(config, replicate) == "night":
        return base_temp - variation

    return base_temp


def find_pico_port(preferred_port=None):
    if preferred_port and os.path.exists(preferred_port):
        return preferred_port

    for port in list_ports.comports():
        desc = (port.description or "").lower()
        manufacturer = (port.manufacturer or "").lower()
        if "pico" in desc or "pico" in manufacturer or "rp2040" in desc:
            return port.device

    if os.path.exists(DEFAULT_PICO_PORT):
        return DEFAULT_PICO_PORT

    raise RuntimeError(
        "Pico serial port not found. Connect the Pico over USB and set pico_serial_port in config.json."
    )


def _open_serial(port):
    return serial.Serial(port, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)


def _read_response(ser, prefix=None, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        if line.startswith("DBG,"):
            continue
        if prefix is None or line.startswith(prefix):
            return line
    raise TimeoutError(f"No serial response received (expected prefix: {prefix})")


def ping_pico(port):
    with _open_serial(port) as ser:
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(b"PING\n")
        ser.flush()
        response = _read_response(ser, prefix="OK,PONG", timeout=3.0)
        if response != "OK,PONG":
            raise RuntimeError(f"Unexpected Pico response: {response}")
    return True


def set_pico_temperature(port, temperature):
    with _open_serial(port) as ser:
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(f"SET,{temperature:.2f}\n".encode("utf-8"))
        ser.flush()
        response = _read_response(ser, prefix="OK,SET", timeout=3.0)
        if not response.startswith("OK,SET,"):
            raise RuntimeError(f"Failed to set Pico temperature: {response}")


def start_pico_logging(port):
    with _open_serial(port) as ser:
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(b"LOG,START\n")
        ser.flush()
        response = _read_response(ser, prefix="OK,LOG,START", timeout=3.0)
        if response != "OK,LOG,START":
            raise RuntimeError(f"Failed to start Pico logging: {response}")


def stop_pico_logging_and_fetch(port, timeout=30.0):
    with _open_serial(port) as ser:
        ser.reset_input_buffer()
        ser.write(b"LOG,STOP\n")
        ser.flush()
        response = _read_response(ser, prefix="OK,LOG,DATA", timeout=timeout)
        if not response.startswith("OK,LOG,DATA,"):
            raise RuntimeError(f"Failed to fetch Pico temperature log: {response}")

        parts = response.split(",")
        if len(parts) < 4 or parts[:3] != ["OK", "LOG", "DATA"]:
            raise RuntimeError(f"Unexpected Pico log response: {response}")

        count = int(parts[3])
        readings = [float(value) for value in parts[4:4 + count]]
        if len(readings) != count:
            raise RuntimeError(
                f"Pico returned {len(readings)} readings but reported {count}"
            )
        return readings


def get_schedule_context(config, replicate, setpoint):
    virtual_time, elapsed_seconds = get_virtual_experiment_clock(config, replicate)
    return {
        "replicate": replicate,
        "cycle_duration_seconds": get_cycle_duration(config),
        "elapsed_experiment_seconds": elapsed_seconds,
        "virtual_experiment_time": _format_time(virtual_time),
        "experiment_phase": get_experiment_phase(config, replicate),
        "segment_setpoint": setpoint,
        "target_temp": config["target_temp"],
        "day_night_temp_variation": config["day_night_temp_variation"],
        "experiment_start_time": config["experiment_start_time"],
        "night_start_time": config["night_start_time"],
        "day_start_time": config["day_start_time"],
    }


def write_temp_tracking(output_path, readings, setpoint, config, replicate):
    if readings:
        avg_temp = statistics.mean(readings)
        std_temp = statistics.stdev(readings) if len(readings) > 1 else 0.0
    else:
        avg_temp = None
        std_temp = None

    payload = {
        "target_temp": setpoint,
        "hysteresis_band": HYSTERESIS_BAND,
        "heater_on_below": setpoint - HYSTERESIS_BAND,
        "heater_off_above": setpoint + HYSTERESIS_BAND,
        "log_interval_seconds": LOG_INTERVAL_SECONDS,
        "sample_count": len(readings),
        "average_temperature": avg_temp,
        "temperature_std_dev": std_temp,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        **get_schedule_context(config, replicate, setpoint),
    }

    with open(output_path, "w") as file:
        json.dump(payload, file, indent=4)

    return payload


def configure_segment_temperature(config, replicate):
    port = find_pico_port(config.get("pico_serial_port"))
    setpoint = get_effective_setpoint(config, replicate)
    set_pico_temperature(port, setpoint)
    start_pico_logging(port)
    context = get_schedule_context(config, replicate, setpoint)
    return port, setpoint, context
