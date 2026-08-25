"""
Redodo MPPT — Modbus register map.

All addresses and poll commands reverse-engineered from btsnoop_hci.log.
All CRC16-Modbus values verified against the captured traffic.

Registers marked TODO: confirmed zero/near-zero during an indoor test with
no solar input. Cross-reference with the official app outdoors in sunlight
to confirm exact meaning and scaling.
"""

# ---------------------------------------------------------------------------
# Device info block  (read once on connect)
# Request: 01 03 00 0A 00 10 64 04  → 16 registers @ 0x000A
# ---------------------------------------------------------------------------
REG_HW_VERSION = 0x000A  # Hardware revision (raw integer, e.g. 10260)
REG_FW_VERSION = 0x000B  # Firmware version  (raw integer, e.g. 6156)
REG_MODEL_START = 0x000C  # First of 7 registers holding ASCII model name
REG_MODEL_END = 0x0012  # "RO-MPPTCC244 " (each register = 2 ASCII bytes)
REG_UNK_014 = 0x0014  # TODO Confirm: observed 160
REG_RATED_W = 0x0015  # TODO Confirm: observed 150

# ---------------------------------------------------------------------------
# Real-time data — primary poll block
# Request: 01 03 01 01 00 13 54 3B  → 19 registers @ 0x0101
# ---------------------------------------------------------------------------

REG_SOC = 0x0101  # Battery state of charge (%)
REG_BATT_VOLTAGE = 0x0102  # Battery voltage  — divide by 10 → V  (observed 132 = 13.2V)

REG_CHARGE_CURRENT = 0x0103  # Charge current ÷100 e.g. 457 = 4.57A
REG_CHARGE_POWER = 0x0104  # Charge power e.g. 44 = 44W
REG_BATT_TEMP = 0x0105  # Battery temperature e.g. 7961 = 79.61 degrees F
REG_UNK_106 = 0x0106  # Unknown, always 0
REG_UNK_107 = 0x0107  # Unknown, always 0
REG_UNK_108 = 0x0108  # Unknown, always 0
REG_PV_VOLTAGE = 0x0109  # Solar voltage e.g. 445 ÷10 = 44.5V
REG_CHARGE_MAX_POWER = 0x010A  # Max solar power e.g. 107 = 107W
REG_CHARGE_AMOUNT = 0x010B  # Daily charge amount e.g. 191 = 191Wh
REG_UNK_10C = 0x010C  # Unknown, always 0 (TODO: these 3 could be related to discharge - always 0 in my case)
REG_UNK_10D = 0x010D  # Unknown, observed values: 0, 2
REG_UNK_10E = 0x010E  # Unknown, always 0
REG_DAYS_ON = 0x010F  # Days on-time e.g. 269 = 269 days
REG_UNK_110 = 0x0110  # Unknown, always 0
REG_CHARGE_AMOUNT_CUMULATIVE = 0x0111  # Total Wh charged e.g. 23252 = 23.252kWh
REG_UNK_112 = 0x0112  # Unknown, always 0 (TODO: likely related to discharge)
REG_DISCHARGE_AMOUNT_CUMULATIVE = (
    0x0113  # Cumulative total discharge amount, e.g. 398 -> 398Wh
)
# TODO: Poll past 0x0113 to maybe find mppt controller temp

# ---------------------------------------------------------------------------
# Real-time data — secondary poll block
# Request: 01 03 04 00 00 05 84 F9  → 5 registers @ 0x0400
# ---------------------------------------------------------------------------

REG_DAILY_CHARGE_AMOUNT = (
    0x0400  # Daily charge amount (mirrors 0x010B) e.g. 123 = 123Wh
)
REG_DAILY_DISCHARGE_AMOUNT = (
    0x0401  # Daily discharge amount (always 0 in my case) e.g. 123 = 123Wh
)
REG_DAILY_CHARGE_MAX_POWER = 0x0402  # Max charging power e.g. 129 = 129W
REG_DAILY_BATT_V_HIGHEST = 0x0403  # Highest daily battery voltage e.g. 135 = 13.5V
REG_DAILY_BATT_V_LOWEST = 0x0404  # Lowest daily battery voltage e.g. 129 = 12.9V

