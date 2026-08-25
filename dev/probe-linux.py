import asyncio
from bleak import BleakClient

MAC_ADDRESS = "C8:47:80:07:E8:78"

async def main():
    async with BleakClient(MAC_ADDRESS) as client:
        print(f"Connected to {MAC_ADDRESS}!")
        for service in client.services:
            print(f"\n[Service] {service.uuid}")
            for char in service.characteristics:
                print(f"  [Char] {char.uuid} | Properties: {char.properties}")

asyncio.run(main())