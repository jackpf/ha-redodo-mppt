"""
Redodo MPPT — standalone CLI polling tool.

Usage:
    python cli.py                        # scan and pick device interactively
    python cli.py --address C8:47:80:07:E8:78
    python cli.py --address C8:47:80:07:E8:78 --interval 5

Useful for:
  - Verifying the BLE connection works before touching HA
  - Capturing register values outdoors to confirm the PV register map
  - Quickly checking device state without opening the official app

On macOS, bleak identifies BLE devices by UUID rather than MAC address.
Use --scan to list nearby devices and copy the UUID to use as --address.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import os

# Resolve the path to custom_components/ regardless of where cli.py is invoked from
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "custom_components"))

from redodo_mppt.client import RedodoClient, FFE1_UUID  # noqa: E402
from redodo_mppt.parser import (  # noqa: E402
    merge_extra,
    parse_config,
    parse_devinfo,
    parse_realtime,
)
from redodo_mppt.const import SERVICE_UUID  # noqa: E402

from bleak import BleakScanner  # noqa: E402
from bleak.backends.device import BLEDevice  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(label: str, value: object, unit: str = "") -> str:
    if value is None:
        return f"  {label:<30} —"
    return f"  {label:<30} {value}{(' ' + unit) if unit else ''}"


async def scan_and_pick() -> BLEDevice:
    """Scan for nearby BLE devices and let the user pick one."""
    print("Scanning for BLE devices (10 s)...")
    devices = await BleakScanner.discover(timeout=10.0, return_adv=False)

    candidates = [d for d in devices if d.name]
    if not candidates:
        print("No named BLE devices found.")
        sys.exit(1)

    print("\nFound devices:")
    for i, d in enumerate(candidates):
        print(f"  [{i}] {d.name}  ({d.address})")

    idx = int(input("\nSelect device number: "))
    return candidates[idx]


async def find_by_address(address: str) -> BLEDevice:
    """Resolve a BLE address/UUID to a BLEDevice object."""
    device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    if device is None:
        print(f"Device not found: {address}")
        sys.exit(1)
    return device


# ---------------------------------------------------------------------------
# Main poll loop
# ---------------------------------------------------------------------------

async def run(address: str | None, interval: int) -> None:
    device = await (find_by_address(address) if address else scan_and_pick())
    print(f"\nConnecting to {device.name} ({device.address})...")

    client = RedodoClient(device)
    await client.connect()
    print("Connected.\n")

    # One-time reads
    try:
        devinfo = parse_devinfo(await client.poll_devinfo())
        print("Device info")
        print(_fmt("Model", devinfo.model))
        print(_fmt("HW version", devinfo.hw_version))
        print(_fmt("FW version", devinfo.fw_version))
        print(_fmt("Rated current", devinfo.rated_current, "× (unit TBC)"))
        print(_fmt("Rated power",   devinfo.rated_power,   "× (unit TBC)"))
        print()
    except Exception as exc:
        print(f"[!] Device info read failed: {exc}\n")

    try:
        data = parse_realtime(await client.poll_realtime())
        data = parse_config(await client.poll_config(), data)
    except Exception as exc:
        print(f"[!] Initial poll failed: {exc}")
        await client.disconnect()
        sys.exit(1)

    print(f"Polling every {interval}s  (Ctrl-C to stop)\n")

    try:
        while True:
            try:
                raw_rt = await client.poll_realtime()
                data = parse_realtime(raw_rt)
                raw_ex = await client.poll_extra()
                data = merge_extra(raw_ex, data)
            except Exception as exc:
                print(f"[!] Poll error: {exc}")
                await asyncio.sleep(interval)
                continue

            print("─" * 42)
            # Confirmed
            print(_fmt("Battery SOC",     data.soc,             "%"))
            print(_fmt("Battery voltage", data.battery_voltage,  "V"))
            # Unconfirmed (shown with label so you can cross-reference the app)
            print(_fmt("PV voltage  [TODO: confirm]", data.pv_voltage,  "V?"))
            print(_fmt("PV current  [TODO: confirm]", data.pv_current,  "A?"))
            print(_fmt("Energy acc  [TODO: confirm]", data.energy_acc,  "raw"))
            print(_fmt("Today energy[TODO: confirm]", data.today_energy, "raw"))
            print(_fmt("Total Ah    [TODO: confirm]", data.total_ah,    "raw"))
            print(_fmt("Cycle count [TODO: confirm]", data.cycle_count, "raw"))

            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Redodo MPPT CLI monitor")
    parser.add_argument(
        "--address",
        help="BLE address or UUID of the controller (skip interactive scan)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Poll interval in seconds (default: 5)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.address, args.interval))


if __name__ == "__main__":
    main()
