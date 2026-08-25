"""Redodo MPPT Charge Controller integration."""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

# HA imports are deferred to inside the async functions so that this package
# can be imported from cli.py without homeassistant being installed.


async def async_setup_entry(hass, entry) -> bool:
    """Set up Redodo MPPT from a config entry."""
    from homeassistant.const import Platform

    from .const import CONF_ADDRESS, DOMAIN
    from .coordinator import RedodoCoordinator

    address: str = entry.data[CONF_ADDRESS]
    coordinator = RedodoCoordinator(hass, address)

    # Raises ConfigEntryNotReady on failure so HA retries automatically.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass, entry) -> bool:
    """Unload a config entry."""
    from homeassistant.const import Platform

    from .const import DOMAIN
    from .coordinator import RedodoCoordinator

    unloaded = await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR]
    )

    if unloaded:
        coordinator: RedodoCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unloaded
