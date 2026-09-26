# Dekking van app- en apparaatfuncties

Dit overzicht bewaakt het einddoel: een brede lokale integratie voor normaal
gebruik in Home Assistant. Het vervangt geen hardwaretest. "Voorbereid"
betekent geïmplementeerd en offline getest; de HA-adapter en bedieningen
moeten nog op het echte apparaat worden gecontroleerd.

## Appfuncties tegenover de integratie

BORA beschrijft in de [appinformatie](https://www.bora.com/en-int/products/products/supplies-and-accessories/app/joy)
een apparaatstatusoverzicht, apparaatmetadata, Assist-programma's en het
personaliseren van opgeslagen Assists. Receptinspiratie, gebruikersprofielen,
favoriete recepten en de winkel zijn daarnaast appfuncties. Die laatste
groep is geen lokale kookplaatbediening en hoort niet bij deze BLE-integratie.

| Gebied | Lokale HA-voorbereiding | Werk tot het volledige doel |
| --- | --- | --- |
| Statusoverzicht | Afzuiging, zones, modi, restwarmte, instellingen en fouten; aparte Assist-fase, bevestigingsmelding en bekende doeltemperatuur | Actieve zones en streams op HA fysiek vergelijken |
| Afzuiging | Vermogen, automatisch/boost, naloop en stoppen | Code 12 uit de handmatige bedieningsproef aan de exacte RPC koppelen; werkelijke acceptatie van bediening controleren |
| Kookzones | Vermogen, warmhouden, aankookautomaat, pauze en CSF stoppen | Elke bedieningsroute met aanwezige gebruiker bevestigen |
| Timers | Codecs plus zonetimerduur, resterende tijd en actief-status | Settereenheden en werkelijke start/stopwerking controleren |
| Instellingen | Sloten, signaalvolume, aanraking, pandetectie, bedrijfsduur en simple-mode-functies | Betekenis en ondersteuning op dit model bevestigen |
| BORA Assist starten/wijzigen | Vier concrete X PURE-catalogusstarts, lokale keuze en aparte startknop; exacte parameters en controles voorbereid | Fysieke werking/bevestiging toetsen; overige programma's en actief wijzigen onderbouwen |
| Opgeslagen Assists | Aparte uitleesknop en sensoren voor slots 3–5; gedeeld met diagnostiek. App-savepad gereconstrueerd | Echte uitlezing bevestigen; firmwaregedrag bij weggelaten slots en behoud van slots 1–2 toetsen vóór opslagbediening |
| Zones koppelen | Bridge-status en codec; de onderzochte appselectie bewaart twee zones lokaal | Werkelijk BLE-koppel-/ontkoppelpad en firmwaregedrag vaststellen |
| Filterstatus | Onderbouwde binaire vervangmelding voor bekende recirculatie; ruwe levensduur en typen beschikbaar | Eenheid van de BLE-status, resetbetekenis en fysieke melding vaststellen |
| Metadata | Model, versies en geredigeerde diagnostiek | Meer modellen en eerste Linux-pairing controleren |
| Wi-Fi en gebeurtenissen | Optionele status/historie in diagnose-download | Alleen onderbouwde informatie als gewone HA-entiteit toevoegen |
| Firmware | Versie zichtbaar; geen updater | Updateworkflow niet als generieke schrijfopdracht aanbieden |

## Aanvullend gedrag uit de handleiding

De officiële [X PURE-handleiding, versie 03](https://www.bora.com/product-documentation/operating-and-installation-instructions/umim-xpure-en.pdf)
beschrijft in §7.4 een Assist-start vanuit de app met bevestiging op de
kookplaat. Een toekomstige HA-actie moet die bevestiging behouden. §7.6
beschrijft dat het beëindigen van een programma van het gekozen programma
afhankelijk is. Een verzonden verzoek bewijst dus geen beëindigde kookcyclus.

Deze handleiding beschrijft productgedrag, geen BLE-velden. Het filtermenu
gebruikt bijvoorbeeld een percentage, terwijl de [officiële filterinformatie](https://www.bora.com/en-int/service/x-pure-v24)
voor PUAKF een nominale levensduur van ongeveer 150 gebruiksuren noemt.
Geen van beide bewijst afzonderlijk de eenheid van het BLE-veld
`remainingFilterLifetime`.

Een aparte appanalyse onderbouwt inmiddels wel de waarschuwing bij nul.
De eenheid blijft onbekend; zie [FILTER-EVIDENCE.md](FILTER-EVIDENCE.md).

BORA's [Data Act-informatieblad](https://www.bora.com/product-documentation/eu-data-act/bora_pure_range_data_act_information_sheet-en.pdf)
van 8 oktober 2025 noemt opvraagbare apparaatgegevens, maar geen beschikbaar
realtime gegevensaanbod. Dat biedt op zichzelf geen vervanging voor de lokale
BLE-statusroute. Er is geen contactverzoek of aanvraag namens de gebruiker
verstuurd.

## Uitbreidingsgrenzen

Geen willekeurige RPC-service, reset-, dealer-, provisioning- of
firmwareschrijfknop. Zulke methoden staan in de lokale onderzoeksinventaris,
maar mogen geen ongedocumenteerde neveneffecten achter een HA-actie verbergen.
Een ontbrekende of onbegrepen functie blijft herkenbaar open; een geslaagde
codec-test alleen wordt niet als werkende apparaatfunctie afgevinkt.

Publiceren, GitHub Releases en HACS-aanmelding blijven een latere opdracht.
De nieuwe catalogusroute gebruikt vastgelegde metadata, zonder runtimeaccount
of cloudaanroep; zie [ASSIST-PRESETS.md](ASSIST-PRESETS.md).
Zie [FEATURES.md](FEATURES.md), [VALIDATION.md](VALIDATION.md) en
[PUBLISHING.md](PUBLISHING.md) voor de huidige implementatie en testgrenzen.
