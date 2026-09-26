# Validatie en open bewijs

Stand van de lokale voorbereiding: 26 september 2026. De huidige HA-code is
offline getest. Er is nog geen fysieke validatie van deze integratie op Home
Assistant, Linux of een Bluetooth-proxy en geen fysieke validatie van de
bedieningsopdrachten.

## Verschillende soorten bewijs

| Niveau | Wat het ondersteunt | Wat het niet bewijst |
| --- | --- | --- |
| Statische schema- en gebruikscodeanalyse | RPC-paden, veldnummers, veldtypen, enums, berichtopbouw en expliciete conversies uit BORA One 1.9.1, build 130922. | Dat iedere methode op ieder apparaat bestaat of dat een onderzochte conversie ook voor andere velden geldt. |
| Openbare programmacatalogus | Anonieme HTTP 200 met vier concrete X PURE-programma-ID's, doelwaarden, grenzen en instellingen; gekoppeld aan de statisch onderzochte appmapper. | Acceptatie door de firmware, temperatuurregeling of fysieke bevestiging. |
| Eerdere apparaatopnamen | Geldige antwoorden en waargenomen veranderingen van één X PURE via een gekoppelde Mac. | Eerste pairing op een andere host, alle modes, schrijfacties of langdurige betrouwbaarheid. |
| Offline codec-, transport- en HA-tests | Gedrag van de implementatie tegen fixtures, nagebootste antwoorden en foutgevallen. | Werking van echte Bluetooth-encryptie, radioverbinding, hardware of firmware. |
| Fysieke integratieproef | Nog uit te voeren op de beoogde HA-installatie. | Tot die proef is afgerond, is er geen bewezen HA/Linux/proxy-ondersteuning. |

## Bestaande fysieke waarnemingen

Onderzoeksapparaat: BORA X PURE PUXU2R, BLE-firmware 3.0.9. De Mac was eerder
gekoppeld. Daarna zijn zelfstandige statusvragen en
statusabonnementen getest, met de officiële app losgekoppeld. De gebruiker
veranderde de apparaatstanden zelf; de onderzoeksclient stuurde geen
opdrachten om verwarming of afzuiging te starten.

- Afzuigstanden zijn zowel opgevraagd als via een statusstream gevolgd, met
  handmatig bevestigde standen 3 en 5. Een reeks losse vragen kreeg afzonderlijke antwoorden.
- Op 25 september zijn de apparaatdescriptor, kookplaatstatus en status van alle
  vier zones uitgelezen. Die opgenomen zones stonden uit. Dit bewijst geen verwarmingsmodus
  of panherkenning.
- De ruwe naloopteller daalde ongeveer 5.000 eenheden in vijf seconden. Daarmee
  zijn milliseconden voor `remainingAfterRun` onderbouwd. Dit bewijs geldt niet
  automatisch voor andere timer- of filtervelden.
- De eerder gekoppelde Mac kon later opnieuw verbinden zonder opnieuw te
  pairen. Eerste pairing met de nieuwe Python/HA-client is niet bewezen.
- Een stream kon starten en stoppen zonder tussentijds statusbericht. Daarom
  vraagt de implementatie expliciet een beginsnapshot op.
- Een korte sessie van ruim drie minuten werkte zonder aparte applicatieheartbeat.
  Dat is geen langdurigheidstest. Onbereikbaarheid na stilstand is waargenomen;
  de precieze slaap- en ontwakingsregels zijn nog onbekend.

Op 26 september is daarnaast tijdens het koken met de zelfstandige Python-client
meegelezen. Linksachter 7 en afzuiging 3 zijn door de gebruiker bevestigd;
de overgang naar zone 0 en naloop 30 minuten is ontvangen. De opname bevat
93 CRC-geldige responses en legde een fout bij tijdelijk onbeschikbare
zonestatus bloot. De daaruit volgende correctie is offline getest, maar nog
niet opnieuw fysiek beproefd. Zie [de kookmeting](COOKING-OBSERVATION.md).

