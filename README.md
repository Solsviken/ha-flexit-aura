# Flexit Aura for Home Assistant

Home Assistant custom integration for the Flexit Aura 160 single-room heat
recovery unit, over the local UDP protocol on port 4000. No cloud, no polling of
a vendor API — Home Assistant talks straight to the unit on your own network.

The Aura 160 is a rebadged unit from the Blauberg/VENTS family, and the protocol
is the one that family uses. Other units in that family may work, but only the
Aura 160 has been tested.

## Entities

| Entity | Register | Writable |
|---|---|---|
| `fan` — on/off and three speeds | `0x01`, `0x02` | yes |
| `select` — air mode (ventilation / heat recovery / supply) | `0xB7` | yes |
| `sensor` — humidity | `0x25` | — |
| `sensor` — fan speed (rpm) | `0x4A`, `0x4B` | — |
| `sensor` — filter remaining, filter interval | `0x64`, `0x63` | — |
| `sensor` — operating time | `0x7E` | — |
| `sensor` — humidity setpoint, timer mode, air mode | `0x19`, `0x07`, `0xB7` | — |
| `binary_sensor` — alarm, filter change, boost, humidity control | `0x83`, `0x88`, `0x06`, `0x0F` | — |

Writes are restricted to an allowlist of registers and values in
`const.py`. Every write is confirmed by reading the register back before the
entity state changes, so a silently dropped UDP packet cannot leave Home
Assistant showing a state the unit is not in.

## Installation

### HACS (custom repository)

1. HACS → Integrations → three-dot menu → Custom repositories.
2. Add this repository, category *Integration*.
3. Install *Flexit Aura*, then restart Home Assistant.

### Manual

Copy `custom_components/flexit_aura` into `<config>/custom_components/` and
restart Home Assistant.

## Setup

Settings → Devices & Services → Add Integration → *Flexit Aura*.

| Field | Notes |
|---|---|
| IP address | Give the unit a DHCP reservation; the integration does not rediscover it |
| Device ID | The 16-character ID from the Flexit app. **Required** — the unit does not answer wildcard discovery, and a wrong ID makes it stay silent |
| Password | `1111` from the factory |
| Port | `4000` unless changed |

Add one entry per unit; the Device ID is the unique identifier, so the entities
survive an IP change (re-enter the new address in the flow).

The poll interval defaults to 30 seconds and can be changed under the
integration's *Configure* menu.

## Development

```bash
python -m pip install pytest pytest-asyncio
python -m pytest
```

The tests run without Home Assistant and without hardware:
`protocol.py`, `client.py` and `model.py` deliberately carry no Home Assistant
imports, and `tests/conftest.py` loads them as a bare package. The client tests
run against a fake unit on localhost that reproduces the real one's error
frames.

To check a live unit without writing anything to it:

```bash
python scripts/smoke_read.py 192.168.1.114 --device-id 004B00285746570B --repeat 3
```

It prints raw bytes next to decoded values, which is how the register decoding
in `docs/protokoll-logg.md` was confirmed.

## Documentation

- [`docs/protokoll-logg.md`](docs/protokoll-logg.md) — captured telegrams,
  register decoding and what has been verified against hardware.
- [`PLAN.md`](PLAN.md) — project plan and phases.
