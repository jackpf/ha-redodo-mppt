"""
BLE + Modbus RTU communication layer for the Redodo MPPT controller.

Protocol summary:
  - Service:    0xFFE0
  - Characteristic: 0xFFE1 (Write Without Response + Notify)
  - Transport:  Modbus RTU frames sent as GATT WRITE_CMD, responses arrive
                as HANDLE_VALUE_NTF on the same characteristic.
  - Request/response correlation: implicit (one request in flight at a time).
    An asyncio.Queue buffers incoming notifications; the caller awaits it
    with a configurable timeout.
"""

import asyncio
import logging

from bleak import BleakClient
from bleak.backends.device import BLEDevice

_LOGGER = logging.getLogger(__name__)

FFE1_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
RESPONSE_TIMEOUT = 5.0  # seconds to wait for a notification after sending a command


class RedodoClient:
    """Manages one active BLE connection to a Redodo MPPT controller."""

    def __init__(self, ble_device: BLEDevice) -> None:
        self._device = ble_device
        self._client: BleakClient | None = None
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the device and enable notifications."""
        self._client = BleakClient(self._device, disconnected_callback=self._on_disconnect)
        await self._client.connect()
        await self._client.start_notify(FFE1_UUID, self._on_notification)
        _LOGGER.debug("Connected to %s", self._device.address)

    async def disconnect(self) -> None:
        if self._client and self._client.is_connected:
            await self._client.stop_notify(FFE1_UUID)
            await self._client.disconnect()
        self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    def _on_disconnect(self, client: BleakClient) -> None:
        _LOGGER.warning("BLE device disconnected: %s", self._device.address)
        self._client = None

    def _on_notification(self, handle: int, data: bytes) -> None:
        _LOGGER.debug("← NTF (%d bytes): %s", len(data), data.hex())
        self._queue.put_nowait(data)

    # ------------------------------------------------------------------
    # Low-level send/receive
    # ------------------------------------------------------------------

    async def _send(self, command: bytes) -> bytes:
        """
        Write a Modbus command and return the raw notification response.

        Drains any stale notifications before sending so we always get the
        response that corresponds to this specific command.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected")

        # Drain stale notifications (e.g. from a previous timed-out request)
        while not self._queue.empty():
            self._queue.get_nowait()

        _LOGGER.debug("→ CMD (%d bytes): %s", len(command), command.hex())
        await self._client.write_gatt_char(FFE1_UUID, command, response=False)

        try:
            return await asyncio.wait_for(self._queue.get(), timeout=RESPONSE_TIMEOUT)
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"No response from device within {RESPONSE_TIMEOUT}s"
            ) from exc

    # ------------------------------------------------------------------
    # Public poll methods
    # ------------------------------------------------------------------

    async def poll(self, command: bytes) -> bytes:
        """Poll the given command."""
        return await self._send(command)