De oorspronkelijke onderzoeksnotities en privéopnamen blijven in een
afzonderlijk lokaal onderzoeksarchief. Dat archief en de officiële appbinary
zijn geen onderdeel van deze distributie. De zelfstandige
[protocolbeschrijving](PROTOCOL.md) vat het relevante bewijs samen.
De repository bevat een
[fixture met opgenomen protocolgegevens](../tests/fixtures/x_pure_3_0_9.json)
voor reproduceerbare offline controles.

## Aanvullend bewijs voor zonetimerstatus

De app zet `ZoneStatus.settings.timer.duration` en `remaining` expliciet om
met Kotlin `MILLISECONDS`. Daarom tonen de zonesensoren duur en resterende
tijd in seconden; de running-vlag heeft een eigen binaire sensor. De ruwe
timerdata blijven aanwezig. Dit is statisch bewijs uit gebruikscode, geen
nieuwe fysieke timerproef.

Daarnaast is een concrete standaardstart voor vier catalogusprogramma's
gereconstrueerd. De app schrijft daarbij index 0 en timer 0; de gehele
gegevensketen is gevolgd, inclusief het verborgen timerscherm en de keuze
voor één zone. Dit maakt een begrensde startimplementatie mogelijk zonder
opgeslagen-programmaparameters te kopiëren. Zie
[ASSIST-PRESETS.md](ASSIST-PRESETS.md) voor bron, instellingen en grenzen.

Gewone timer-settereenheden, limieten, de aparte kookwekker en filtereenheden
blijven onbekend. Ook is bij CSF een verschil vastgesteld: opslaan schrijft
seconden zonder omzetting, terwijl starten naar milliseconden converteert.
Wat de firmware bij opslaan/uitlezen doet is nog onbekend. Zie
[TIMER-EVIDENCE.md](TIMER-EVIDENCE.md) voor het concrete bewijs en de grenzen.

Een nieuwe filteranalyse volgt de appboolean `shouldChangeFilter` terug naar
`remainingFilterLifetime < 1` en vooruit naar de Swift-waarschuwing. Daarmee
is een binaire vervangmelding onderbouwd, zonder de eenheid te kennen.
De integratie beperkt deze tot expliciete recirculatie en normale positieve
Int32-waarden of nul; andere gevallen blijven onbekend. Zie
[FILTER-EVIDENCE.md](FILTER-EVIDENCE.md).

## Platformstatus

| Omgeving | Status |
| --- | --- |
| Eerder gekoppelde Mac, onderzoeksclient | Fysieke read-only proef geslaagd voor de genoemde functies. |
| Home Assistant 2026.9.3, Python 3.14 | Offline testomgeving met gesimuleerde Bluetooth-verbinding. |
| Linux / BlueZ met lokale adapter | Adapterroute geïmplementeerd; eerste pairing, bondopslag en fysiek gebruik nog niet bewezen. |
| Bluetooth-proxy, inclusief ESPHome | Niet fysiek gevalideerd. Gewone GATT-notify/write-ondersteuning bewijst geen ondersteuning van de benodigde bonding en encryptie. |
| Andere modellen of firmwareversies | Niet fysiek gevalideerd; descriptorondersteuning alleen is onvoldoende bewijs. |

Een Bluetooth-bond behoort bij de identiteit van de host/adapter. Een
Mac-bond verhuist niet met deze code naar Linux of een proxy. De configuratie
heeft een expliciete pairingstap en reauthenticatiepad; hun bestaan is geen
bewijs dat elke backend die koppeling uitvoert en bewaart.

## Wat de offline tests controleren

