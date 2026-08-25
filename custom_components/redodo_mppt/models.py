"""Dataclasses representing data returned by the Redodo MPPT controller."""

from dataclasses import dataclass, field


@dataclass
class DeviceInfo:
    """Static device identity read once on first connect."""

    model: str = ""
    hw_version: int = 0
    fw_version: int = 0
    rated_current: int | None = None
    rated_power: int | None = None


@dataclass
class MPPTData:
    """
    Snapshot of controller sensor readings from one poll cycle.

    Fields marked with None are populated only when the relevant register
    block has been successfully read. Unconfirmed fields (PV, energy, etc.)
    remain None until outdoor verification is complete — see registers.py.
    """

    # --- Confirmed ---
    soc: int | None = None             # Battery state of charge (%)
    battery_voltage: float | None = None  # V (÷10 from raw register)

    # --- Unconfirmed: set when POLL_REALTIME succeeds, values uncertain ---
    pv_voltage: float | None = None    # V  (TODO: confirm REG_PV_VOLTAGE)
    pv_current: float | None = None    # A  (TODO: confirm REG_PV_CURRENT)
    battery_temp: int | None = None      # raw (TODO: confirm unit — Wh?)
    today_energy: int | None = None    # raw (TODO: confirm unit — Wh?)
    total_ah: int | None = None        # raw (TODO: confirm unit)
    total_discharge: int | None = None     # raw

    # --- Config (populated from POLL_CONFIG, static) ---
    absorption_voltage: float | None = None
    float_voltage: float | None = None
    max_charge_current: int | None = None

    def is_valid(self) -> bool:
        """True if the minimum confirmed fields are present."""
        return self.soc is not None and self.battery_voltage is not None
