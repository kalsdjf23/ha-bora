# Filterwaarschuwing: wat wel en niet vaststaat

Aanvullende statische analyse op 26 september 2026 van BORA One 1.9.1,
build 130922. De app is hiervoor niet uitgevoerd en er is geen nieuwe
apparaatverbinding gemaakt.

## De waarschuwing is onderbouwd

De Pure-statusmapper leest `remainingFilterLifetime` en zet de boolean
`shouldChangeFilter` als de waarde kleiner is dan 1. De Swift-weergave
gebruikt die boolean voor de melding dat het geurfilter vervangen moet
worden. Dit is een gevolgde gegevensketen van statusveld naar melding,
geen interpretatie van alleen een RPC-naam.

De beslissende arm64-adressen zijn `0x1010dd85c–0x1010dd864` voor het
lezen en vergelijken, `0x1010de434–0x1010de438` voor opslag van de boolean
en `0x10009b0f8–0x10009b108` voor de Swift-waarschuwingsbranch.

## Gedrag in Home Assistant

De binaire sensor **Filter replacement required** heeft geen bedieningsoptie
nodig. Hij gebruikt uitsluitend de laatste ontvangen Pure-instellingen:

- Bij expliciete recirculatie (`extraction_type=1`) en resterende waarde
  nul is de melding aan. Positieve waarden tot en met `0x7fffffff` geven uit.
- Bij afvoer naar buiten, een onbekend type, ontbrekende dealerconfiguratie
  of een afwijkende waarde blijft de melding onbekend.
- Zonder Pure-status of beschikbare verbinding is de sensor onbeschikbaar.

Deze beperking tot bekende recirculatie is een keuze van de integratie.
De onderzochte appvergelijking en lokale waarschuwingsbranch hebben zelf
geen extra check op het afzuigtype; een bovenliggende schermvoorwaarde is
niet uitgesloten. Daarom wordt geen vervangadvies voor afvoer naar buiten
afgeleid uit alleen een nulwaarde.

Het protocolveld is uint32, maar de app vergelijkt een signed Int. De
betekenis van waarden vanaf `0x80000000` is onbekend. Die worden niet
omgezet in een negatieve levensduur of een vervangmelding. Een ontbrekend
heel Pure-bericht wordt evenmin nul; een ontbrekende scalar in een wel
aanwezig protobufbericht heeft volgens dat schema zijn normale nuldefault.

## Nog open

Dit bewijs geeft geen eenheid voor `remainingFilterLifetime` of
`FilterUnit.lifetime`. Er worden geen resterende uren, percentages of
voorspelde vervangdatums berekend. Een lijst ondersteunde filtertypen
bewijst niet welk filter gemonteerd is. De betekenis van filterreset blijft
onbekend en er is geen resetknop toegevoegd.

Ook alle eerdere lokale protocolopnamen zijn hierop gecontroleerd. Er zijn
slechts twee filterwaarden: 7234 en 7230, ontvangen met 150,002 seconden
tussenruimte. De exacte actieve bedrijfsduur en interne updatefrequentie
zijn niet vastgelegd. Deze daling bewijst dus geen minuten, uren of andere
tijdseenheid en wordt niet tot een resterende gebruiksduur omgerekend.

De drempel, onbekende waarden en HA-beschikbaarheid zijn offline getest.
De melding moet nog met de echte app en de kookplaat worden vergeleken;
het apparaatfilter is tijdens deze voorbereiding niet gereset.
