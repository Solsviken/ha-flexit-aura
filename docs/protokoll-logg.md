# Protokolllogg — Flexit Aura 160

Alle telegrammer under er fanget mot forfatterens egen Aura 160 på et privat
hjemmenett, Device ID `004B00285746570B` (den står i pakkene), UDP port 4000. Bare lesing er brukt der ikke annet
er nevnt.

## Rammeformat (bekreftet)

```
FD FD | 02 | len + device_id (ASCII) | len + passord (ASCII) | funksjon | data | checksum
```

- Checksum = 16-bits sum av alle bytes etter headeren, little-endian.
- Forespørselsfunksjoner: `01` = les, `03` = skriv-og-returner.
- Svarfunksjoner: `06` = normalt svar, `07` = feil.
- Databblokk: `FF <side>` bytter side, `<param> <verdi>` = énbyte,
  `FE <len> <param> <data>` = flerbyte, `FD <param>` = ikke støttet.

## 2026-09-02 — lesing av 0x01

```
TX: FD FD 02 10 30 30 34 42 30 30 32 38 35 37 34 36 35 37 30 42 04 31 31 31 31 01 FF 00 01 2F 05
RX: FD FD 02 10 30 30 34 42 30 30 32 38 35 37 34 36 35 37 30 42 04 31 31 31 31 06 FF 00 01 01 35 05
```

TX-en er byte-identisk med den som ble fanget i fase 2, og gjenskapes av
`build_read()` i enhetstesten `test_read_packet_matches_captured_bytes`.

**Funn:** svaret har funksjon `06`, ikke `01`. Forespørsels- og svarfunksjon er
altså forskjellige.

## 2026-09-02 — feil passord og feil Device ID

| Tilfelle | Resultat |
|---|---|
| Riktig ID + passord | Funksjon `06`, parameterliste |
| Feil passord (`9999`) | `… 04 39 39 39 39 07 01 56 04` — funksjon `07`, statusbyte `01` |
| Tomt passord | `… 00 07 01 6E 03` — samme feilramme |
| Feil Device ID | **Ingen svar i det hele tatt** (timeout) |

**Konsekvens for integrasjonen:** feil passord kan skilles fra alt annet
(funksjon `07` → `AuraAuthError` → «invalid_auth» i config flow), mens feil
Device ID ser ut som nettverksfeil og må dekkes av `cannot_connect`-teksten.
Feilrammen ble tidligere tolket som en parameterliste og ga parsefeil; den
håndteres nå eksplisitt.

## 2026-09-02 — wildcard-oppdagelse virker ikke

Blauberg/VENTS-familien skal kunne svare på Device ID `DEFAULT_DEVICEID`.
Denne viften svarer ikke:

- Unicast til `<vifte-IP>:4000` med wildcard: timeout.
- Broadcast til `255.255.255.255:4000` og subnettets broadcast-adresse: ingen svar.

**Konsekvens:** ingen automatisk oppdagelse. Device ID er et påkrevd felt i
config flow.

## 2026-09-02 — full registerlesing (3 runder)

| Reg | Navn | Rå hex | Dekodet |
|---|---|---|---|
| 0x01 | power | `01` | på |
| 0x02 | speed | `01` | lav |
| 0x06 | boost | `00` | av |
| 0x07 | timer mode | `00` | av |
| 0x0F | humidity control | `00` | av |
| 0x19 | humidity limit | `46` | 70 % |
| 0x25 | humidity | `45` | 69 % |
| 0x4A | fan 1 rpm | `0C 03` | 780 rpm (little-endian) |
| 0x4B | fan 2 rpm | `00 00` | 0 — enkeltvifte-modell |
| 0x63 | filter interval | `5A 00` | 90 dager |
| 0x64 | filter remaining | `22 10 58 00` | 88 d 16 t 34 min |
| 0x7E | runtime | `19 07 01 00` | 1 d 7 t 25 min = 31,4 t |
| 0x83 | alarm | `00` | ingen |
| 0x88 | filter warning | `00` | ikke nødvendig |
| 0xB7 | air mode | `02` | tilluft |

Tre lesinger på rad ga identiske bytes bortsett fra `0x25`, `0x64` og `0x7E`,
som skal endre seg. Ingen timeouts, ingen checksum-feil.

### Dekoding av varighetsregistrene

`0x64` og `0x7E` kom som **fire** bytes, ikke tre. Layouten er
`minutter, timer, dager (16-bit little-endian)`:

- `0x64 = 22 10 58 00` → 34 min, 16 t, 88 dager = 88,69 dager igjen av 90.
- `0x7E = 19 07 01 00` → 25 min, 7 t, 1 dag = 31,42 timer.

De to bekrefter hverandre: 90 − 88,69 = 1,31 dager forbrukt filtertid, som er
de samme 31,4 timene som driftstelleren viser. En naiv little-endian-tolkning
ga 66,8 dager og 67 353 timer og er altså feil. Dekodingen er låst med
enhetstestene i `tests/test_model.py`.

## 2026-09-12 — sporadiske tapte poller i drift

Etter fem dager i drift viste loggboken i Home Assistant ni «Utilgjengelig»-
perioder på ti timer, hver på **nøyaktig 30 sekunder** — ett poll-intervall.
Det er signaturen til én enkelt mislykket lesing (to forsøk à 2 s), ikke en
vifte som faller av nettet. Sannsynlige årsaker: tapte UDP-datagrammer over
Wi-Fi, eller at viften er opptatt med skyforbindelsen eller retningsskiftet.

**Konsekvens:** koordinatoren beholder nå siste snapshot til
`MAX_CONSECUTIVE_FAILURES` (3) poller på rad har feilet, og klienten gjør tre
forsøk per utveksling i stedet for to. Antall påfølgende feil vises i
diagnostikken som `consecutive_failures`.

## Åpne punkter

- ~~Skriving via async-klienten mot fysisk vifte~~ — bekreftet i Home Assistant
  2026-09-07: hastighet (`0x02`) og luftmodus (`0xB7`) styres fra entitetene.
- Verdien `0xFF` (manuell hastighet, register `0x44`) er ikke undersøkt.
- Adferd ved viftens omstart og ved lengre nettverksbrudd er ikke testet.
