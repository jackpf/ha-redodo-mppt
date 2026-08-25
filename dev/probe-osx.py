import asyncio

from bleak import BleakClient, BleakScanner


async def main():
    print("Scanning for BT-ROCC2440...")

    # Find the device by name
    device = await BleakScanner.find_device_by_name("BT-ROCC2440", timeout=10.0)

    if not device:
        # Fallback search if the name is slightly different
        devices = await BleakScanner.discover()
        for d in devices:
            if d.name and "ROCC" in d.name:
                device = d
                break

    if not device:
        print(
            "Device not found! Make sure your phone's Bluetooth is turned OFF so it releases the connection."
        )
        return

    print(f"Found Device! Name: {device.name}")
    print(f"Mac OS UUID: {device.address}")  # This will print the Mac UUID!

    print("\nConnecting to dump services...")
    async with BleakClient(device) as client:
        print("Connected!")
        for service in client.services:
            print(f"\n[Service] {service.uuid}")
            for char in service.characteristics:
                print(f"  [Char] {char.uuid} | Properties: {char.properties}")


asyncio.run(main())
