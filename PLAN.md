# Flexit Aura 160 → Home Assistant — utviklingsplan

Status per 2026-09-02. Bygger på fase 1–5 i `Old dokumenter/`.

**Framdrift:** fase A–D er implementert. Integrasjonen ligger i
`custom_components/flexit_aura/`, 37 tester passerer uten hardware, og lesing er
verifisert mot den fysiske viften (se `docs/protokoll-logg.md`). Gjenstår:
skrivetest av async-klienten mot fysisk vifte, og fase E (HACS-publisering).

## 1. Hva som allerede er etablert

| Område | Status |
|---|---|
| Transport | UDP, port 4000, unicast mot viftas IP |
| Rammeformat | `FD FD` + `02` (protokolltype) + len+DeviceID (16 ASCII) + len+passord (4 ASCII) + funksjon + parameterblokk + 2-byte checksum (sum & 0xFFFF, little-endian) |
| Funksjoner | `0x01` = les, `0x03` = skriv-og-returner |
| Parameterkoding | `FF <høybyte>` setter side; `<param> <verdi>` = 1 byte; `FE <len> <param> <data>` = flerbyte; `FD <param>` = ugyldig/ikke støttet |
| Verifisert skriving | `0x02` hastighet (1/2/3) — testet reversibelt og bekreftet med kontroll-lesing |
| Kode som kan gjenbrukes | `protocol.py` (ramme/parse) og `aura_client.py` (enhetsmodell) — allerede fri for webserver-avhengigheter |

### Protokollidentifikasjon (høy sannsynlighet, bør bekreftes)
Rammeformatet (`FD FD`, 16-tegns device-ID, 4-sifret passord, UDP/4000, registerkart med
0x01 power / 0x02 speed / 0x25 RH / 0x4A-0x4B RPM / 0x64 filter / 0xB7 luftmodus) er identisk med
**Blauberg / VENTS-protokollen** (Vento Expert / TwinFresh, «unit type 0x1B00»). Flexit Aura 160 er
etter alt å dømme en rebrandet enhet fra denne familien. Konsekvens: registerkartet kan
kryss-sjekkes mot offentlig dokumentert Blauberg-protokoll i stedet for å gjettes — men hver
skrivbar verdi skal fortsatt verifiseres fysisk på *denne* enheten før den eksponeres.

## 2. Add-on eller integrasjon? → **Custom integration (HACS)** — BESLUTTET 2026-09-02

Anbefaling: bygg en `custom_components/flexit_aura` integrasjon, ikke en add-on.

- Kommunikasjonen er ren UDP fra HA-verten til viften. Ingen egen prosess, database eller
  binærtjeneste trengs — altså ingen grunn til add-on.
- Add-ons kjører kun på HA OS/Supervised. En integrasjon virker på alle installasjonstyper
  (Container, Core, OS) og distribueres via HACS.
- Kun en integrasjon kan eksponere ekte entiteter (`fan`, `sensor`, `binary_sensor`, `select`,
  `number`, `button`) med device registry, unique_id, energi-/historikk-støtte og
  config flow for IP + flere enheter.
- En add-on ville uansett måtte snakke med HA via MQTT eller REST — et unødvendig ekstra ledd.

Add-on er kun aktuelt senere hvis vi vil ha et separat feilsøkingspanel; det er en «nice to have»,
ikke en del av leveransen.

## 3. Arkitektur

```
custom_components/flexit_aura/
  manifest.json          # domain, iot_class: local_polling, requirements, version
  const.py               # DOMAIN, registre, enums, defaults
  protocol.py            # ren ramme-/parse-logikk (fra dagens protocol.py, uten sockets)
  client.py              # async UDP-klient: asyncio DatagramProtocol, retry, lås, batch-lesing
  coordinator.py         # DataUpdateCoordinator, poll-intervall (default 30 s), feilhåndtering
  config_flow.py         # bruker-flyt: host, device_id, passord + options flow (intervall)
  entity.py              # felles FlexitAuraEntity med DeviceInfo/unique_id
  fan.py sensor.py binary_sensor.py select.py number.py switch.py button.py
  strings.json / translations/{en,nb}.json
  diagnostics.py
hacs.json                # HACS-metadata
```

Nøkkelvalg:
- **Async**: HA tåler ikke blokkerende `socket.recv` i event-loopen. `protocol.py` beholdes synkron
  og ren (lett å teste), mens `client.py` gjør I/O med `asyncio`.
