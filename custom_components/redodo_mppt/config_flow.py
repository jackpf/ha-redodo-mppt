"""Config flow for the Redodo MPPT integration.

Step 1: HA's bluetooth scanner feeds us a list of nearby BLE devices that
        advertise the 0xFFE0 service. We filter that list and present it to
        the user as a dropdown.
Step 2: User selects a device → we store its address and name in the config
        entry.

The flow can also be triggered automatically by HA when it detects a device
advertising the service UUID declared in manifest.json.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import CONF_NAME, DOMAIN, SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


class RedodoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Redodo MPPT config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_devices: dict[str, str] = {}  # address → name

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Triggered when the user clicks 'Add Integration' in the UI."""
        return await self._async_show_device_picker(user_input)

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """
        Triggered automatically by HA when a device advertising 0xFFE0 is
        detected nearby. Pre-populate discovered_devices and go straight to
        the picker.
        """
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovered_devices[discovery_info.address] = (
            discovery_info.name or discovery_info.address
        )
        return await self.async_step_user()

    async def _async_show_device_picker(
        self, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        # Merge any already-discovered devices with the current scan results
        for info in async_discovered_service_info(self.hass):
            if SERVICE_UUID in (info.service_uuids or []):
                self._discovered_devices.setdefault(
                    info.address, info.name or info.address
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            name = self._discovered_devices.get(address, address)

            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data={CONF_ADDRESS: address, CONF_NAME: name},
            )

        device_choices = {
            address: f"{name} ({address})"
            for address, name in sorted(self._discovered_devices.items())
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(device_choices)}
            ),
            errors=errors,
        )
