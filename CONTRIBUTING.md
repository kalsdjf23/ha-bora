# Bijdragen

Dit is voorlopig een privéontwikkelproject op GitHub. Openbare publicatie en
releases volgen pas na een aparte opdracht. Gebruik Python 3.14; de vastgezette testomgeving gebruikt
Home Assistant 2026.9.3.

```sh
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements-test.txt
ruff check .
pytest -q --cov=custom_components.bora --cov-report=term-missing
```

De tests gebruiken geselecteerde opnames en gesimuleerde BLE-verbindingen.
Ze maken geen verbinding met een kookplaat. Houd nieuwe tests eveneens
vrij van echte hardware, adapters en productie-Home Assistant.

Protocolcode staat onder `custom_components/bora/ble/` en importeert Home
Assistant niet. Bewaar Protobuf-aanwezigheid, descriptorlimieten en onbekende
waarden; behandel afwezige status nooit als bevestigde uitstand. Een
bedieningsopdracht mag niet automatisch worden herhaald, ook niet na timeout.

Documenteer bij elke nieuwe functie afzonderlijk:

1. Het bronbewijs voor pad, berichtstructuur en eenheden.
2. De door het concrete apparaat geadverteerde mogelijkheden.
3. De geslaagde offline tests en eventueel uitgevoerde fysieke proef.

Een fysieke bedieningsproef vereist een aanwezige gebruiker en een vooraf
begrensd testscenario met controle van de eindtoestand. Laat geen onderzoek-
client of onbegrensde observatie achter. Firmware, reset- en dealeracties
horen niet bij gewone HA-bediening.

Voeg geen officiële appbestanden, toegangstokens, serienummers, SSID's,
hostspecifieke Bluetooth-ID's of ruwe privéscans toe. Gebruik gecachete,
geredigeerde HA-diagnostiek bij een later probleemrapport; kijk de export
zelf na voordat je die openbaar deelt.
