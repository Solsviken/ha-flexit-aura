"""Constants and the register map for the Flexit Aura integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "flexit_aura"

CONF_DEVICE_ID: Final = "device_id"

DEFAULT_PASSWORD: Final = "1111"
DEFAULT_PORT: Final = 4000
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
DEFAULT_TIMEOUT: Final = 2.0

# Polls that may fail in a row before the entities are reported unavailable.
# UDP over Wi-Fi drops the odd datagram; one missed poll is not the unit gone.
MAX_CONSECUTIVE_FAILURES: Final = 3

MANUFACTURER: Final = "Flexit"
MODEL: Final = "Aura 160"

# --- Registers -------------------------------------------------------------
# Only registers that have been read from the physical unit are listed. Writes
# are restricted to the allowlist in WRITABLE below.
REG_POWER: Final = 0x01
REG_SPEED: Final = 0x02
REG_BOOST: Final = 0x06
REG_TIMER_MODE: Final = 0x07
REG_HUMIDITY_CONTROL: Final = 0x0F
REG_HUMIDITY_LIMIT: Final = 0x19
REG_HUMIDITY: Final = 0x25
REG_FAN1_RPM: Final = 0x4A
REG_FAN2_RPM: Final = 0x4B
REG_FILTER_INTERVAL: Final = 0x63
REG_FILTER_REMAINING: Final = 0x64
REG_RUNTIME: Final = 0x7E
REG_ALARM: Final = 0x83
REG_FILTER_WARNING: Final = 0x88
REG_AIR_MODE: Final = 0xB7

# Read in a single datagram on every poll.
POLL_REGISTERS: Final[list[int]] = [
    REG_POWER,
    REG_SPEED,
    REG_BOOST,
    REG_TIMER_MODE,
    REG_HUMIDITY_CONTROL,
    REG_HUMIDITY_LIMIT,
    REG_HUMIDITY,
    REG_FAN1_RPM,
    REG_FAN2_RPM,
    REG_FILTER_INTERVAL,
    REG_FILTER_REMAINING,
    REG_RUNTIME,
    REG_ALARM,
    REG_FILTER_WARNING,
    REG_AIR_MODE,
]

# Write allowlist: register -> accepted values. Anything else is rejected before
# a packet is built, so an unverified register can never be written by accident.
WRITABLE: Final[dict[int, frozenset[int]]] = {
    REG_POWER: frozenset({0, 1}),
    REG_SPEED: frozenset({1, 2, 3}),
    REG_AIR_MODE: frozenset({0, 1, 2}),
}

# --- Enumerations ----------------------------------------------------------
SPEED_STANDBY: Final = 0
SPEED_LOW: Final = 1
SPEED_MEDIUM: Final = 2
SPEED_HIGH: Final = 3
SPEED_MANUAL: Final = 255

ORDERED_SPEEDS: Final[list[int]] = [SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

AIR_MODE_VENTILATION: Final = 0
AIR_MODE_HEAT_RECOVERY: Final = 1
AIR_MODE_SUPPLY: Final = 2

AIR_MODES: Final[dict[int, str]] = {
    AIR_MODE_VENTILATION: "ventilation",
    AIR_MODE_HEAT_RECOVERY: "heat_recovery",
    AIR_MODE_SUPPLY: "supply",
}
AIR_MODE_VALUES: Final[dict[str, int]] = {name: value for value, name in AIR_MODES.items()}

TIMER_MODES: Final[dict[int, str]] = {0: "off", 1: "night", 2: "party"}
