"""
DataUpdateCoordinator for the Redodo MPPT integration.

Manages the BLE connection lifecycle and periodic Modbus polling.
"""

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import TypeVar

from bleak import BleakError
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import RedodoClient
from .const import DEFAULT_POLL_INTERVAL, DOMAIN
from .models import DeviceInfo, MPPTData
from .parser import parse_config, parse_device_info, parse_extra, parse_realtime
from .registers import POLL_CONFIG, POLL_DEVINFO, POLL_EXTRA, POLL_REALTIME

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")
class RedodoCoordinator(DataUpdateCoordinator[MPPTData]):
    """Polls the Redodo MPPT controller over BLE on a fixed interval."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )
        self._address = address
        self._client: RedodoClient | None = None

        # Populated on first successful connect; exposed as a property so
        # sensor entities can read it for device_info without re-polling.
        self.device_info: DeviceInfo | None = None

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    async def _connect(self) -> None:
        """Creates a connected client."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"Device {self._address} not found — is it in range and powered on?"
            )

        client = RedodoClient(ble_device)
        try:
            await client.connect()
        except BleakError as exc:
            raise UpdateFailed(f"BLE connection failed: {exc}") from exc

        self._client = client
        _LOGGER.info("Connected to Redodo MPPT at %s", self._address)

    async def _disconnect(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except BleakError as exc:
                _LOGGER.warning("Disconnect failed: %s", exc)
            self._client = None

    async def _try_poll(
        self, command: bytes, parse_fn: Callable[[bytes], T]
    ) -> T | None:
        try:
            return parse_fn(await self._client.poll(command))
        except Exception as exc: # noqa: BLE001
            _LOGGER.warning("Poll failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # DataUpdateCoordinator protocol
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> MPPTData:
        try:
            if not self._is_connected():
                await self._connect()
                self.device_info = None  # Re-fetch

            if self.device_info is None:
                self.device_info = await self._try_poll(POLL_DEVINFO, parse_device_info)

            realtime_data = await self._try_poll(POLL_REALTIME, parse_realtime)

            # If primary poll fails, we stop
            if realtime_data is None:
                raise UpdateFailed("Poll failed")

            extra_data = await self._try_poll(POLL_EXTRA, parse_extra)
            config_data = await self._try_poll(POLL_CONFIG, parse_config)

            return MPPTData.from_blocks(realtime_data, extra_data, config_data)
        except UpdateFailed:
            raise
        except (BleakError, ValueError) as exc:
            await self._disconnect()
            raise UpdateFailed(str(exc)) from exc

    async def async_shutdown(self) -> None:
        """Disconnect cleanly when the integration is unloaded."""
        await self._disconnect()
        await super().async_shutdown()
