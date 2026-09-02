"""Framing tests. No hardware and no Home Assistant needed."""

from __future__ import annotations

import pytest

from flexit_aura.protocol import (
    ERROR_FUNCTION,
    RESPONSE_FUNCTION,
    ParameterValue,
    ProtocolError,
    build_read,
    build_write,
    checksum,
    parse_parameters,
    parse_response,
)

DEVICE_ID = "004B00285746570B"
PASSWORD = "1111"

# FD FD | 02 | 10 + 16 id bytes | 04 + 4 password bytes -> function byte lands here.
FUNCTION_INDEX = 3 + 1 + len(DEVICE_ID) + 1 + len(PASSWORD)

# Captured from the physical unit during the phase 2 read test.
KNOWN_READ_TX = bytes.fromhex(
    "FDFD02103030344230303238353734363537304204313131310"
    "1FF00012F05".replace(" ", "")
)


def test_read_packet_matches_captured_bytes() -> None:
    assert build_read(DEVICE_ID, PASSWORD, [0x01]) == KNOWN_READ_TX


def test_checksum_is_little_endian_sum() -> None:
    assert checksum(b"\x01\x02\x03") == b"\x06\x00"
    assert checksum(bytes([0xFF] * 4)) == b"\xFC\x03"


def test_read_groups_parameters_by_page() -> None:
    packet = build_read(DEVICE_ID, PASSWORD, [0x02, 0x01, 0x0102])
    body = packet[len(KNOWN_READ_TX) - 6 :]
    # Page 0 holds 01 and 02, page 1 holds 02; each page prefix appears once.
    assert body.count(b"\xFF") == 2


def test_read_rejects_empty_parameter_list() -> None:
    with pytest.raises(ValueError):
        build_read(DEVICE_ID, PASSWORD, [])


def test_write_uses_the_verified_page_zero_encoding() -> None:
    packet = build_write(DEVICE_ID, PASSWORD, 0x02, bytes([2]))
    # Function 0x03 followed directly by parameter and value, no FF prefix.
    assert packet[FUNCTION_INDEX : FUNCTION_INDEX + 3] == b"\x03\x02\x02"


def test_write_adds_page_prefix_above_page_zero() -> None:
    packet = build_write(DEVICE_ID, PASSWORD, 0x0102, bytes([7]))
    assert packet[FUNCTION_INDEX : FUNCTION_INDEX + 5] == b"\x03\xFF\x01\x02\x07"


def test_write_rejects_bad_value_length() -> None:
    with pytest.raises(ValueError):
        build_write(DEVICE_ID, PASSWORD, 0x02, b"")


def test_write_packet_parses_back_to_the_same_value() -> None:
    packet = build_write(DEVICE_ID, PASSWORD, 0x02, bytes([3]))
    response = parse_response(packet)
    assert response.checksum_ok
    assert response.device_id == DEVICE_ID
    assert response.parameters[0x02].raw == bytes([3])


def test_parse_single_byte_values() -> None:
    values = parse_parameters(bytes.fromhex("FF000101 0202".replace(" ", "")))
    assert values[0x01].as_int() == 1
    assert values[0x02].as_int() == 2


def test_parse_sized_and_unsupported_markers() -> None:
    # FE 02 4A E8 03 -> parameter 0x4A is two bytes; FD 99 -> 0x99 unsupported.
    values = parse_parameters(bytes.fromhex("FF00FE024AE803FD99"))
    assert values[0x4A].as_int("little") == 1000
    assert values[0x99].raw is None
    assert values[0x99].as_int() is None


def test_parse_carries_the_page_across_parameters() -> None:
    values = parse_parameters(bytes.fromhex("FF010102"))
    assert 0x0101 in values
    assert values[0x0101].as_int() == 2


def test_truncated_value_length_is_rejected() -> None:
    with pytest.raises(ProtocolError):
        parse_parameters(bytes.fromhex("FF00FE0A4AE803"))


def test_short_response_is_rejected() -> None:
    with pytest.raises(ProtocolError):
        parse_response(b"\xFD\xFD\x02\x01")


def test_bad_checksum_is_reported_not_raised() -> None:
    # A read request has no values in it, so build a reply-shaped packet instead.
    packet = bytearray(build_write(DEVICE_ID, PASSWORD, 0x02, bytes([1])))
    packet[-1] ^= 0xFF
    assert parse_response(bytes(packet)).checksum_ok is False


def test_parameter_value_helpers() -> None:
    assert ParameterValue(None).as_int() is None
    assert ParameterValue(b"\xE8\x03").as_int("little") == 1000


def test_captured_reply_uses_the_response_function() -> None:
    # Captured 2026-09-02: a read of 0x01 comes back as function 0x06.
    raw = bytes.fromhex(
        "FDFD0210303034423030323835373436353730420431313131"
        "06FF0001013505"
    )
    response = parse_response(raw)
    assert response.checksum_ok
    assert response.function == RESPONSE_FUNCTION
    assert response.is_error is False
    assert response.parameters[0x01].as_int() == 1


def test_captured_error_frame_is_decoded_not_rejected() -> None:
    # Captured 2026-09-02 with a wrong password: function 0x07, one status byte
    # and no parameter list. Parsing it as parameters used to raise.
    raw = bytes.fromhex(
        "FDFD0210303034423030323835373436353730420439393939"
        "07015604"
    )
    response = parse_response(raw)
    assert response.checksum_ok
    assert response.function == ERROR_FUNCTION
    assert response.is_error is True
    assert response.error_code == 1
    assert response.parameters == {}
