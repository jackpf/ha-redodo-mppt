"""Constants for the Redodo MPPT integration."""

DOMAIN = "redodo_mppt"

# BLE service UUID used to identify the device during scanning
SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"

# Config entry keys
CONF_ADDRESS = "address"
CONF_NAME = "name"

# Coordinator poll interval (seconds)
DEFAULT_POLL_INTERVAL = 30

# How many consecutive errors before the coordinator marks the device unavailable
MAX_ERRORS_BEFORE_UNAVAILABLE = 3
