"""Decoding tests for the register snapshot.

The duration cases use bytes captured from the physical unit on 2026-09-02.
"""

from __future__ import annotations

from flexit_aura.model import FlexitAuraData, countdown_days, plain_int, runtime_hours
from flexit_aura.protocol import ParameterValue


def test_missing_and_unsupported_values_decode_to_none() -> None:
    assert plain_int(None) is None
    assert plain_int(ParameterValue(None)) is None
    assert countdown_days(ParameterValue(None)) is None
    assert runtime_hours(None) is None


def test_multi_byte_counters_are_little_endian() -> None:
    assert plain_int(ParameterValue(b"\x0C\x03")) == 780


def test_filter_countdown_from_captured_bytes() -> None:
    # 0x64 = 22 10 58 00 -> 34 minutes, 16 hours, 88 days.
    assert countdown_days(ParameterValue(bytes.fromhex("22105800"))) == 88.69


def test_runtime_from_captured_bytes() -> None:
    # 0x7E = 19 07 01 00 -> 25 minutes, 7 hours, 1 day.
    assert runtime_hours(ParameterValue(bytes.fromhex("19070100"))) == 31.42


def test_captured_durations_agree_with_each_other() -> None:
    """90-day filter interval minus the countdown must equal the run time."""
    remaining = countdown_days(ParameterValue(bytes.fromhex("22105800")))
    elapsed_hours = runtime_hours(ParameterValue(bytes.fromhex("19070100")))
    assert abs((90 - remaining) * 24 - elapsed_hours) < 0.5


def test_three_byte_durations_still_decode() -> None:
    assert countdown_days(ParameterValue(bytes([30, 12, 89]))) == 89.52
    assert runtime_hours(ParameterValue(bytes([30, 12, 2]))) == 60.5


def test_short_durations_fall_back_to_a_plain_counter() -> None:
    assert countdown_days(ParameterValue(b"\x00")) == 0.0
    assert runtime_hours(ParameterValue(b"\x2A")) == 42.0


def test_snapshot_keeps_raw_hex_for_every_register() -> None:
    values = {
        0x01: ParameterValue(b"\x01"),
        0x02: ParameterValue(b"\x02"),
        0x25: ParameterValue(bytes([41])),
        0x4A: ParameterValue(b"\x0C\x03"),
        0x99: ParameterValue(None),
    }
    data = FlexitAuraData.from_parameters(values)
    assert data.power == 1
    assert data.speed == 2
    assert data.humidity == 41
    assert data.fan1_rpm == 780
    assert data.raw["0x4A"] == "0C03"
    assert data.raw["0x99"] is None
    # Registers the unit did not return stay None rather than defaulting to 0.
    assert data.air_mode is None