De laatste volledige lokale run gaf **720 geslaagde tests** en **96% coverage**
van de integratiecode (2.283 statements, 97 niet geraakt). De eerdere run vanuit
het uitgepakte [proefpakket](PACKAGING.md) telde 714 tests. De zes aanvullende
tests betreffen uitsluitend de verzoekregistratie in het ontwikkelproefscript;
de runtime in dat pakket is ongewijzigd. Er is getest met
Python 3.14.7 en de echte Home Assistant 2026.9.3-runtime, terwijl de Bluetooth-peer gesimuleerd bleef.
De fixtures omvatten 39 eerdere geschoonde antwoorden en vier geselecteerde
payloads uit de kookmeting. Ruff meldde geen
fouten. De officiële Home Assistant-hassfest-validator slaagde opnieuw inclusief
`--requirements`, met nul ongeldige integraties en nul waarschuwingen,
tegen core 2026.9.3, commit `6de5eb18cd4502f94af44cfff3a02250d88716ed`.
Ook de nieuwe abortvertaling voor een afwijkende reauthenticatie-identiteit
zat in deze validatie. Het [hassfest-verslag](HASSFEST.md) bevat de
reproduceerbare opdracht.
De officiële HACS-validator is nog niet uitgevoerd. Zijn
[entrypoint](https://github.com/hacs/integration/blob/main/action/action.py)
vereist een GitHub-token en repositorynaam; de
[repositorycode](https://github.com/hacs/integration/blob/main/custom_components/hacs/repositories/base.py)
leest GitHub-metadata en bestanden, niet alleen een lokale integratiemap.
De repository staat inmiddels privé op GitHub. HACS vereist een publieke
repository; deze controle blijft daarom uitgesteld tot openbare publicatie.
Zie [publicatievoorbereiding](PUBLISHING.md) voor de bronnen en
voorwaarden. Hassfest, offline tests en pakketcontroles zijn geen vervanging.

De configuratieflow heeft nu 100% statementcoverage. Dat is geen
volledigheidsclaim: de Bluetooth-backend is nagebootst, en de eerste fysieke
koppeling en backendafhankelijk gedrag vragen nog aanvullende tests.

De [tests](../tests) dekken onder meer:

- Framing, checksums, fragmentatie, Protobuf-presence, enums en descriptorgrenzen.
- Decodeerbare opgenomen berichten en onbekende of ongeldige velden.
- Request-ID's, streamlevensduur, timeouts, verbroken verbindingen en late
  callbacks; statusupdates in volgorde bij gelijktijdige vragen en streams.
- Nieuwe beginsnapshots, abonnementherstel, optioneel niet ondersteunde
  methoden en het niet herhalen van bedieningsopdrachten na reconnect.
- Beide bedieningsopties, validatie van zones en standen, geen gefingeerde
  nulwaarden, bevestiging via uitlezen en correcte beschikbaarheid.
- Centrale kookbeveiliging voor sloten, pandetectie, bedrijfsduur en de
  simple-mode-groep, ook wanneer een interne aanroeper de kookvlag weglaat.
- Ontvangstbevestiging met afwijkende of ontbrekende teruglezing: geen
  succesclaim, geen herhaalde schrijfopdracht, behoud van de echte status en
  verwerking van een eventuele latere streamupdate.
- Geen vaste warmhoudbediening afleiden uit alleen de mode-enum wanneer
  variabele ondersteuning ontbreekt; de drie bekende standen blijven mogelijk
  wanneer de descriptor ze via die ondersteuning aanbiedt.
- Discovery zonder automatisch koppelen, configuratie, reauthenticatie met
  bevestiging, succes, fouten, expliciete retry en controle van apparaatidentiteit.
- Beide opties en het herladen van gewijzigde instellingen; probe-opruiming
  bij succes, fout, timeout en annulering, plus unload/shutdown en dynamische entiteiten.
  De begrensde proefregistratie koppelt een zonefout aan het verzoek-ID/RPC-pad
  en bewaart streamafsluiting, zonder ruwe foutteksten of gefingeerd antwoord.
- Zonetimers: conversie van 33.000 milliseconden naar 33 seconden, behoud van
  fracties en ruwe data, juiste zone en ontbrekende timers zonder gefingeerde nulstand.
- Atomair samenvoegen van simple-mode-instellingen en read-only diagnostiek,
  inclusief redactie en downloaden zonder nieuwe apparaatvragen.
- Assist-selectie zonder I/O, expliciete start, verse uitstandscontrole,
  weigering van actieve/gekoppelde zones en afwijkende presetparameters,
  herhaald drukken zonder een lopend programma te wijzigen en geen
  herhaling bij reconnect. Fase confirmation-required blijft zichtbaar.
- De echte HA-services voor Assist-keuze/start en de HA-statusovergangen bij
  fase 2, onbekende fase, fase 3 en einde van het programma, met een fake BLE-peer.
  De ontvangen doeltemperatuur en programmatitel veranderen niet door een
  andere lokale keuze. Geen standaardtemperatuur invullen bij ontbrekende data.
- Filterwaarschuwing bij nul, normale positieve waarden, onbekende of afwijkende
  waarden, recirculatie versus afvoer en verlies van de verbinding/status.
- Opgeslagen favorieten: alleen expliciete reads, plaatsnummer in plaats van
  lijstvolgorde, herkenning zonder eenheden aan te nemen, dubbele indices,
  verschil tussen onbekend en een geslaagde lege response, fouten/annulering,
  cacheverlies bij disconnect en het weigeren van late antwoorden.
- Tijdelijk onbeschikbare zone (code 14): alleen die status wordt onbekend;
  andere bronnen blijven bruikbaar. Correcte fout-/streamvolgorde, geen
  succesvolle refresh na disconnect en geen wachtende zonewrite na invalidatie.

Voor Assist-starts geldt een extra herstelgrens: gelijktijdige aanvragen op
dezelfde zone worden vóór het wachten op de verbinding uitgesloten. Een
mogelijk verzonden start blijft na fout, annulering of reconnect geblokkeerd
tot een later ontvangen status precies dat programma in preheat,
confirmation-required of active toont. Een uitstand heft de blokkade niet op,
omdat vertraagde toepassing nog mogelijk is. Als het programma nooit wordt
toegepast, kan de blokkade dus gedurende de huidige clientinstantie blijven
bestaan. Ze wordt niet over integratieherladen of HA-herstart opgeslagen.
Dit conservatieve beleid bewijst geen werkelijke timing van de firmware;
ook het herstel na een onzekere fysieke start moet nog worden gevalideerd.

Het afzonderlijke [uitleeshulpmiddel](READONLY-PROBE.md) heeft elf offline
tests binnen deze testset: toegelaten reads, weigering van bedienings- en
bevestigingsopdrachten vóór I/O, tijdslimieten, geredigeerde uitvoer en opruiming
bij annulering of fouten. De optionele favorietenread blijft na afsluiten in
het verslag bewaard, ook bij een leeg of niet ondersteund antwoord. De
diagnostiektests controleren bovendien dat een numeriek standaardadres 0
geen nulwaarden in gewone status wist; echte numerieke identifiers en hun
aliassen blijven geredigeerd. De CLI/rapportworkflow is niet op hardware
uitgevoerd; de read-only verbindingsklasse is wel in de kookmonitor gebruikt. Zelfs
een latere geslaagde zelfstandige BLE-proef zou nog geen HA- of proxytest zijn.

Uitvoeren vanuit de projectmap met een voorbereide ontwikkelomgeving:

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

Deze opdrachten testen de lokale code; een groen resultaat is geen
hardwarecertificering. De minimumversie in de metadata is de offline geteste
versie 2026.9.3; oudere versies zijn niet gevalideerd.

## Nog fysiek te valideren

Alle onderstaande punten staan open voor een later afgesproken proef, met
iemand bij het apparaat. Ze zijn tijdens deze voorbereiding niet uitgevoerd.

- [ ] Eerste pairing op de beoogde HA-adapter, inclusief fysieke Connect-modus,
  versleutelde karakteristieken, herstart en bondbehoud.
- [ ] Read-only status en abonnementen op HA vergelijken met het bedieningspaneel.
- [ ] Bereikverlies, slaap/ontwaken, herstel, HA-herstart en langere verbindingen
  testen; vaststellen of een heartbeat ooit nodig is.
- [ ] De correctie voor code 14 tijdens naloop fysiek herhalen: afzuiging blijft
  zichtbaar, ontbrekende zones zijn onbekend en herstellen bij geldige status.
- [ ] Aanwezige en ontbrekende waarden toetsen voor actieve zones, restwarmte,
  pandetectie, bridge-status en CSF-fasen.
- [ ] Ondersteunde bedieningen afzonderlijk bevestigen, inclusief teruglezen,
  foutgevallen en de daadwerkelijk aangeboden descriptorwaarden.
- [ ] De onderbouwde zonetimerstatusconversies met een handmatig ingestelde timer vergelijken.
- [ ] Settereenheden en limieten van timers, de aparte kookwekker, filtervelden
  en de opslag-/startconversies van CSF verder onderbouwen vóór extra bediening.
- [ ] De vier voorbereide Assist-starts en fysieke bevestiging op de kookplaat
  toetsen, inclusief daadwerkelijke eindtoestand na stoppen.
- [ ] De filtervervangmelding vergelijken met de echte app; raw schaal en
  resetwerking blijven afzonderlijke onderzoeksvragen.
- [ ] Bewaarsemantiek van SaveCsf toetsen via volledige lijsten vóór en na
  een bewuste appwijziging, inclusief weggelaten slots en behoud van slots 1–2.
- [ ] Eerst de read-only favorietenknop en plaatsen 3–5 met de officiële app
  vergelijken, zonder opgeslagen parameters terug te schrijven.
- [ ] Bridge- en unbridgegedrag, overige CSF-starts en actieve wijziging
  reconstrueren en valideren vóór verdere uitbreiding.
- [ ] Eventuele proxyondersteuning per concrete hardware/softwarecombinatie
  testen en de supportmatrix bijwerken.

Voor actuele functiekeuzes en beperkingen: [FEATURES.md](FEATURES.md).

## Beoordeling van het volledige einddoel

De lokale voorbereiding is niet gelijk aan een werkende, volledig geteste
eerste release. De volgende beoordeling gebruikt de huidige code en het
bestaande bewijs; ontbrekend bewijs wordt niet als een geslaagde controle geteld.

| Vereiste | Huidig bewijs | Oordeel |
| --- | --- | --- |
| Installeerbare HA/HACS-projectstructuur | Configuratieflow, zeven entiteitsplatforms, manifest, HACS-metadata, icoon, licentie en workflows; lokale hassfest geslaagd. | Lokaal voorbereid; echte installatie en HACS-validatie nog open. |
| Lokale verbinding zonder een cloudaccount in de integratie | Zelfstandige BRPC-laag, adaptercode en eerdere Mac-statusopnamen. | Eerste HA-pairing, bondbehoud en proxygedrag niet bewezen. |
| Brede bruikbare app- en BLE-functionaliteit | Onderbouwde status, afzuiging, zones, vier catalogusstarts, Assist-fase/doel/bevestiging, opgeslagen-favorietenoverzicht, filtermelding, instellingen en optionele diagnostiek aanwezig; inventaris van 54 gegenereerde generic-RPC's onderzocht. | Onvolledig: timerbediening, overige CSF-starts/wijzigingen/opslag, bridge en filtereenheden/reset blijven open. |
| Betrouwbare bediening en herstel | Offline tests voor grenzen, teruglezing, timeouts, streams, annulering en geen commandoreplay. | Softwaregedrag getoetst; apparaatreacties, timing en duurproef ontbreken. |
| Tests, documentatie en bruikbare eerste release | Reproduceerbare offline suite, opnamen, protocol- en functiedocumentatie, read-only proefscript. | Voorbereiding aanwezig; fysieke acceptatie en definitieve releasekeuzes ontbreken. |
| Later publiceren | Alleen lokale bestanden en voorbereide metadata. | Bewust uitgesteld op verzoek van de gebruiker. |

De volgende noodzakelijke externe stap is een proef met een aanwezige gebruiker
op de beoogde HA-adapter, aanvankelijk met beide bedieningsopties uit. Daarnaast
zijn gerichte vergelijkingen met de officiële app nodig voor de nog onbekende
timer-, preset- en filterwaarden. De reeds geslaagde offline suite opnieuw
uitvoeren kan deze ontbrekende waarnemingen niet vervangen.
