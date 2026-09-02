"""Pure framing and parsing for the Flexit Aura (Blauberg/VENTS 0x1B00) UDP protocol.

This module performs no I/O so it can be unit tested without hardware.
Frame layout::

    FD FD | 02 | len+device_id (ASCII) | len+password (ASCII) | function | data | checksum

The checksum is the 16-bit sum of every byte after the header, little-endian.
"""

from __future__ import annotations

from dataclasses import dataclass

HEADER = b"\xFD\xFD"
PROTOCOL_TYPE = 0x02
DEFAULT_PORT = 4000

# Request functions.
READ_FUNCTION = 0x01
WRITE_AND_RETURN_FUNCTION = 0x03
# Reply functions, observed on the unit 2026-09-02: a read answered with 0x01 in
# the request comes back as 0x06, and a rejected password comes back as 0x07
# with a single error byte instead of a parameter list.
RESPONSE_FUNCTION = 0x06
ERROR_FUNCTION = 0x07

# 16-character wildcard that some units in this family accept instead of the
# real device ID. The Aura 160 tested here answers neither unicast nor broadcast
# wildcard reads, so discovery is not available and the ID must be entered.
WILDCARD_DEVICE_ID = "DEFAULT_DEVICEID"

# Data-block markers.
MARKER_PAGE = 0xFF
MARKER_INVALID = 0xFD
MARKER_SIZED = 0xFE


class ProtocolError(RuntimeError):
    """Raised when a device response cannot be trusted or decoded."""


@dataclass(frozen=True)
class ParameterValue:
    """One parameter as returned by the device. ``raw`` is None when unsupported."""

    raw: bytes | None

    def as_int(self, byteorder: str = "big") -> int | None:
        return None if self.raw is None else int.from_bytes(self.raw, byteorder)


@dataclass(frozen=True)
class Response:
    raw: bytes
    device_id: str
    function: int
    parameters: dict[int, ParameterValue]
    checksum_ok: bool
    error_code: int | None = None

    @property
    def is_error(self) -> bool:
        return self.function == ERROR_FUNCTION


def checksum(body: bytes) -> bytes:
    return (sum(body) & 0xFFFF).to_bytes(2, "little")


def _dynamic(value: bytes) -> bytes:
    if len(value) > 255:
        raise ValueError("Dynamisk felt er for langt")
    return bytes([len(value)]) + value


def _envelope(device_id: str, password: str, function: int, data: bytes) -> bytes:
    body = (
        bytes([PROTOCOL_TYPE])
        + _dynamic(device_id.encode("ascii"))
        + _dynamic(password.encode("ascii"))
        + bytes([function])
        + data
    )
    return HEADER + body + checksum(body)


def _parameter_block(parameters: list[int]) -> bytes:
    """Group parameters by high byte so each page prefix is only sent once."""
    groups: dict[int, list[int]] = {}
    for parameter in sorted(set(parameters)):
        if not 0 <= parameter <= 0xFFFF:
            raise ValueError(f"Ugyldig parameter: {parameter}")
        groups.setdefault(parameter >> 8, []).append(parameter & 0xFF)
    result = bytearray()
    for page, tails in groups.items():
        result.extend((MARKER_PAGE, page, *tails))
    return bytes(result)


def build_read(device_id: str, password: str, parameters: list[int]) -> bytes:
    if not parameters:
        raise ValueError("Minst én parameter må oppgis")
    return _envelope(device_id, password, READ_FUNCTION, _parameter_block(parameters))


def build_write(device_id: str, password: str, parameter: int, value: bytes) -> bytes:
    """Build one write-and-return packet. Policy validation belongs in the client."""
    if not 0 <= parameter <= 0xFFFF:
        raise ValueError(f"Ugyldig parameter: {parameter}")
    if not value or len(value) > 255:
        raise ValueError("Skriveverdien har ugyldig lengde")
    encoded = bytearray()
    # Page 0 is the device default. The physically verified speed write carried no
    # page prefix, so keep that exact encoding and only emit FF for other pages.
    if parameter > 0xFF:
        encoded += bytes([MARKER_PAGE, parameter >> 8])
    if len(value) == 1:
        encoded += bytes([parameter & 0xFF]) + value
    else:
        encoded += bytes([MARKER_SIZED, len(value), parameter & 0xFF]) + value
    return _envelope(device_id, password, WRITE_AND_RETURN_FUNCTION, bytes(encoded))


def parse_parameters(data: bytes) -> dict[int, ParameterValue]:
    values: dict[int, ParameterValue] = {}
    page = 0
    index = 0
    while index < len(data):
        marker = data[index]
        index += 1
        if marker == MARKER_PAGE:
            if index >= len(data):
                raise ProtocolError("Avkortet FF-parametergruppe")
            page = data[index]
            index += 1
        elif marker == MARKER_INVALID:
            if index >= len(data):
                raise ProtocolError("Avkortet FD-parameter")
            values[(page << 8) | data[index]] = ParameterValue(None)
            index += 1
        elif marker == MARKER_SIZED:
            if index + 2 > len(data):
                raise ProtocolError("Avkortet FE-parameter")
            length, tail = data[index], data[index + 1]
            index += 2
            if index + length > len(data):
                raise ProtocolError("Oppgitt verdi-lengde går utenfor UDP-pakken")
            values[(page << 8) | tail] = ParameterValue(data[index : index + length])
            index += length
        else:
            if index >= len(data):
                raise ProtocolError("Parameter mangler verdi")
            values[(page << 8) | marker] = ParameterValue(data[index : index + 1])
            index += 1
    return values


def parse_response(raw: bytes) -> Response:
    if len(raw) < 10 or raw[:2] != HEADER or raw[2] != PROTOCOL_TYPE:
        raise ProtocolError("Svaret har ukjent eller avkortet header")
    index = 3
    id_length = raw[index]
    index += 1
    if index + id_length + 1 > len(raw) - 2:
        raise ProtocolError("Avkortet Device ID-felt")
    device_id_raw = raw[index : index + id_length]
    index += id_length
    password_length = raw[index]
    index += 1
    if index + password_length + 1 > len(raw) - 2:
        raise ProtocolError("Avkortet passordfelt")
    index += password_length
    function = raw[index]
    data = raw[index + 1 : -2]
    try:
        device_id = device_id_raw.decode("ascii")
    except UnicodeDecodeError:
        device_id = device_id_raw.hex().upper()
    checksum_ok = raw[-2:] == checksum(raw[2:-2])
    if function == ERROR_FUNCTION:
        # An error frame carries a status byte, not a parameter list, so parsing
        # it as parameters would fail on a value that is not there.
        return Response(
            raw=raw,
            device_id=device_id,
            function=function,
            parameters={},
            checksum_ok=checksum_ok,
            error_code=data[0] if data else None,
        )
    return Response(
        raw=raw,
        device_id=device_id,
        function=function,
        parameters=parse_parameters(data),
        checksum_ok=checksum_ok,
    )