- **Én samlelesing per poll**: alle registre i én pakke (fungerer allerede i dag) → én UDP-runde per
  30 s i stedet for 20.
- **Skrivepolicy beholdes**: allowlist av register + validerte verdiområder, skriv → kontroll-les →
  oppdater state. Ukjente registre skrives aldri.
- **unique_id = Device ID** (16-tegns enhets-ID fra viften), ikke IP. Da overlever integrasjonen
  DHCP-endringer. IP kan senere oppdateres via reauth/discovery.
- **Flere vifter**: én config entry per enhet, ingen hardkodet IP noe sted.

## 4. Entiteter (fase 1 av integrasjonen = kun verifiserte funksjoner)

| Entitet | Register | Skriv | Merknad |
|---|---|---|---|
| `fan.flexit_aura` | 0x01 power, 0x02 speed | ja | 3 preset modes (lav/medium/høy) + on/off. Både 0x01 og 0x02 er fysisk bekreftet |
| `sensor` fuktighet | 0x25 | – | % RH |
| `sensor` vifte 1/2 RPM | 0x4A/0x4B | – | diagnostic |
| `sensor` filter gjenstår | 0x64 | – | dager |
| `sensor` driftstimer | 0x7E | – | diagnostic |
| `binary_sensor` alarm | 0x83 | – | problem-klasse |
| `binary_sensor` filterbytte | 0x88 | – | problem-klasse |
| `select` luftmodus | 0xB7 | ja | ventilasjon / varmegjenvinning / tilluft — bekreftet fysisk |
| `switch` boost | 0x06 | ja* | etter test |
| `switch` fuktstyring | 0x0F | ja* | etter test |
| `number` fuktgrense | 0x19 | ja* | etter test |

Alt merket `*` holdes deaktivert i koden til en reversibel test er kjørt og logget.

## 5. Faseplan

**Fase A — protokoll-hardening (før HA-kode)**
1. Kjør 20+ gjentatte lesinger uten skriving; verifiser stabile bytes og at checksum stemmer på
   alle svar (svarer på det åpne spørsmålet i statusdokumentet).
2. Beregn checksum-kandidater mot minst 5 uavhengige RX-pakker.
3. ~~0x01 og 0xB7~~ — bekreftet fysisk av bruker 2026-09-02. Gjenstår: skriv logg til
   `docs/protokoll-logg.md` hvis konsollutskriftene finnes.
4. Test reconnect: bryt nettverk, restart viften, verifiser at klienten kommer tilbake.

**Fase B — bibliotekslag**
5. Flytt `protocol.py` til ren, sync, testbar modul + async `client.py`. Enhetstester uten hardware
   (fake datagram-endepunkt) — de eksisterende testene i `tests/` gjenbrukes.

**Fase C — HA-skjelett**
6. `manifest.json`, `const.py`, `coordinator.py`, `config_flow.py`, `entity.py`.
7. Kun read-only entiteter først. Installer manuelt i `config/custom_components/` og verifiser.

**Fase D — styring**
8. `fan`-entitet med power (0x01) + hastighet (0x02) — begge bekreftet, kan bygges direkte.
9. `select` luftmodus (0xB7) — bekreftet. Switch/number (0x06/0x0F/0x19) etter egne tester.

**Fase E — polering og distribusjon**
10. Oversettelser (nb/en), diagnostics, options flow for poll-intervall, ikoner.
11. `hacs.json`, README, GitHub-repo, versjonstagging → installerbar via HACS som custom repository.
12. Valgfritt senere: DHCP/UDP-broadcast discovery (Blauberg-protokollen har en broadcast-scan med
    device-ID `DEFAULT_DEVICEID`), som gir automatisk oppdagelse av nye vifter.

## 6. Åpne punkter som trenger avklaring
- Er 0x01-skrivetesten (power) og 0xB7 (luftmodus) faktisk kjørt og bekreftet fysisk? Loggene finnes
  ikke i mappen. Hvis ikke: fase A pkt. 3 må kjøres først.
- Kjører Home Assistant på samme nettverk/VLAN som viften? UDP-unicast krever ruting hvis ikke.
- Skal integrasjonen publiseres offentlig på GitHub/HACS, eller kun brukes privat?
- Passordet `1111` — er det fabrikkstandard, og skal det kunne endres i config flow? (ja, gjør det
  til et felt med default `1111`).
