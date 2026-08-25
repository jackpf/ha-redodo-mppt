"""
Redodo MPPT — standalone CLI register dump tool.

Connects to the controller, reads all known Modbus registers, and prints
every REG_* constant alongside its raw integer value — sorted by address.
Repeats every --interval seconds so you can watch values change in real time.

Usage:
    python cli.py                        # scan and pick device interactively
    python cli.py --address C8:47:80:07:E8:78
    python cli.py --address C8:47:80:07:E8:78 --interval 5

On macOS, bleak identifies BLE devices by UUID rather than MAC address.
Use the interactive scan to list nearby devices and copy the UUID.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Resolve the path to custom_components/ regardless of where cli.py is invoked from
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, "custom_components"))

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from redodo_mppt.client import RedodoClient
from redodo_mppt.parser import parse_debug, parse_device_info
from redodo_mppt.registers import (
    POLL_CONFIG,
    POLL_DEVINFO,
    POLL_EXTRA,
    POLL_REALTIME,
    POLL_STATUS1,
    POLL_STATUS2,
    REGISTER_MAP,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def scan_and_pick() -> BLEDevice:
    """Scan for nearby BLE devices and let the user pick one."""
    print("Scanning for BLE devices...")
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


def _print_dump(dump: dict[str, int]) -> None:
    print("Register dump")
    print("─" * 52)
    for name, value in dump.items():
        addr = REGISTER_MAP.get(name)
        addr_str = f"0x{addr:04X}" if addr is not None else "      "
        print(f"  {name:<28} {addr_str}   {value}")
    print()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def run(address: str | None, interval: int) -> None:
    device = await (find_by_address(address) if address else scan_and_pick())
    print(f"\nConnecting to {device.name} ({device.address})...")

    client = RedodoClient(device)
    await client.connect()
    print("Connected.\n")

    # One-time device info
    try:
        devinfo = parse_device_info(await client.poll(POLL_DEVINFO))
        print(f"  Model      {devinfo.model}")
        print(f"  HW version {devinfo.hw_version}")
        print(f"  FW version {devinfo.fw_version}")
        print()
    except Exception as exc:  # noqa: BLE001
        print(f"[!] Device info read failed: {exc}\n")

    print(f"Polling every {interval}s  (Ctrl-C to stop)\n")

    try:
        while True:
            payloads: dict[str, bytes] = {}
            errors: list[str] = []

            for block_name, command in [
                ("devinfo", POLL_DEVINFO),
                ("realtime", POLL_REALTIME),
                ("extra", POLL_EXTRA),
                ("config", POLL_CONFIG),
                ("status1", POLL_STATUS1),
                ("status2", POLL_STATUS2),
            ]:
                try:
                    payloads[block_name] = await client.poll(command)
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"[!] {block_name}: {exc}")

            dump = parse_debug(payloads)
            _print_dump(dump)

            for err in errors:
                print(err)

            await asyncio.sleep(interval)
    finally:
        await client.disconnect()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Redodo MPPT register dump")
    parser.add_argument(
        "--address",
        help="BLE address or UUID of the controller",
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
