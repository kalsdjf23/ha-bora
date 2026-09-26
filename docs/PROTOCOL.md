# Lokaal BORA-protocol

Deze eigen implementatie is afgeleid uit de berichtbeschrijvingen van de
lokaal onderzochte BORA One-app en gecontroleerd met geselecteerde opnames
van één X PURE (PUXU2R, BLE-revisie 3.0.9). De officiële app, appbinary,
accountgegevens en ruwe privéopnames maken geen deel uit van dit project.
De aanwezigheid van een methode in de app bewijst geen ondersteuning door
elk apparaat. Apparaatdescriptors beperken de aangeboden waarden.

## BLE en pairing

De eigen service is `64cbfe50-126b-17ac-774e-f6fa40487dac`.
De overige characteristics delen hetzelfde suffix:

| Characteristic | Functie |
| --- | --- |
| FE51 | BRPC-verzoeken, writes met ATT-bevestiging |
| FE52 | Beveiligd antwoordkanaal, notificaties |
| FE53 | Bondingstatus: 00 niet gekoppeld, 01 gekoppeld, 02 bezig |

De transportlaag gebruikt conservatieve chunks van maximaal 20 bytes.
Home Assistant levert het actuele BLE-device via zijn Bluetoothmanager;
er wordt geen afzonderlijke scanner gestart. Eerste pairing gebeurt alleen
na bevestiging in de configuratieflow. Een gewone reconnect controleert
het bestaande bond en kan een herauthenticatieverzoek opleveren.

Een gekoppelde Mac heeft succesvol gelezen. Pairing via Linux of een
Bluetooth-proxy moet nog fysiek worden getest. macOS-peripheral-ID's zijn
hostspecifiek; ze worden niet als universeel MAC-adres vastgelegd.

## Framing en BRPC

Een frame is `7E + escaped(payload + CRC32) + 7C`. CRC32 is big-endian;
de checksum wordt over de Protobuf-payload berekend. Bytes 7C, 7D en 7E
worden geescaped als respectievelijk 7D5C, 7D5D en 7D5E. Notificaties kunnen
fragmenten van frames of meerdere frames bevatten. Foute CRC's, ongeldige
velden en frames groter dan 1 MiB worden afgewezen.

| Requestveld | Nummer | Type |
| --- | --- | --- |
| path | 2 | string |
| id | 3 | uint32, uniek en niet nul |
| body | 4 | bytes met specifiek Protobuf-verzoek |
| stream | 6 | NONE=0 of STOP=2 |

| Responseveld | Nummer | Type |
| --- | --- | --- |
| code | 2 | antwoordcode; 0 bij succes |
| request_id | 3 | uint32 |
| body | 4 | bytes met specifiek Protobuf-antwoord |
| error | 5 | foutbericht; niet als succes behandelen |
| stream | 7 | NONE=0, CONTINUE=1, STOP=2, START=3 |

Een stream start met een normaal verzoek aan `Stream…`. START bevestigt
het abonnement; CONTINUE levert updates. STOP gebruikt hetzelfde pad en
request-ID als het abonnement. START garandeert geen beginsnapshot: na
abonneren volgen daarom expliciete statusvragen. Unary-antwoorden en
streamupdates worden in ontvangstvolgorde verwerkt, zodat een oudere
snapshot geen nieuwere update overschrijft.

Request-ID's worden niet hergebruikt zolang er een bijbehorend verzoek of
abonnement bestaat. Notificaties van een oude verbinding worden genegeerd.
Een timeout van een bedieningsverzoek kan betekenen dat het apparaat de
opdracht wel heeft ontvangen. De integratie herhaalt die opdracht nooit.

## Diensten en bewijs

De bibliotheek bevat eigen codecs voor de diensten Identify, Extractor,
Cooktop en Zone en voor optionele diagnostische leesmethoden. Het overzicht
in [FEATURES.md](FEATURES.md) onderscheidt HA-entiteiten, codec-ondersteuning
en nog ontbrekende validatie. Er is geen HA-service om willekeurige RPC's
uit te voeren. Firmware, factory reset, provisioning en dealerinstellingen
worden niet aangeboden als bediening.

De gesaniteerde fixture `tests/fixtures/x_pure_3_0_9.json` bevat 15 sessies
met 39 geldige antwoorden. Dit is bewijs voor concrete reads, framing en
afzuigstreamupdates; het is geen opname van geslaagde bedieningscommando's.
Encoder- en entiteitentests zijn offline bewijs voor de implementatie.

Een geslaagde RPC bevestigt ontvangst, niet dat de gewenste waarde al actief is.
De client leest status terug en vergelijkt de relevante velden. Ontbreekt die
waarde of wijkt ze af, dan meldt HA de opdracht als nog onbevestigd en toont
het de werkelijk ontvangen status. Er volgt geen nieuwe schrijfopdracht.
Latere streams kunnen de verandering alsnog tonen; hun timing en het gedrag
van echte bedieningen moeten nog fysiek worden onderzocht.

## Semantiek die niet gegokt wordt

- `remainingAfterRun` is aantoonbaar milliseconden. De gemeten ingestelde
  naloop is 30 minuten, terwijl de descriptor alleen 10, 15 en 20 minuten
  als schrijfbare opties adverteert. Uitlezing en keuzelijst blijven gescheiden.
- Afzuiging gebruikt index 9 voor `P`; kookzones gebruiken index 10 voor `P`.
  Indexen en labels worden uit de descriptor gelezen.
- `readyForSleep=false` kwam ook voor bij een fysiek uitgeschakelde kookplaat.
  Dit veld is geen aan/uit-status. `potDetectionActive` bewijst evenmin dat
  daadwerkelijk een pan aanwezig is.
- Zonestatus Timer.duration/remaining zijn via appconversies als milliseconden
  bewezen en worden als seconden getoond. De aparte timer-settervelden,
  kookwekker en filterlevensduur houden hun eerdere bewijsgrenzen; zie
  [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md).
- Super Simple Mode schrijft de volledige groep van vijf uitgeschakelde
  functies. De integratie wijzigt deze groep onder een lock, met bevestigde
  uitlezing tussen wijzigingen. Dit is geen aan/uit-knop voor de modus zelf.
- Vier CSF-catalogusstarts combineren concrete openbare records met de
  gereconstrueerde productiecaller. Hun vaste index- en timerwaarde nul zijn
  expliciete appstartuitzonderingen; ze worden niet uit descriptorgrenzen
  gegokt. Zie [ASSIST-PRESETS.md](ASSIST-PRESETS.md). Overige CSF-bediening en
  het ongedaan maken van een zonebrug blijven zonder onderbouwde route.
- De onderzochte Swift-appactie `bridgeSelectedAction` roept `SelectZones`
  aan; die tak bewaart een paar zone-identiteiten in het selectiemodel en
  keert terug. Dit bewijst lokale selectie, geen `SetBridged`-opdracht. De
  aanwezigheid van gegenereerde service-adapters bewijst evenmin appgebruik.
