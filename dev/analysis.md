# Redodo MPPT Charge Controller — Bluetooth Protocol Analysis

> Reverse-engineered from `btsnoop_hci.log` captured during a session with the official Redodo Android app.  
> Device model: **RO-MPPTCC244** (Redodo MPPT CC, likely 12V/40A or 24V/40A).

---

## Protocol Summary

### Transport Layer (BLE GATT)

The app communicates through a single custom GATT characteristic:

| Item | Value |
|------|-------|
| **Service** | `0xFFE0` (handles `0x000E–0x0013`) |
| **Data Characteristic** | UUID `0xFFE1`, value handle **`0x0012`**, props: Read + Write + WriteNoResp + **Notify** |
| **Write-only char** | UUID `0xFFE2`, handle `0x0010` (not used in this session) |
| **CCCD** | Handle `0x0013` (UUID `0x2902`) — write `01 00` to enable notifications |
| **MTU** | 131 bytes (negotiated) |

There is also a second custom service `f000ffc0-0451-4000-b000-000000000000` with two writable/notifiable characteristics (`f000ffc1` and `f000ffc2`) — likely for OTA firmware updates — but it was not used during this session.

### Application Protocol: Modbus RTU over GATT

**All CRCs verified.** The device speaks **Modbus RTU FC03 (Read Holding Registers)** tunnelled over BLE.

- Commands are sent as ATT **`WRITE_CMD`** (Write Without Response, opcode `0x52`) to handle `0x0012`.
- Responses arrive as **`HANDLE_VALUE_NTF`** (notification, opcode `0x1B`) on the same handle.
- Responses may span two HCI ACL fragments — this is handled transparently by any standard BLE library (e.g. `bleak`).

**Modbus device address: `0x01`**

---

## Register Map

### Device Info — read once on connect

```
Request:  01 03 00 0A 00 10 64 04   (FC03, read 16 regs @ 0x000A)
```

| Register | Value (hex) | Meaning |
|----------|-------------|---------|
| `0x000A` | `0x2814` = 10260 | Hardware revision |
| `0x000B` | `0x180C` = 6156 | Firmware version |
| `0x000C–0x0012` | ASCII | Model name: **"RO-MPPTCC244 "** |
| `0x0014` | 160 | Rated current? (16.0A) |
| `0x0015` | 150 | Rated power? (150W) |

---

### Real-time Data — primary poll block

```
Request:  01 03 01 01 00 13 54 3B   (FC03, read 19 regs @ 0x0101)
```

