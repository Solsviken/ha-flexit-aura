"""Decoding of raw register values into a typed snapshot.

Deliberately free of Home Assistant imports so it can be unit tested and used
by the standalone diagnostic scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .const import (
    REG_AIR_MODE,
    REG_ALARM,
    REG_BOOST,
    REG_FAN1_RPM,
    REG_FAN2_RPM,
    REG_FILTER_INTERVAL,
    REG_FILTER_REMAINING,
    REG_FILTER_WARNING,
    REG_HUMIDITY,
    REG_HUMIDITY_CONTROL,
    REG_HUMIDITY_LIMIT,
    REG_POWER,
    REG_RUNTIME,
    REG_SPEED,
    REG_TIMER_MODE,
)
from .protocol import ParameterValue


def plain_int(value: ParameterValue | None) -> int | None:
    """Little-endian integer, which is how the unit encodes multi-byte counters."""
    if value is None or value.raw is None:
        return None
    return int.from_bytes(value.raw, "little")


def _duration_parts(raw: bytes) -> tuple[int, int, int] | None:
    """Split a duration register into minutes, hours and days.

    Confirmed against the unit on 2026-09-02: both 0x64 and 0x7E arrive as
    ``minutes, hours, days`` with the days field taking every remaining byte,
    little-endian. The capture ``0x64 = 22 10 58 00`` (88 d 16 h 34 min left of a
    90-day interval) and ``0x7E = 19 07 01 00`` (1 d 7 h 25 min run time) agree
    with each other: 90 - 88.69 days elapsed is the same 31.4 hours.
    """
    if len(raw) < 3:
        return None
    return raw[0], raw[1], int.from_bytes(raw[2:], "little")


def countdown_days(value: ParameterValue | None) -> float | None:
    """Filter countdown expressed in days."""
    if value is None or value.raw is None:
        return None
    parts = _duration_parts(value.raw)
    if parts is None:
        # Shorter than expected: fall back to a plain counter rather than guess.
        return float(int.from_bytes(value.raw, "little"))
    minutes, hours, days = parts
    return round(days + hours / 24 + minutes / 1440, 2)


def runtime_hours(value: ParameterValue | None) -> float | None:
    """Operating time expressed in hours."""
    if value is None or value.raw is None:
        return None
    parts = _duration_parts(value.raw)
    if parts is None:
        return float(int.from_bytes(value.raw, "little"))
    minutes, hours, days = parts
    return round(days * 24 + hours + minutes / 60, 2)


@dataclass
class FlexitAuraData:
    """Decoded snapshot of one poll."""

    power: int | None = None
    speed: int | None = None
    boost: int | None = None
    timer_mode: int | None = None
    humidity_control: int | None = None
    humidity_limit: int | None = None
    humidity: int | None = None
    fan1_rpm: int | None = None
    fan2_rpm: int | None = None
    filter_interval_days: int | None = None
    filter_remaining_days: float | None = None
    runtime_hours: float | None = None
    alarm: int | None = None
    filter_warning: int | None = None
    air_mode: int | None = None
    raw: dict[str, str | None] = field(default_factory=dict)

    @classmethod
    def from_parameters(cls, values: dict[int, ParameterValue]) -> FlexitAuraData:
        return cls(
            power=plain_int(values.get(REG_POWER)),
            speed=plain_int(values.get(REG_SPEED)),
            boost=plain_int(values.get(REG_BOOST)),
            timer_mode=plain_int(values.get(REG_TIMER_MODE)),
            humidity_control=plain_int(values.get(REG_HUMIDITY_CONTROL)),
            humidity_limit=plain_int(values.get(REG_HUMIDITY_LIMIT)),
            humidity=plain_int(values.get(REG_HUMIDITY)),
            fan1_rpm=plain_int(values.get(REG_FAN1_RPM)),
            fan2_rpm=plain_int(values.get(REG_FAN2_RPM)),
            filter_interval_days=plain_int(values.get(REG_FILTER_INTERVAL)),
            filter_remaining_days=countdown_days(values.get(REG_FILTER_REMAINING)),
            runtime_hours=runtime_hours(values.get(REG_RUNTIME)),
            alarm=plain_int(values.get(REG_ALARM)),
            filter_warning=plain_int(values.get(REG_FILTER_WARNING)),
            air_mode=plain_int(values.get(REG_AIR_MODE)),
            # Kept so diagnostics can show exactly what the unit returned.
            raw={
                f"0x{register:02X}": None if value.raw is None else value.raw.hex().upper()
                for register, value in sorted(values.items())
            },
        )
