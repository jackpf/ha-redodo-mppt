"""Sensor entities for the Redodo MPPT integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RedodoCoordinator


@dataclass(frozen=True, kw_only=True)
class RedodoSensorDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with a value extractor."""

    value_fn: Any = None  # Callable[[MPPTData], float | int | None]


SENSOR_DESCRIPTIONS: tuple[RedodoSensorDescription, ...] = (
    # --- Live readings ---
    RedodoSensorDescription(
        key="battery_soc",
        name="Battery SOC",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d.soc,
    ),
    RedodoSensorDescription(
        key="battery_voltage",
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda d: d.battery_voltage,
    ),
    RedodoSensorDescription(
        key="pv_voltage",
        name="PV Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda d: d.pv_voltage,
    ),
    RedodoSensorDescription(
        key="charge_current",
        name="Charge Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=2,
        value_fn=lambda d: d.charge_current,
    ),
    RedodoSensorDescription(
        key="charge_power",
        name="Charge Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.charge_power,
    ),
    RedodoSensorDescription(
        key="battery_temp",
        name="Battery Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        suggested_display_precision=1,
        value_fn=lambda d: d.battery_temp_f,
    ),
    # --- Daily stats ---
    RedodoSensorDescription(
        key="daily_charge_wh",
        name="Daily Charge",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda d: d.daily_charge_wh,
    ),
    RedodoSensorDescription(
        key="daily_discharge_wh",
        name="Daily Discharge",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda d: d.daily_discharge_wh,
    ),
    RedodoSensorDescription(
        key="charge_max_power",
        name="Daily Peak Charge Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d.charge_max_power,
    ),
    RedodoSensorDescription(
        key="daily_batt_v_high",
        name="Daily High Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda d: d.daily_batt_v_high,
    ),
    RedodoSensorDescription(
        key="daily_batt_v_low",
        name="Daily Low Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda d: d.daily_batt_v_low,
    ),
    # --- Cumulative ---
    RedodoSensorDescription(
        key="total_charge_wh",
        name="Total Charge",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda d: d.total_charge_wh,
    ),
    RedodoSensorDescription(
        key="total_discharge_wh",
        name="Total Discharge",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda d: d.total_discharge_wh,
    ),
    RedodoSensorDescription(
        key="days_on",
        name="Days On",
        device_class=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda d: d.days_on,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RedodoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        RedodoSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class RedodoSensor(CoordinatorEntity[RedodoCoordinator], SensorEntity):
    """A single sensor entity backed by the RedodoCoordinator."""

    entity_description: RedodoSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RedodoCoordinator,
        entry: ConfigEntry,
        description: RedodoSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        dev = self.coordinator.device_info
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.unique_id)},
            name=self._entry.title,
            manufacturer="Redodo",
            model=dev.model if dev else None,
            sw_version=str(dev.fw_version) if dev else None,
            hw_version=str(dev.hw_version) if dev else None,
        )

    @property
    def native_value(self) -> float | int | None:
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