| Register | Observed | Likely Meaning |
|----------|----------|----------------|
| `0x0101` | 99–100 | **Battery SOC (%)** ✓ high confidence |
| `0x0102` | 132 | **Battery voltage × 0.1V = 13.2V** ✓ high confidence |
| `0x0103–0x0104` | 0 | Unknown |
| `0x0105` | 6169 | Energy accumulator (Wh?) |
| `0x0106–0x0109` | 0 | Unknown |
| `0x010A` | 107 | PV voltage × 0.1V = 10.7V, or temperature (low-light indoor test) |
| `0x010B` | 22 | PV current × 0.01A = 0.22A, OR PV voltage × 0.1V = 2.2V |
| `0x010C–0x010E` | 0 | Unknown |
| `0x010F` | 269 | Some counter (today's Wh?) |
| `0x0110` | 0 | Unknown |
| `0x0111` | 22990 | Large accumulator (total Wh/Ah?) |
| `0x0112` | 0 | Unknown |
| `0x0113` | 398 | Some counter (cycle count?) |

> **Note:** The log was captured **indoors with minimal solar**, so PV registers show near-zero values. Take a second log outdoors while actively charging to confirm which register is PV voltage vs. current vs. power.

---

### Real-time Data — secondary poll block

```
Request:  01 03 04 00 00 05 84 F9   (FC03, read 5 regs @ 0x0400)
```

| Register | Value | Notes |
|----------|-------|-------|
| `0x0400` | 22 | Same value as `0x010B` — likely PV-related |
| `0x0401` | 0 | Unknown |
| `0x0402` | 107 | Same value as `0x010A` — likely PV voltage or power |
| `0x0403` | 132 | **Battery voltage × 0.1V = 13.2V** (mirrors `0x0102`) |
| `0x0404` | 132 | Output/load voltage? |

---

### Configuration — static charge settings

```
Request:  01 03 02 01 00 11 E4 7E 15 C0   (10-byte variant — see note below)
```

| Register | Value | Meaning (÷10 for volts) |
|----------|-------|-------------------------|
| `0x0201` | 1 | Battery type (1 = LiFePO4?) |
| `0x0202` | 12 | System voltage / cell count? |
| `0x0203` | 4 | Charge stages |
| `0x0204` | 144 | Bulk/Absorption voltage = **14.4V** |
| `0x0205` | 144 | Equalisation voltage = **14.4V** |
| `0x0206` | 144 | Float voltage = **14.4V** |
| `0x0207` | 132 | Boost return voltage = **13.2V** |
| `0x0208` | 124 | Low battery warning = **12.4V** |
| `0x0209` | 120 | Low battery cutoff = **12.0V** |
| `0x020A` | 108 | Over-discharge protect = **10.8V** |
| `0x020B–0x020C` | 120 | Reconnect thresholds |
| `0x020D` | 10 | Timer setting (hours?) |
| `0x020E` | 5 | Timer 2? |
| `0x020F` | 15 | Max charge current = **15A** |
| `0x0210` | 3 | Load setting |
| `0x0211` | 30 | Load max |

> **10-byte command anomaly:** The `0x0201` read uses a non-standard 10-byte payload: `01 03 02 01 00 11 E4 7E 15 C0`. The `E4 7E` bytes are **not** a standard Modbus CRC — the correct Modbus CRC for the 6-byte frame would be `D5 BE`. Instead, `15 C0` is CRC16-Modbus of the full preceding 8 bytes, making `E4 7E` an embedded extension field (possibly a secondary device address or session token). No other common CRC variant (`CCITT`, `ARC`, `USB`, `X25`, `Kermit`) matches `E4 7E` either.
>
> **For implementation: copy these bytes exactly.**

---

### Status registers (always read as 0x0000 in this session)

| Request | Register | Notes |
|---------|----------|-------|
| `01 03 01 21 00 01 D5 FC` | `0x0121` | Status flag |
| `01 03 01 22 00 01 25 FC` | `0x0122` | Status flag |

---

## App Polling Loop

The app repeats this sequence every few seconds:

| Step | Bytes (hex) | Description |
|------|-------------|-------------|
| 1 | `01 03 01 21 00 01 D5 FC` | Read status @ `0x0121` |
| 2 | `01 03 01 01 00 13 54 3B` | Read 19 real-time regs @ `0x0101` |
| 3 | `01 03 04 00 00 05 84 F9` | Read 5 real-time regs @ `0x0400` |
| 4 | `01 03 02 01 00 11 E4 7E 15 C0` | Read 17 config regs @ `0x0201` |
| 5 | `01 03 01 22 00 01 25 FC` | Read status @ `0x0122` |

Periodically also reads:
- `01 03 00 0A 00 10 64 04` — device info / model name
- `01 03 00 0B 00 01 F5 C8` — firmware version only

---

## Home Assistant Implementation Sketch

Use `bleak` for BLE communication.

```python
import struct
import asyncio
from bleak import BleakClient

DEVICE_ADDRESS = "XX:XX:XX:XX:XX:XX"  # BLE MAC of your controller
FFE1_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
CCCD_HANDLE = 0x0013  # or discover via GATT

# Modbus FC03 read requests
CMD_REALTIME  = bytes.fromhex("010301010013543b")  # 19 regs @ 0x0101
CMD_EXTRA     = bytes.fromhex("01030400000584f9")  # 5 regs  @ 0x0400
CMD_DEVINFO   = bytes.fromhex("0103000a00106404")  # 16 regs @ 0x000A
CMD_CONFIG    = bytes.fromhex("010302010011e47e15c0")  # 17 regs @ 0x0201 (non-standard)

def parse_modbus_response(data: bytes) -> list[int]:
    """Parse Modbus FC03 response, return list of register values."""
    if len(data) < 3 or data[1] != 0x03:
        return []
    byte_count = data[2]
    raw = data[3:3 + byte_count]
    return [struct.unpack(">H", raw[i:i+2])[0] for i in range(0, len(raw), 2)]

async def monitor(address: str):
    async with BleakClient(address) as client:
        # Enable notifications on FFE1
        await client.write_gatt_descriptor(CCCD_HANDLE, b"\x01\x00")

        response_buf: list[bytes] = []

        def on_notify(handle, data: bytes):
            regs = parse_modbus_response(data)
            if not regs:
                return
            # Main real-time block (0x0101, 19 regs)
            if len(regs) == 19:
                soc        = regs[0]          # %
                batt_v     = regs[1] / 10.0   # V
                print(f"SOC: {soc}%  Battery: {batt_v:.1f}V")
            # Supplemental block (0x0400, 5 regs)
            elif len(regs) == 5:
                batt_v2 = regs[3] / 10.0
                print(f"Battery (alt): {batt_v2:.1f}V")

        await client.start_notify(FFE1_UUID, on_notify)

        while True:
            await client.write_gatt_char(FFE1_UUID, CMD_REALTIME, response=False)
            await asyncio.sleep(1)
            await client.write_gatt_char(FFE1_UUID, CMD_EXTRA, response=False)
            await asyncio.sleep(4)
```

---

## What Still Needs Outdoor Confirmation

The capture was done indoors with essentially no solar input, so PV registers are near-zero. The following require a second capture **outdoors in sunlight**:

| Register(s) | Currently | To confirm |
|-------------|-----------|------------|
| `0x010A` / `0x0402` | 107 | PV voltage (×0.1V) vs. temperature vs. power |
| `0x010B` / `0x0400` | 22 | PV current (×0.01A) vs. PV voltage (×0.1V) |
| `0x0105` | 6169 | Unit: Wh, ×0.1kWh, or something else |
| `0x010F`, `0x0113` | 269, 398 | Today's energy? Cycle count? |

**High-confidence readings (confirmed from this capture):**

- `0x0101` → Battery SOC (%)
- `0x0102` → Battery voltage (÷10 → V) — observed 13.2V, consistent with full LiFePO4
- `0x0403` → Battery voltage (duplicate / output channel)
- `0x0204–0x020A` → Charge voltage thresholds (÷10 → V)
