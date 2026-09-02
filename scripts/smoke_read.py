"""Read-only check against a physical unit.

Sends nothing but read telegrams, so it is safe to run at any time. Prints the
raw bytes for every register next to the decoded value, which is how a decoding
assumption gets confirmed or disproved.

    python scripts/smoke_read.py 192.168.1.114 --device-id 004B00285746570B
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import types

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "flexit_aura"
if "flexit_aura" not in sys.modules:
    package = types.ModuleType("flexit_aura")
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules["flexit_aura"] = package

from flexit_aura.client import AuraClient, AuraError  # noqa: E402
from flexit_aura.const import (  # noqa: E402
    AIR_MODES,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    POLL_REGISTERS,
)
from flexit_aura.model import FlexitAuraData  # noqa: E402

REGISTER_NAMES = {
    0x01: "power",
    0x02: "speed",
    0x06: "boost",
    0x07: "timer mode",
    0x0F: "humidity control",
    0x19: "humidity limit",
    0x25: "humidity",
    0x4A: "fan 1 rpm",
    0x4B: "fan 2 rpm",
    0x63: "filter interval",
    0x64: "filter remaining",
    0x7E: "runtime",
    0x83: "alarm",
    0x88: "filter warning",
    0xB7: "air mode",
}


async def run(host: str, password: str, port: int, device_id: str, repeat: int) -> int:
    client = AuraClient(host=host, device_id=device_id, password=password, port=port)

    snapshots: list[FlexitAuraData] = []
    for round_number in range(1, repeat + 1):
        try:
            values = await client.async_read(POLL_REGISTERS)
        except AuraError as error:
            print(f"FEIL i runde {round_number}: {error}")
            return 1
        snapshots.append(FlexitAuraData.from_parameters(values))
        if round_number < repeat:
            await asyncio.sleep(1)

    latest = snapshots[-1]
    print(f"{'REG':<6}{'NAVN':<20}{'RÅ HEX':<12}DEKODET")
    print("-" * 62)
    for register in POLL_REGISTERS:
        key = f"0x{register:02X}"
        raw = latest.raw.get(key, "(mangler)")
        print(f"{key:<6}{REGISTER_NAMES.get(register, ''):<20}{str(raw):<12}", end="")
        print(_decoded_for(register, latest))

    print()
    print(f"Fuktighet:        {latest.humidity} %")
    print(f"Vifte 1 / 2:      {latest.fan1_rpm} / {latest.fan2_rpm} rpm")
    print(f"Filter gjenstår:  {latest.filter_remaining_days} dager")
    print(f"Driftstid:        {latest.runtime_hours} timer")
    print(f"Luftmodus:        {AIR_MODES.get(latest.air_mode, latest.air_mode)}")

    if repeat > 1:
        unstable = {
            key
            for snapshot in snapshots
            for key, value in snapshot.raw.items()
            if value != snapshots[0].raw.get(key)
        }
        print()
        print(f"{repeat} lesinger fullført uten feil.")
        print(
            "Registre som endret seg underveis: "
            + (", ".join(sorted(unstable)) if unstable else "ingen")
        )
    return 0


def _decoded_for(register: int, data: FlexitAuraData) -> str:
    mapping = {
        0x01: data.power,
        0x02: data.speed,
        0x06: data.boost,
        0x07: data.timer_mode,
        0x0F: data.humidity_control,
        0x19: data.humidity_limit,
        0x25: data.humidity,
        0x4A: data.fan1_rpm,
        0x4B: data.fan2_rpm,
        0x63: data.filter_interval_days,
        0x64: data.filter_remaining_days,
        0x7E: data.runtime_hours,
        0x83: data.alarm,
        0x88: data.filter_warning,
        0xB7: data.air_mode,
    }
    return str(mapping.get(register))


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only test mot Flexit Aura")
    parser.add_argument("host")
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--repeat", type=int, default=1, help="antall lesinger")
    args = parser.parse_args()
    return asyncio.run(
        run(args.host, args.password, args.port, args.device_id, args.repeat)
    )


if __name__ == "__main__":
    raise SystemExit(main())
