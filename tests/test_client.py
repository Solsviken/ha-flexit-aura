"""Client tests against a fake unit on localhost. No hardware needed."""

from __future__ import annotations

import asyncio

import pytest

from flexit_aura import client as client_module
from flexit_aura.client import (
    AuraAuthError,
    AuraClient,
    AuraConnectionError,
    AuraResponseError,
    AuraWriteError,
)
from flexit_aura.protocol import (
    ERROR_FUNCTION,
    HEADER,
    MARKER_PAGE,
    RESPONSE_FUNCTION,
    WRITE_AND_RETURN_FUNCTION,
    checksum,
)

DEVICE_ID = "004B00285746570B"
PASSWORD = "1111"


def _parse_request(raw: bytes) -> tuple[str, int, list[tuple[int, int | None]]]:
    """Minimal request decoder, mirroring what the real unit has to do."""
    index = 3
    id_length = raw[index]
    index += 1
    device_id = raw[index : index + id_length].decode("ascii")
    index += id_length
    index += 1 + raw[index]
    function = raw[index]
    data = raw[index + 1 : -2]

    items: list[tuple[int, int | None]] = []
    page = 0
    cursor = 0
    while cursor < len(data):
        marker = data[cursor]
        cursor += 1
        if marker == MARKER_PAGE:
            page = data[cursor]
            cursor += 1
            continue
        register = (page << 8) | marker
        if function == WRITE_AND_RETURN_FUNCTION:
            items.append((register, data[cursor]))
            cursor += 1
        else:
            items.append((register, None))
    return device_id, function, items


class FakeUnit(asyncio.DatagramProtocol):
    """Answers like the ventilation unit, with switchable misbehaviour."""

    def __init__(self, registers: dict[int, int]) -> None:
        self.registers = registers
        self.ignore_writes = False
        self.corrupt_checksum = False
        self.answer_as: str | None = None
        self.silent = False
        self.reject_password = False
        self.transport: asyncio.DatagramTransport | None = None
        self.received = 0

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        self.received += 1
        if self.silent:
            return
        device_id, function, items = _parse_request(data)

        if self.reject_password:
            # What the real unit sends for a bad password: function 0x07 and a
            # single status byte where the parameter list would be.
            reply_function = ERROR_FUNCTION
            payload = bytearray([0x01])
        else:
            reply_function = RESPONSE_FUNCTION
            payload = bytearray([MARKER_PAGE, 0x00])
            for register, value in items:
                if function == WRITE_AND_RETURN_FUNCTION and not self.ignore_writes:
                    self.registers[register] = value
                payload += bytes([register & 0xFF, self.registers.get(register, 0)])

        answer_id = self.answer_as or device_id
        body = (
            bytes([0x02])
            + bytes([len(answer_id)])
            + answer_id.encode("ascii")
            + bytes([len(PASSWORD)])
            + PASSWORD.encode("ascii")
            + bytes([reply_function])
            + bytes(payload)
        )
        packet = bytearray(HEADER + body + checksum(body))
        if self.corrupt_checksum:
            packet[-1] ^= 0xFF
        assert self.transport is not None
        self.transport.sendto(bytes(packet), addr)


@pytest.fixture(autouse=True)
def _no_verify_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """The half-second settle time is real-hardware behaviour, not test behaviour."""
    monkeypatch.setattr(client_module, "VERIFY_DELAY", 0)


@pytest.fixture
async def unit() -> FakeUnit:
    loop = asyncio.get_running_loop()
    registers = {0x01: 1, 0x02: 2, 0x25: 41, 0xB7: 1}
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: FakeUnit(registers), local_addr=("127.0.0.1", 0)
    )
    protocol.port = transport.get_extra_info("sockname")[1]
    try:
        yield protocol
    finally:
        transport.close()


def _client(unit: FakeUnit, device_id: str = DEVICE_ID, **kwargs) -> AuraClient:
    return AuraClient(
        host="127.0.0.1",
        device_id=device_id,
        password=PASSWORD,
        port=unit.port,
        **kwargs,
    )


async def test_read_returns_decoded_registers(unit: FakeUnit) -> None:
    values = await _client(unit).async_read([0x01, 0x02, 0x25])
    assert values[0x02].as_int() == 2
    assert values[0x25].as_int() == 41


async def test_write_applies_and_verifies(unit: FakeUnit) -> None:
    assert await _client(unit).async_write(0x02, 3) == 3
    assert unit.registers[0x02] == 3


async def test_write_rejects_register_outside_the_allowlist(unit: FakeUnit) -> None:
    with pytest.raises(ValueError):
        await _client(unit).async_write(0x25, 50)
    assert unit.received == 0


async def test_write_rejects_value_outside_the_allowlist(unit: FakeUnit) -> None:
    with pytest.raises(ValueError):
        await _client(unit).async_write(0x02, 9)
    assert unit.received == 0


async def test_write_fails_when_read_back_never_confirms(unit: FakeUnit) -> None:
    unit.ignore_writes = True
    with pytest.raises(AuraWriteError):
        await _client(unit).async_write(0x02, 3)
    assert unit.registers[0x02] == 2


async def test_write_survives_a_lost_acknowledgement(unit: FakeUnit) -> None:
    """A late or dropped write reply must not hide a write that did land."""
    original_handler = unit.datagram_received
    state = {"first": True}

    def drop_first_reply(data: bytes, addr: tuple) -> None:
        if state["first"]:
            state["first"] = False
            _, _, items = _parse_request(data)
            for register, value in items:
                unit.registers[register] = value
            unit.received += 1
            return
        original_handler(data, addr)

    unit.datagram_received = drop_first_reply  # type: ignore[method-assign]
    client = _client(unit, timeout=0.2)
    assert await client.async_write(0x02, 3) == 3


async def test_timeout_raises_connection_error(unit: FakeUnit) -> None:
    unit.silent = True
    with pytest.raises(AuraConnectionError):
        await _client(unit, timeout=0.2).async_read([0x01])


async def test_bad_checksum_raises_response_error(unit: FakeUnit) -> None:
    unit.corrupt_checksum = True
    with pytest.raises(AuraResponseError):
        await _client(unit).async_read([0x01])


async def test_answer_from_another_device_is_rejected(unit: FakeUnit) -> None:
    unit.answer_as = "FFFFFFFFFFFFFFFF"
    with pytest.raises(AuraResponseError):
        await _client(unit).async_read([0x01])


async def test_rejected_password_raises_auth_error(unit: FakeUnit) -> None:
    unit.reject_password = True
    with pytest.raises(AuraAuthError):
        await _client(unit).async_read([0x01])


async def test_rejected_password_is_not_retried(unit: FakeUnit) -> None:
    unit.reject_password = True
    with pytest.raises(AuraAuthError):
        await _client(unit).async_read([0x01])
    assert unit.received == 1


async def test_rejected_password_fails_a_write_immediately(unit: FakeUnit) -> None:
    unit.reject_password = True
    with pytest.raises(AuraAuthError):
        await _client(unit).async_write(0x02, 3)
    assert unit.received == 1
