"""Dataclasses representing data returned by the Redodo MPPT controller."""

from dataclasses import dataclass


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

    Fields are None until the relevant poll block has been successfully read.

    Live readings — populated each cycle from POLL_REALTIME:
      soc, battery_voltage, charge_current, charge_power, battery_temp_f,
      pv_voltage, charge_max_power, daily_charge_wh, days_on,
      total_charge_wh, total_discharge_wh

    Daily stats — populated each cycle from POLL_EXTRA:
      daily_discharge_wh, daily_batt_v_high, daily_batt_v_low

    Config — populated once from POLL_CONFIG:
      absorption_voltage, float_voltage, max_charge_current
    """

    # --- Live: confirmed ---
    soc: int | None = None                  # Battery state of charge (%)
    battery_voltage: float | None = None    # V (÷10)
    charge_current: float | None = None     # A (÷100)
    charge_power: int | None = None         # W
    battery_temp_f: float | None = None     # °F (÷100)
    pv_voltage: float | None = None         # V (÷10)

    # --- Daily stats: from primary block ---
    charge_max_power: int | None = None     # W, daily peak charge power
    daily_charge_wh: int | None = None      # Wh charged today

    # --- Daily stats: from extra block only ---
    daily_discharge_wh: int | None = None   # Wh discharged today
    daily_batt_v_high: float | None = None  # V (÷10), highest today
    daily_batt_v_low: float | None = None   # V (÷10), lowest today

    # --- Cumulative: from primary block ---
    days_on: int | None = None              # days controller has been on
    total_charge_wh: int | None = None      # Wh charged lifetime
    total_discharge_wh: int | None = None   # Wh discharged lifetime

    # --- Config: from POLL_CONFIG (static) ---
    absorption_voltage: float | None = None
    float_voltage: float | None = None
    max_charge_current: int | None = None

    def is_valid(self) -> bool:
        """True if the minimum confirmed fields are present."""
        return self.soc is not None and self.battery_voltage is not None
