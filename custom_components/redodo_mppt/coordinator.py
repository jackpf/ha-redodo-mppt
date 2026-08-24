"""
DataUpdateCoordinator for the Redodo MPPT integration.

Manages the BLE connection lifecycle and periodic Modbus polling.
Config (absorption/float voltage, max current) is fetched once on first
successful connect and stored as an attribute — it doesn't change between
polls so there's no need to read it every cycle.
"""

import asyncio
import logging
from datetime import timedelta

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import RedodoClient
from .const import DEFAULT_POLL_INTERVAL, DOMAIN, MAX_ERRORS_BEFORE_UNAVAILABLE
from .models import DeviceInfo, MPPTData
from .parser import merge_extra, parse_config, parse_devinfo, parse_realtime

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
        self._config_fetched = False

        # Populated on first successful connect; exposed as a property so
        # sensor entities can read it for device_info without re-polling.
        self.device_info: DeviceInfo | None = None

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    async def _ensure_connected(self) -> RedodoClient:
        """Return a connected client, creating/reconnecting as needed."""
        if self._client and self._client.is_connected:
            return self._client

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
        self._config_fetched = False  # re-fetch config after reconnect
        _LOGGER.info("Connected to Redodo MPPT at %s", self._address)
        return client

    async def _fetch_static_data(self, client: RedodoClient) -> None:
        """Read device info and config once per connection."""
        try:
            raw_devinfo = await client.poll_devinfo()
            self.device_info = parse_devinfo(raw_devinfo)
            _LOGGER.debug("Device info: %s", self.device_info)
        except Exception as exc:
            _LOGGER.warning("Failed to read device info: %s", exc)

    # ------------------------------------------------------------------
    # DataUpdateCoordinator protocol
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> MPPTData:
        try:
            client = await self._ensure_connected()

            # One-time static reads after each new connection
            if not self._config_fetched:
                await self._fetch_static_data(client)
                self._config_fetched = True

            # Primary real-time poll
            raw_realtime = await client.poll_realtime()
            data = parse_realtime(raw_realtime)

            # Supplemental poll — merges battery voltage mirror + PV fields
            try:
                raw_extra = await client.poll_extra()
                data = merge_extra(raw_extra, data)
            except Exception as exc:
                _LOGGER.debug("Extra poll failed (non-fatal): %s", exc)

            # Config poll — only on first cycle after connect
            if not hasattr(self, "_config_merged") or not self._config_merged:
                try:
                    raw_config = await client.poll_config()
                    data = parse_config(raw_config, data)
                    self._config_merged = True
                except Exception as exc:
                    _LOGGER.debug("Config poll failed (non-fatal): %s", exc)
                    self._config_merged = False

            if not data.is_valid():
                raise UpdateFailed("Response parsed but produced no usable data")

            self._consecutive_errors = 0
            return data

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
            # Drop the connection so _ensure_connected reconnects next cycle
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
                self._client = None

            raise UpdateFailed(str(exc)) from exc

    async def async_shutdown(self) -> None:
        """Disconnect cleanly when the integration is unloaded."""
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        await super().async_shutdown()
