"""Asynchronous UDP client for the Flexit Aura ventilation unit."""

from __future__ import annotations

import asyncio
import logging

from .const import DEFAULT_PORT, DEFAULT_TIMEOUT, WRITABLE
from .protocol import (
    ParameterValue,
    ProtocolError,
    Response,
    build_read,
    build_write,
    parse_response,
)

_LOGGER = logging.getLogger(__name__)

# The unit needs a short pause after a write before the new value reads back.
VERIFY_DELAY = 0.5
VERIFY_ATTEMPTS = 3
READ_ATTEMPTS = 2


class AuraError(Exception):
    """Base error for all client failures."""


class AuraConnectionError(AuraError):
    """The unit did not answer."""


class AuraResponseError(AuraError):
    """The unit answered with something we cannot trust."""


class AuraAuthError(AuraError):
    """The unit rejected the password (reply function 0x07)."""


class AuraWriteError(AuraError):
    """A write was sent but the read-back never confirmed it."""


class _DatagramHandler(asyncio.DatagramProtocol):
    """Resolves a future with the first datagram that arrives."""

    def __init__(self, future: asyncio.Future[bytes]) -> None:
        self._future = future

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if not self._future.done():
            self._future.set_result(data)

    def error_received(self, exc: Exception) -> None:
        if not self._future.done():
            self._future.set_exception(exc)


class AuraClient:
    """Talks to one unit. Every exchange is serialised by a lock.

    UDP has no request identifier, so two overlapping exchanges could pick up
    each other's replies. The lock makes that impossible.
    """

    def __init__(
        self,
        host: str,
        device_id: str,
        password: str,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.host = host
        self.port = port
        self.device_id = device_id
        self.password = password
        self.timeout = timeout
        self._lock = asyncio.Lock()

    async def _send(self, packet: bytes) -> bytes:
        """One datagram out, one datagram in. Raises AuraConnectionError on timeout."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()
        try:
            transport, _ = await loop.create_datagram_endpoint(
                lambda: _DatagramHandler(future),
                remote_addr=(self.host, self.port),
            )
        except OSError as err:
            raise AuraConnectionError(f"Kunne ikke åpne UDP-socket: {err}") from err
        try:
            transport.sendto(packet)
            return await asyncio.wait_for(future, self.timeout)
        except TimeoutError as err:
            raise AuraConnectionError(
                f"Ingen svar fra {self.host}:{self.port} innen {self.timeout} s"
            ) from err
        except OSError as err:
            raise AuraConnectionError(f"Nettverksfeil mot {self.host}: {err}") from err
        finally:
            transport.close()

    def _validate(self, raw: bytes) -> Response:
        try:
            response = parse_response(raw)
        except ProtocolError as err:
            raise AuraResponseError(str(err)) from err
        if not response.checksum_ok:
            raise AuraResponseError("Checksum-feil i svar fra viften")
        if response.is_error:
            raise AuraAuthError(
                f"Viften avviste forespørselen (feilkode {response.error_code}). "
                "Kontroller passordet."
            )
        if response.device_id != self.device_id:
            raise AuraResponseError(
                f"Svar fra uventet Device ID: {response.device_id}"
            )
        return response

    async def _exchange(self, packet: bytes) -> Response:
        last_error: AuraError | None = None
        for attempt in range(READ_ATTEMPTS):
            try:
                raw = await self._send(packet)
                return self._validate(raw)
            except AuraAuthError:
                # A rejected password will be rejected again; do not retry.
                raise
            except AuraError as err:
                last_error = err
                _LOGGER.debug(
                    "Forsøk %s/%s mot %s feilet: %s",
                    attempt + 1,
                    READ_ATTEMPTS,
                    self.host,
                    err,
                )
        assert last_error is not None
        raise last_error

    async def async_read(self, registers: list[int]) -> dict[int, ParameterValue]:
        """Read every register in a single datagram."""
        packet = build_read(self.device_id, self.password, registers)
        async with self._lock:
            response = await self._exchange(packet)
        return response.parameters

    async def async_write(self, register: int, value: int) -> int:
        """Write one allowlisted register and confirm it with a read-back.

        The unit sometimes applies a write but acknowledges it late, so a
        timeout on the write itself is not treated as a failure until the
        read-back has also failed.
        """
        allowed = WRITABLE.get(register)
        if allowed is None:
            raise ValueError(f"Register 0x{register:02X} er ikke skrivbart")
        if value not in allowed:
            raise ValueError(
                f"Verdi {value} er ikke tillatt for register 0x{register:02X}"
            )

        write_packet = build_write(self.device_id, self.password, register, bytes([value]))
        verify_packet = build_read(self.device_id, self.password, [register])
        expected = bytes([value])

        async with self._lock:
            try:
                await self._exchange(write_packet)
            except AuraAuthError:
                # Nothing to verify: the unit never accepted the packet.
                raise
            except AuraError as err:
                _LOGGER.debug("Skrivekvittering uteble (%s); kontroll-leser", err)

            for attempt in range(VERIFY_ATTEMPTS):
                await asyncio.sleep(VERIFY_DELAY)
                try:
                    response = await self._exchange(verify_packet)
                except AuraError as err:
                    _LOGGER.debug(
                        "Kontroll-lesing %s/%s feilet: %s", attempt + 1, VERIFY_ATTEMPTS, err
                    )
                    continue
                current = response.parameters.get(register)
                if current is not None and current.raw == expected:
                    return value

        raise AuraWriteError(
            f"Kontroll-lesingen bekreftet ikke register 0x{register:02X} = {value}"
        )
