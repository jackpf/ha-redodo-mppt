"""Dataclasses representing data returned by the Redodo MPPT controller."""

from dataclasses import dataclass


@dataclass
class DeviceInfo:
    """Static device identity read once on first connect."""

    model: str
    hw_version: int
    fw_version: int


@dataclass
class RealtimeData:
    """Live sensor readings from the primary POLL_REALTIME block (0x0101)."""

    soc: int
    battery_voltage: float  # V (÷10)
    charge_current: float  # A (÷100)
    charge_power: int  # W
    battery_temp_f: float  # °F (÷100)
    pv_voltage: float  # V (÷10)
    charge_max_power: int  # W, daily peak
    daily_charge_wh: int  # Wh charged today
    days_on: int  # days controller has been on
    total_charge_wh: int  # Wh charged lifetime
    total_discharge_wh: int  # Wh discharged lifetime


@dataclass
class ExtraData:
    """Supplemental daily stats from the POLL_EXTRA block (0x0400)."""

    daily_discharge_wh: int  # Wh discharged today
    daily_batt_v_high: float  # V (÷10), highest today
    daily_batt_v_low: float  # V (÷10), lowest today


@dataclass
class ConfigData:
    """Static configuration registers from the POLL_CONFIG block (0x0201)."""

    absorption_voltage: float  # V (÷10)
    float_voltage: float  # V (÷10)
    max_charge_current: int  # A


@dataclass
class MPPTData:
    """
    Flat snapshot of all available controller data from one poll cycle.

    All fields are None until the relevant poll block has been successfully
    read. Construct via MPPTData.from_blocks() rather than directly.
    """

    # --- From RealtimeData ---
    soc: int | None = None
    battery_voltage: float | None = None
    charge_current: float | None = None
    charge_power: int | None = None
    battery_temp_f: float | None = None
    pv_voltage: float | None = None
    charge_max_power: int | None = None
    daily_charge_wh: int | None = None
    days_on: int | None = None
    total_charge_wh: int | None = None
    total_discharge_wh: int | None = None

    # --- From ExtraData ---
    daily_discharge_wh: int | None = None
    daily_batt_v_high: float | None = None
    daily_batt_v_low: float | None = None

    # --- From ConfigData ---
    absorption_voltage: float | None = None
    float_voltage: float | None = None
    max_charge_current: int | None = None

    @classmethod
    def from_blocks(
        cls,
        realtime: RealtimeData | None,
        extra: ExtraData | None = None,
        config: ConfigData | None = None,
    ) -> "MPPTData":
        """Assemble a flat MPPTData from individually parsed poll blocks."""
        return cls(
            soc=realtime.soc if realtime else None,
            battery_voltage=realtime.battery_voltage if realtime else None,
            charge_current=realtime.charge_current if realtime else None,
            charge_power=realtime.charge_power if realtime else None,
            battery_temp_f=realtime.battery_temp_f if realtime else None,
            pv_voltage=realtime.pv_voltage if realtime else None,
            charge_max_power=realtime.charge_max_power if realtime else None,
            daily_charge_wh=realtime.daily_charge_wh if realtime else None,
            days_on=realtime.days_on if realtime else None,
            total_charge_wh=realtime.total_charge_wh if realtime else None,
            total_discharge_wh=realtime.total_discharge_wh if realtime else None,
            daily_discharge_wh=extra.daily_discharge_wh if extra else None,
            daily_batt_v_high=extra.daily_batt_v_high if extra else None,
            daily_batt_v_low=extra.daily_batt_v_low if extra else None,
            absorption_voltage=config.absorption_voltage if config else None,
            float_voltage=config.float_voltage if config else None,
            max_charge_current=config.max_charge_current if config else None,
        )
