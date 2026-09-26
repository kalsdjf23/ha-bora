# Functies en voorwaarden

Deze lijst beschrijft de lokaal geïmplementeerde integratie. Een codec, entiteit
of geslaagde simulatietest bewijst niet dat een echte kookplaat de bijbehorende
opdracht accepteert. De huidige fysieke onderbouwing staat in
[VALIDATION.md](VALIDATION.md).

## Algemene voorwaarden

- **Monitoring:** geen bedieningsoptie nodig; wel een beschikbare verbinding en relevante status.
- **Algemene bediening:** optie `enable_controls` moet aan staan.
- **Kookbediening:** zowel `enable_controls` als `enable_cooking_controls` moeten aan staan.
- Vermogensstanden, zonenamen en beschikbare mogelijkheden worden uit de
  apparaatdescriptor gelezen. Instellingen in een `pure`-bericht worden alleen
  aangeboden wanneer die uitbreiding in de status aanwezig is.
- Niet elke instelling heeft een eigen capability-vlag. Voor zulke instellingen
  vormt het bekende berichtschema de basis; fysieke ondersteuning moet nog
  worden bevestigd. Een apparaat kan een methode met `UNIMPLEMENTED` afwijzen.
- Ontbrekende of onbekende waarden blijven onbekend. Een onderbroken verbinding
  maakt entiteiten onbeschikbaar; een stil statusabonnement betekent niet dat
  vermogen of resterende tijd nul is.
- Een individuele zonestatusvraag met code 14 (`UNAVAILABLE`) maakt alleen
  die zone onbekend; afzuiging en andere geldige status blijven bruikbaar.
  Zonebediening vereist actuele zonestatus. Zie [de kookmeting](COOKING-OBSERVATION.md).

## Afzuiging

De fysieke proef voor handmatig 0 → 1 → 0 bevestigde geen geslaagde bediening:
beide bedieningsfases eindigden met code 12. Het log koppelt de fout nog niet
aan de schrijfopdracht of een daaropvolgende statusvraag. De onderstaande
bedieningen zijn dus implementatievoorbereiding, geen bewezen apparaatfuncties.
Zie [het hardwareverslag](HARDWARE-CHECKS.md). Uitlezen van standen werkte wel.

| Entiteit of functie | Voorwaarden en gedrag |
| --- | --- |
| Vermogen en modus | Monitoring; stand met label uit de descriptor. |
| Fan: handmatige standen | Algemene bediening; alleen geadverteerde standen en handmatige modus. Percentage verdeelt de gewone standen, zonder fysiek luchtdebiet te suggereren. |
| Fan: automatisch en boost | Algemene bediening; automatisch alleen bij geadverteerde automodus. Een bijzonder vermogenslabel zoals `P` wordt een afzonderlijke preset. |
| Resterende naloop en naloop actief | Monitoring; de waargenomen milliseconden worden naar seconden omgerekend. |
| Ingestelde nalooptijd | Monitoring; het bekende enumlabel wordt als minuten getoond. |
| Nalooptijd kiezen | Algemene bediening; `pure`-status en een lijst ondersteunde naloopwaarden vereist. |
| Naloop stoppen | Algemene bediening; alleen beschikbaar bij een positieve resterende nalooptijd. |

Op het onderzochte apparaat zijn afzuigstanden `0` tot en met `8` gewone
standen en is index `9` het label `P`. De fan kiest bij 100% de hoogste gewone
stand; boost vraagt om de expliciete preset. Dit zijn apparaatdescriptorwaarden,
geen vaste aanname voor alle modellen.

De vastgelegde naloopconfiguratie is 30 minuten, terwijl de descriptor voor
wijzigingen 10, 15 en 20 minuten aanbiedt. De aparte statussensor kan daarom
30 minuten tonen zonder die waarde als selecteerbare optie toe te voegen.

## Kookzones

