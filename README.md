# BORA voor Home Assistant

Privévoorbereiding van een onofficiële Bluetooth-integratie voor BORA.
De integratie bevat statusweergave, afzuigbediening en kookinstellingen, met
bediening standaard uitgeschakeld. De broncode staat in de privérepository
[kalsdjf23/ha-bora](https://github.com/kalsdjf23/ha-bora). Dit project is nog niet openbaar,
niet via HACS beschikbaar gemaakt en niet op een echte Home Assistant-installatie
met de kookplaat gevalideerd.

Het fysieke onderzoeksbewijs betreft één BORA X PURE, model PUXU2R met
BLE-firmware 3.0.9, uitgelezen vanaf een eerder gekoppelde Mac. De Home
Assistant-integratie is getest met opgenomen antwoorden en gesimuleerd
Bluetooth-verkeer. Eerste koppeling op Linux, gebruik via Bluetooth-proxy's,
andere BORA-modellen en fysieke bediening via deze integratie zijn nog niet
bewezen. Zie [validatie en beperkingen](docs/VALIDATION.md).

Een [live kookmeting](docs/COOKING-OBSERVATION.md) bevestigde zonevermogen,
afzuigstanden en het begin van de naloop. De gevonden uitval bij een tijdelijk
onbeschikbare zone is vervolgens offline verholpen; die correctie moet nog
op het apparaat worden herhaald.

Een afzonderlijke [afzuigproef](docs/HARDWARE-CHECKS.md) leverde code 12
(`UNIMPLEMENTED`) op en bevestigde geen werkende bediening. Het proeflog
onderscheidt de mislukte schrijfopdracht nog niet van het teruglezen erna.
Afzuigbediening blijft daarom experimenteel; statusuitlezing werkte wel.

## Wat is voorbereid?

- Afzuigstand, automatische stand, expliciete boostpreset, nalooptijd en naloop stoppen.
- Per kookzone vermogen, modus, restwarmte, bridge-status en kookprogrammastatus;
  daarnaast leesbare timerduur, resterende tijd en actief-status.
- Optionele kookbediening: vermogen, warmhouden, aankookautomaat en een actief kookprogramma stoppen.
- Vier X PURE Assist-programma's: lokale programmakeuze en een afzonderlijke
  startknop per ondersteunde zone, met behoud van fysieke Assist-bevestiging.
  Actuele fase, bevestiging nodig en herkenbare doeltemperatuur komen uit de ontvangen status.
- Filtervervangmelding voor bekende recirculatie, volgens de onderbouwde appdrempel.
- Opgeslagen appfavorieten bekijken via een expliciete uitleesknop en drie statussensoren.
- Pauze, kinderslot, reinigingsslot, signaalvolume, aanraakgevoeligheid en andere ondersteunde instellingen.
- Apparaatgegevens, foutcodes en optionele, expliciet op te vragen diagnostiek.

Entiteiten en keuzelijsten volgen de apparaatdescriptor en aanwezige
statusberichten. Niet ieder model krijgt alle functies. De volledige lijst,
voorwaarden en nog ontbrekende functies staan in [FEATURES.md](docs/FEATURES.md).
De zonetimerstatus gebruikt onderbouwde millisecondenconversies. Timerbediening,
kookwekkerconversies en filtereenheden blijven open; zie
[TIMER-EVIDENCE.md](docs/TIMER-EVIDENCE.md).
De vier concrete catalogusstarts en hun onderbouwing staan in
[ASSIST-PRESETS.md](docs/ASSIST-PRESETS.md). Dit zijn voorbereide standaardstarts;
eigen programmaparameters en opgeslagen-programmahergebruik blijven open.
Het afzonderlijke [favorietenoverzicht](docs/SAVED-ASSISTS.md) biedt wel
uitlezing, zonder opgeslagen programma's te starten of te wijzigen.

De integratie vraagt geen cloudaccount en communiceert lokaal via Bluetooth.
Ze gebruikt Home Assistants Bluetooth-infrastructuur. Dat maakt de architectuur geschikt om verschillende
adapters te gebruiken, maar bewijst nog geen werkende pairing via een proxy.

## Bediening inschakelen

Bij het toevoegen staan beide opties uit:

| Optie | Betekenis |
| --- | --- |
| Bediening van afzuiging en instellingen inschakelen | Ontgrendelt afzuigbediening en algemene instellingen. |
| Kookbediening inschakelen | Extra toestemming voor onder meer zonevermogen, warmhouden, aankookautomaat, pauze en vergrendelingen. Vereist ook de eerste optie. |

Met beide opties uit blijven statusentiteiten en de optionele diagnoseknop
bruikbaar. Bediening vereist daarnaast een bereikbare kookplaat, een geldige
status en de betreffende ondersteunde waarden. Een ontbrekende status wordt
geen nulstand. Verbindingsherstel herstelt uitlezen en abonnementen; opdrachten
worden niet opnieuw afgespeeld of voor later bewaard.

Na ontvangstbevestiging van een opdracht leest de integratie de status opnieuw
en vergelijkt het relevante veld met de gevraagde waarde. Bij een afwijkende
of ontbrekende waarde wordt de bediening als nog onbevestigd gemeld; de echte
teruggelezen toestand blijft zichtbaar. Een apparaat kan de verandering pas
later melden. Ook bij een timeout kan de uitkomst onzeker zijn. De integratie
herhaalt de opdracht in geen van deze gevallen automatisch.

## Latere handmatige installatie

Onderstaande stappen beschrijven een toekomstige, afzonderlijk uit te voeren
proef. Tijdens de lokale voorbereiding zijn ze niet op Home Assistant uitgevoerd.
De projectmetadata vermeldt Home Assistant 2026.9.3 als minimum; de offline
testomgeving gebruikt 2026.9.3 en Python 3.14. Oudere versies zijn niet gevalideerd.

1. Kopieer de map `custom_components/bora` naar
   `/config/custom_components/bora` van de beoogde Home Assistant-installatie.
2. Herstart Home Assistant en voeg **BORA** toe via **Instellingen → Apparaten & diensten**.
3. Selecteer het gevonden apparaat of voer de Bluetooth-identiteit handmatig in.
   De configuratiestap vraagt om de Connect-modus op de kookplaat te activeren,
   BORA One te sluiten en een eventuele koppelingsvraag te bevestigen.
4. Begin met beide bedieningsopties uit en controleer de statusweergave.

De eerste koppeling met de gekozen HA-adapter moet nog fysiek worden getest.
Een bestaande Mac-koppeling wordt niet overgedragen aan die adapter. Publicatie,
HACS-installatie en praktijktests blijven open werk; zie
[PUBLISHING.md](docs/PUBLISHING.md).

## Ontwikkeling en tests

De protocolcode staat los van Home Assistant onder
[`custom_components/bora/ble`](custom_components/bora/ble).
De adapter, coordinator en entiteiten verbinden deze laag met Home Assistant.
De tests gebruiken fixtures en een gesimuleerde BLE-peer; ze maken geen
verbinding met de echte kookplaat.

De laatste lokale verificatie: **720 tests geslaagd, 96% coverage** van de
integratiecode, met Python 3.14.7 en de echte Home Assistant 2026.9.3-testruntime. Ruff en de
officiële [hassfest-validatie](docs/HASSFEST.md), inclusief requirementscontrole, slaagden ook.
HACS-validatie en de fysieke HA-proef zijn nog niet uitgevoerd.

Voor een ontwikkelomgeving met Python 3.14:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

Zie [VALIDATION.md](docs/VALIDATION.md) voor de betekenis en grenzen van die tests
en [PROTOCOL.md](docs/PROTOCOL.md) voor de protocolbeschrijving.
[APP-COVERAGE.md](docs/APP-COVERAGE.md) bewaakt de brede functiedekking;
[READONLY-PROBE.md](docs/READONLY-PROBE.md) beschrijft een voorbereide, begrensde
uitleesproef. Dat hulpmiddel heeft zeventien offline tests; de gewone
rapportworkflow is ook op de gekoppelde Mac [fysiek gecontroleerd](docs/HARDWARE-CHECKS.md).
Het project gebruikt de [MIT-licentie](LICENSE). Het is geen officieel BORA-product
en bevat geen distributie van de officiële BORA-app.