# ---------------------------------------------------------------------------
# Status registers
# ---------------------------------------------------------------------------
REG_STATUS_1 = 0x0121  # TODO: status / fault flags?
REG_STATUS_2 = 0x0122  # TODO: status / fault flags?

# ---------------------------------------------------------------------------
# Charge configuration block (static — changes only when user edits settings)
# Request: 01 03 02 01 00 11 E4 7E 15 C0  → 17 registers @ 0x0201
# Note: non-standard 10-byte command. E4 7E are an embedded extension field
#       (not a standard Modbus CRC). 15 C0 is CRC16-Modbus of the 8 preceding
#       bytes. Copy these bytes verbatim — do not recalculate.
# ---------------------------------------------------------------------------
REG_BATT_TYPE = 0x0201  # Battery type — observed 1 (1 = LiFePO4)
REG_SYS_VOLTAGE = 0x0202  # System voltage / cell count — observed 12
REG_CHARGE_STAGES = 0x0203  # Number of charge stages — observed 4
REG_ABSORPTION_V = 0x0204  # Bulk/absorption voltage (÷10 → V) — 144 = 14.4 V
REG_EQUALIZATION_V = 0x0205  # Equalisation voltage   (÷10 → V) — 144 = 14.4 V
REG_FLOAT_V = 0x0206  # Float voltage          (÷10 → V) — 144 = 14.4 V
REG_BOOST_RETURN_V = 0x0207  # Boost return voltage   (÷10 → V) — 132 = 13.2 V
REG_LOW_BATT_WARN_V = 0x0208  # Low battery warning    (÷10 → V) — 124 = 12.4 V
REG_LOW_BATT_CUT_V = 0x0209  # Low battery cutoff     (÷10 → V) — 120 = 12.0 V
REG_OVERDISCH_V = 0x020A  # Over-discharge protect (÷10 → V) — 108 = 10.8 V
REG_DISC_RECONNECT_V = 0x020B  # Discharge reconnect    (÷10 → V) — 120 = 12.0 V
REG_THRESH_12 = 0x020C  # TODO: threshold (÷10 → V)?        — 120 = 12.0 V
REG_TIMER_1 = 0x020D  # TODO: timer setting (hours?)       — observed 10
REG_TIMER_2 = 0x020E  # TODO: timer 2                      — observed 5
REG_MAX_CHARGE_A = 0x020F  # Max charge current (A)             — observed 15
REG_LOAD_SETTING = 0x0210  # TODO: load setting                 — observed 3
REG_LOAD_MAX = 0x0211  # TODO: load max                     — observed 30

# ---------------------------------------------------------------------------
# Pre-built poll commands (exact bytes, CRCs verified against btsnoop log)
# ---------------------------------------------------------------------------
POLL_DEVINFO = bytes.fromhex("0103000a00106404")  # 16 regs @ 0x000A
POLL_REALTIME = bytes.fromhex("010301010013543b")  # 19 regs @ 0x0101
POLL_EXTRA = bytes.fromhex("01030400000584f9")  # 5 regs  @ 0x0400
POLL_CONFIG = bytes.fromhex("010302010011e47e15c0")  # 17 regs @ 0x0201 (non-std)
POLL_STATUS1 = bytes.fromhex("010301210001d5fc")  # 1 reg   @ 0x0121
POLL_STATUS2 = bytes.fromhex("010301220001" + "25fc")  # 1 reg @ 0x0122

# Number of registers each poll command returns (for response validation)
POLL_DEVINFO_COUNT = 16
POLL_REALTIME_COUNT = 19
POLL_EXTRA_COUNT = 5
POLL_CONFIG_COUNT = 17

# Auto-built map of {constant_name → register_address} for all REG_* names.
# Any new REG_* constant added above is automatically included.
REGISTER_MAP: dict[str, int] = {
    k: v for k, v in globals().items() if k.startswith("REG_")
}