| Entiteit of functie | Voorwaarden en gedrag |
| --- | --- |
| Vermogen en modus | Monitoring per geadverteerde zone; label, timerdata en eventuele gekoppelde zone als attributen. |
| Timerduur, resterende tijd en timer actief | Monitoring zonder bedieningsopties; duur en resterende tijd worden vanuit onderbouwde milliseconden als seconden getoond, met behoud van ruwe attributen. Een ontbrekend timerbericht maakt de entiteiten onbeschikbaar en hun waarden onbekend. |
| Restwarmte | Monitoring van de gerapporteerde vlag; geen gemeten temperatuur. |
| Pandetectie actief | Diagnostische vlag; betekent niet bewezen dat er een pan aanwezig is. |
| Bridge-status | Monitoring van de bridge-vlag en gekoppelde zone-identiteit. |
| Kookprogramma / CSF | Monitoring van type en ruwe parameters; herkenbare catalogusprogramma's krijgen hun naam als attribuut. Dit komt uit apparaatstatus, niet uit de lokale keuze. |
| Programmafase en Assist-bevestiging nodig | Aparte fase-sensor en binaire bevestigingssensor. Bekende andere zonemodus geeft `inactive`; onbekende fasen maken de bevestigingswaarde onbekend. |
| Assist-doeltemperatuur | Ontvangen doelwaarde in °C voor de vier herkenbare FRYING-programma's op een passende X PURE-zone. Geen gemeten pantemperatuur en geen ingevulde catalogusdefault; onbekende programma's en ongeldige waarden blijven onbekend. |
| Vermogen instellen | Kookbediening en geadverteerde vermogensmodus. Aaneengesloten indices krijgen een getalinvoer; bij gaten in de lijst wordt het een keuzelijst. |
| Warmhouden | Kookbediening, `pure`-status, geadverteerde warmhoudmodus en variabele warmhoudondersteuning. Keuzes: smelten, warmhouden en sudderen volgens de bekende enums. |
| Aankookautomaat | Kookbediening, `pure`-status en geadverteerde aankookmodus. De keuzes gebruiken gewone numerieke vermogenslabels, zonder boostlabel. |
| Kookprogramma stoppen | Kookbediening en geadverteerde CSF-modus; alleen beschikbaar wanneer de zone CSF als huidige modus meldt. |
| Assist kiezen en starten | Kookbediening, X PURE-producttype 2 en passende FRYING-capabilities; vier concrete catalogusprogramma's. Keuze is lokaal, start vereist een aparte knop en een opnieuw uitgelezen uitgeschakelde, ongekoppelde zone. |

De onderzochte X PURE heeft de zone-identiteiten `front_left`, `back_left`,
`back_right` en `front_right`. Gewone zonevermogens lopen van `0` tot en met `9`;
index `10` heeft label `P`. Dit verschilt dus van de boostindex van de afzuiging.
Het zonetimerbewijs komt uit expliciete conversies in de appcode, nog niet uit
een nieuwe fysieke timerproef; zie [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md).

Vaste warmhoudbediening bij `variableHeatRetentionSupport=false` is nog niet
onderbouwd. Ontvangen warmhoudstatus blijft leesbaar; bediening vereist voorlopig
geadverteerde variabele ondersteuning. De onderzochte X PURE meldt die wel.

De Assist-starts volgen de bewezen standaardparameters uit een anoniem
uitgelezen catalogus en de appcode. De integratie haalt deze gegevens niet
zelf van internet en biedt geen eigen timer of temperatuur bij deze starts.
Zie [ASSIST-PRESETS.md](ASSIST-PRESETS.md) voor de vier programma's, de
fysieke bevestiging en de bijzondere index- en timerwaarde nul.

De opgeslagen appfavorieten hebben daarnaast drie aparte sensoren voor
plaatsen 3–5 en een knop **Refresh saved Assists**. Deze gebruiken één
expliciete leesvraag en zijn ook met bediening uit beschikbaar. Onbekende
programma's en dubbele plaatsnummers worden herkenbaar weergegeven;
verbindingsverlies of een mislukte uitlezing wist de vorige waarden.
De gegevens starten of wijzigen niets. Zie [SAVED-ASSISTS.md](SAVED-ASSISTS.md)
voor momentopnamen, leesdatum en de afzonderlijke grens rond opslagbediening.

## Kookplaat en instellingen

| Entiteit of functie | Voorwaarden en gedrag |
| --- | --- |
| Pauzestatus, kinderslotstatus | Monitoring. |
| Pauze en kinderslot bedienen | Kookbediening; kinderslot gebruikt de bekende vergrendelingsenums. |
| Reinigingsslotstatus, simple-mode-status | Monitoring; `pure`-status vereist. |
| Reinigingsslot, permanent kinderslot, automatische pandetectie | Kookbediening en `pure`-status. |
| Signaalvolume | Algemene bediening; uitsluitend descriptorlabels en indices. |
| Aanraakgevoeligheid | Algemene bediening en `pure`-status; langzaam, standaard of snel volgens het schema. |
| Maximale bedrijfsduur | Kookbediening en `pure`-status; enumkeuzes `default`, `high` en `max`, zonder onbewezen tijdseenheid. |
| Functies in simple mode | Kookbediening en aanwezige groep instellingen. Afzonderlijke schakelaars voor reinigingsslot, pauze, warmhouden, timer en sneltoets. Dit schakelt de functie binnen simple mode in of uit, niet simple mode zelf. |
| Foutcodes | Diagnostische teller, ruwe codes en bekende SDK-labels. Geen afgeleide oorzaak of reparatieadvies. |
| Connectiviteit, herstelstatus, gereed voor slaap | Diagnostiek. `ready_for_sleep` is geen betrouwbare fysieke aan/uitindicator. |
| Filter vervangen nodig | Binaire monitoring voor expliciete recirculatie. De onderbouwde appdrempel is resterende raw waarde nul; onbekend type of afwijkende waarde blijft onbekend. Geen uren of percentage. |

