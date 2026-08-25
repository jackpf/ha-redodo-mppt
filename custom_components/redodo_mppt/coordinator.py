"""
DataUpdateCoordinator for the Redodo MPPT integration.

Manages the BLE connection lifecycle and periodic Modbus polling.
Config (absorption/float voltage, max current) is fetched once on first
successful connect and stored as an attribute — it doesn't change between
polls so there's no need to read it every cycle.
"""

import logging
from datetime import timedelta
from typing import TypeVar, Callable

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import RedodoClient
from .const import DEFAULT_POLL_INTERVAL, DOMAIN, MAX_ERRORS_BEFORE_UNAVAILABLE
from .models import DeviceInfo, MPPTData, RealtimeData, ExtraData, ConfigData
from .parser import parse_config, parse_extra, parse_realtime, parse_device_info
from .registers import POLL_DEVINFO, POLL_REALTIME, POLL_EXTRA, POLL_CONFIG

_LOGGER = logging.getLogger(__name__)


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
        self._consecutive_errors = 0

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
        except Exception as exc:
            raise UpdateFailed(f"BLE connection failed: {exc}") from exc

        self._client = client
        _LOGGER.info("Connected to Redodo MPPT at %s", self._address)

    async def _disconnect(self) -> None:
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    T = TypeVar("T")
    async def _try_poll(self, command: bytes, parse_fn: Callable[[bytes], T]) -> T | None:
        try:
            return parse_fn(await self._client.poll(command))
        except Exception as exc:
            _LOGGER.warning("Poll failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # DataUpdateCoordinator protocol
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> MPPTData:
        try:
            if not self._is_connected():
                await self._connect()
                self.device_info = None # Re-fetch

            if self.device_info is None:
                self.device_info = await self._try_poll(POLL_DEVINFO, parse_device_info)

            realtime_data = await self._try_poll(POLL_REALTIME, parse_realtime)

            # If primary poll fails, we stop
            if realtime_data is None:
                raise UpdateFailed("Poll failed")

            extra_data = await self._try_poll(POLL_EXTRA, parse_extra)
            config_data = await self._try_poll(POLL_CONFIG, parse_config)

            self._consecutive_errors = 0 # Reset consecutive errors
            return MPPTData.from_blocks(realtime_data, extra_data, config_data)
        except UpdateFailed:
            raise
        except Exception as exc:
            self._consecutive_errors += 1
            _LOGGER.warning(
                "Poll error %d/%d: %s",
                self._consecutive_errors,
                MAX_ERRORS_BEFORE_UNAVAILABLE,
                exc,
            )
            await self._disconnect()

            raise UpdateFailed(str(exc)) from exc

    async def async_shutdown(self) -> None:
        """Disconnect cleanly when the integration is unloaded."""
        await self._disconnect()
        await super().async_shutdown()
