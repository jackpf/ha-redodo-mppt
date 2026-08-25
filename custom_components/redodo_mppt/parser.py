"""
Pure Modbus RTU response parser — no I/O, fully unit-testable.

All functions accept the raw notification payload (starting from the Modbus
address byte) and return structured data or raise ValueError on malformed input.
"""

import struct

from .models import DeviceInfo, MPPTData
from .registers import (
    POLL_CONFIG_COUNT,
    POLL_DEVINFO_COUNT,
    POLL_EXTRA_COUNT,
    POLL_REALTIME_COUNT,
    REGISTER_MAP,
    REG_ABSORPTION_V,
    REG_BATT_VOLTAGE,
    REG_BATT_VOLTAGE2,
    REG_TOTAL_DISCHARGE,
    REG_BATT_TEMP,
    REG_FW_VERSION,
    REG_HW_VERSION,
    REG_MAX_CHARGE_A,
    REG_MODEL_START,
    REG_OUTPUT_V,
    REG_PV_CURRENT,
    REG_PV_CURRENT2,
    REG_PV_VOLTAGE,
    REG_PV_VOLTAGE2,
    REG_RATED_A,
    REG_RATED_W,
    REG_SOC,
    REG_TODAY_ENERGY,
    REG_TOTAL_AH,
    REG_FLOAT_V,
)


def _crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def validate_crc(payload: bytes) -> bool:
    """Return True if the last two bytes are a valid CRC16-Modbus checksum."""
    if len(payload) < 4:
        return False
    body, stored = payload[:-2], struct.unpack_from("<H", payload, len(payload) - 2)[0]
    return _crc16(body) == stored


def _unpack_registers(payload: bytes, expected_count: int) -> list[int]:
    """
    Parse a Modbus FC03 response payload into a list of 16-bit register values.

    Raises ValueError if the payload is malformed, CRC fails, or register
    count doesn't match expected_count.
    """
    if len(payload) < 5:
        raise ValueError(f"Payload too short: {len(payload)} bytes")
    if payload[1] != 0x03:
        raise ValueError(f"Unexpected function code: 0x{payload[1]:02X}")
    if not validate_crc(payload):
        raise ValueError("CRC mismatch")

    byte_count = payload[2]
    data = payload[3 : 3 + byte_count]

    if len(data) != byte_count:
        raise ValueError(f"Truncated data: expected {byte_count} bytes, got {len(data)}")

    count = byte_count // 2
    if count != expected_count:
        raise ValueError(f"Register count mismatch: expected {expected_count}, got {count}")

    return [struct.unpack_from(">H", data, i * 2)[0] for i in range(count)]


# ---------------------------------------------------------------------------
# Public parse functions
# ---------------------------------------------------------------------------

def parse_realtime(payload: bytes) -> MPPTData:
    """Decode the 19-register POLL_REALTIME response (0x0101 block)."""
    regs = _unpack_registers(payload, POLL_REALTIME_COUNT)
    base = REG_SOC  # 0x0101

    def r(addr: int) -> int:
        return regs[addr - base]

    return MPPTData(
        soc=r(REG_SOC),
        battery_voltage=r(REG_BATT_VOLTAGE) / 10.0,
        pv_voltage=r(REG_PV_VOLTAGE) / 10.0,
        pv_current=r(REG_PV_CURRENT) / 100.0,
        battery_temp=r(REG_BATT_TEMP),
        today_energy=r(REG_TODAY_ENERGY),
        total_ah=r(REG_TOTAL_AH),
        total_discharge=r(REG_TOTAL_DISCHARGE),
    )


def merge_extra(payload: bytes, data: MPPTData) -> MPPTData:
    """
    Decode the 5-register POLL_EXTRA response (0x0400 block) and merge into
    an existing MPPTData. Battery voltage is updated from the confirmed register;
    PV fields are updated only if the primary block left them as None.
    """
    regs = _unpack_registers(payload, POLL_EXTRA_COUNT)
    base = 0x0400

    def r(addr: int) -> int:
        return regs[addr - base]

    # 0x0403 is the confirmed battery voltage mirror — update unconditionally
    data.battery_voltage = r(REG_BATT_VOLTAGE2) / 10.0

    # Only fill PV fields if still unset (primary block takes priority)
    if data.pv_voltage is None:
        data.pv_voltage = r(REG_PV_VOLTAGE2) / 10.0
    if data.pv_current is None:
        data.pv_current = r(REG_PV_CURRENT2) / 100.0

    return data


def parse_config(payload: bytes, data: MPPTData) -> MPPTData:
    """Decode the 17-register POLL_CONFIG response (0x0201 block) and merge."""
    regs = _unpack_registers(payload, POLL_CONFIG_COUNT)
    base = 0x0201

    def r(addr: int) -> int:
        return regs[addr - base]

    data.absorption_voltage = r(REG_ABSORPTION_V) / 10.0
    data.float_voltage = r(REG_FLOAT_V) / 10.0
    data.max_charge_current = r(REG_MAX_CHARGE_A)
    return data


def parse_debug(payloads: dict[str, bytes]) -> dict[str, int]:
    """
    Parse all poll block payloads and return {REG_NAME: raw_int} for every
    named register found across all blocks.

    Expected keys in payloads: devinfo / realtime / extra / config /
    status1 / status2.  Missing keys are silently skipped.
    """
    _blocks: dict[str, tuple[int, int]] = {
        "devinfo":  (0x000A, POLL_DEVINFO_COUNT),
        "realtime": (0x0101, POLL_REALTIME_COUNT),
        "extra":    (0x0400, POLL_EXTRA_COUNT),
        "config":   (0x0201, POLL_CONFIG_COUNT),
        "status1":  (0x0121, 1),
        "status2":  (0x0122, 1),
    }

    raw: dict[str, int] = {}
    for block_name, (base, count) in _blocks.items():
        payload = payloads.get(block_name)
        if payload is None:
            continue
        try:
            regs = _unpack_registers(payload, count)
        except ValueError as exc:
            raw[f"[{block_name} parse error]"] = str(exc)  # type: ignore[assignment]
            continue
        for name, addr in REGISTER_MAP.items():
            offset = addr - base
            if 0 <= offset < len(regs):
                raw[name] = regs[offset]

    return dict(sorted(raw.items(), key=lambda kv: REGISTER_MAP.get(kv[0], 0xFFFF)))


def parse_devinfo(payload: bytes) -> DeviceInfo:
    """Decode the 16-register POLL_DEVINFO response (0x000A block)."""
    regs = _unpack_registers(payload, POLL_DEVINFO_COUNT)
    base = 0x000A

    def r(addr: int) -> int:
        return regs[addr - base]

    # Model name: registers 0x000C–0x0012, each holding two ASCII bytes
    model_bytes = b"".join(
        struct.pack(">H", r(addr))
        for addr in range(REG_MODEL_START, REG_MODEL_START + 7)
    )
    model = model_bytes.decode("ascii", errors="replace").rstrip("\x00 ")

    return DeviceInfo(
        model=model,
        hw_version=r(REG_HW_VERSION),
        fw_version=r(REG_FW_VERSION),
        rated_current=r(REG_RATED_A),
        rated_power=r(REG_RATED_W),
    )