Een wijziging van een simple-mode-functie wordt onder dezelfde apparaatlock
samengevoegd met de andere vier velden uit de laatste status. Zo sturen twee
gelijktijdige wijzigingen niet elk een verouderde volledige groep terug.
Alle bedieningsopdrachten worden gevalideerd en door een statusuitlezing gevolgd.
Alleen de waargenomen relevante waarde kan de opdracht bevestigen. Een afwijking
of ontbrekende waarde geeft een melding dat de opdracht nog niet bevestigd is,
terwijl de beschikbare werkelijke status zichtbaar blijft. Er volgt geen retry;
een latere statusstream kan de verandering alsnog melden. CSF stoppen is pas
bevestigd wanneer een bekende andere zonemodus wordt waargenomen. Dat bewijst
op zichzelf niet dat de zone niet meer verwarmt; haar vermogen blijft afzonderlijk
zichtbaar. Deze vergelijkingen zijn offline getest, niet op hardware.

## Diagnostiek

De standaard uitgeschakelde knop **Refresh diagnostics** is ook beschikbaar
met beide bedieningsopties uit. Na expliciet indrukken vraagt hij eenmalig
optionele Wi-Fi-status, heartbeatstatus en -periode, opgeslagen CSF-gegevens en
systeem- en gebruikersgebeurtenissen op, met een aangevraagde limiet van 20 per
lijst. Niet ondersteunde methoden krijgen een afzonderlijke status; ze zijn
geen reden om verzonnen meetwaarden te tonen. Dit is geen periodieke gebeurtenisverzameling.

Home Assistants diagnose-download exporteert alleen de reeds aanwezige cache;
downloaden veroorzaakt zelf geen BLE-verkeer. Bekende identificerende en
geheime velden worden geredigeerd. Controleer een export voor openbaar delen,
zeker bij nieuwe firmware of nog onbekende velden.

## Bewust nog niet als bediening aangeboden

- **Timerbediening:** zonetimerstatus is nu in seconden beschikbaar. De eenheden
  van de afzonderlijke settervelden, limieten en de kookwekker blijven open.
  Daarom nog geen tijdinvoer; zie [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md).
- **Filterlevensduur:** de appwaarschuwing is beschikbaar onder de voorwaarden
  uit [FILTER-EVIDENCE.md](FILTER-EVIDENCE.md). Ruwe status en descriptormetadata
  geven nog geen uren, percentage, vervangdatum of resetbetekenis. Het lijstje
  filtertypen bewijst niet welk filter gemonteerd is.
- **Bridge aan/uit:** de codec voor twee zone-identiteiten is bekend; veilige
  unbridge-semantiek en fysieke werking zijn niet gevalideerd. Geen HA-bediening.
  De onderzochte `bridgeSelectedAction` in de app leidt via `SelectZones` naar
  een lokale selectie van twee zones. Dat pad alleen bewijst geen BLE-opdracht.
- **Overige CSF-starts en wijzigen:** de vier catalogusstarts hierboven zijn
  voorbereid; andere types, eigen parameters, actieve programmawijzigingen en
  opgeslagen presets blijven open. Het opslagpad schrijft seconden zonder
  omzetting, terwijl het startpad naar milliseconden converteert. Zie
  [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md). Alle starts vereisen passende
  mogelijkheden per zone; een globaal programmalabel bewijst geen zonesupport.
- **LED-, dealer-, Wi-Fi-provisioning-, firmware-, reset- en debugwrites:** niet
  aangeboden. Er is geen algemene service om willekeurige RPC's te versturen.
- **Energie en draaiuren:** geen bewezen meetmethode gevonden; heartbeatcounters
  en gebeurtenisnamen worden niet als zulke sensoren gepresenteerd.

[APP-COVERAGE.md](APP-COVERAGE.md) vergelijkt deze voorbereiding met de bredere
appfuncties. Het hulpmiddel uit [READONLY-PROBE.md](READONLY-PROBE.md) kan een
latere, afgesproken uitleesproef ondersteunen; het heeft alleen offline tests
doorlopen en is niet op hardware uitgevoerd.
