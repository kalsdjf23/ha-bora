# Begrensde uitleesproef voor een later testmoment

`scripts/readonly_probe.py` is een ontwikkelhulpmiddel voor een aanwezige
gebruiker. De CLI en rapportworkflow zijn met gesimuleerde peers getest.
De read-only verbindingsklasse is daarnaast gebruikt door een afzonderlijke
[live kookmonitor](COOKING-OBSERVATION.md); de volledige CLI/rapportworkflow
is nog niet op hardware uitgevoerd.

Hij maakt expliciet verbinding met één opgegeven Bluetooth-identiteit, leest
metadata en status, volgt maximaal vijf minuten de gewone statusstreams en
schrijft daarna een geredigeerd JSON-verslag. De verbinding wordt ook bij een
fout of annulering lokaal afgesloten. Als de Bluetoothbackend zelf vastloopt,
kan een afgebroken disconnect geen bevestigde radiodisconnect garanderen.

De RPC-allowlist bevat alleen bekende status- en diagnosevragen. Bedieningen,
firmware, resets en de afzonderlijke gebruikersbevestigings-RPC worden
geweigerd. OS-pairing is apart en standaard uit; `--pair` staat dit expliciet
toe. Deze tool kan geen afzuiging of verwarming starten.

## Voorbereide opdrachten

Voer deze pas uit tijdens een afgesproken fysieke proef. Gebruik Python 3.14
en een Bluetoothadapter van de machine waarop het commando draait:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install bleak-retry-connector==4.7.0
.venv/bin/python scripts/readonly_probe.py \
  --address '<BLUETOOTH-ID>' --seconds 30 --output probe-status.json
```

Voor een nieuwe adapter: voeg `--pair` toe en bevestig de gewone pairingvraag
op de kookplaat/host als deze verschijnt. Voor de zes optionele diagnosevragen:
voeg `--extended` toe. Dit omvat ook `GetSavedCsf`; een niet ondersteunde
methode wordt als zodanig in het verslag opgenomen. Gebruik steeds een nieuwe
bestandsnaam. Bestaande bestanden worden niet overschreven.

Het verslag bewaart de afgeronde diagnosevragen ook nadat de verbinding is
afgesloten en de live favorietencache is gewist. Persoonlijke identifiers en
netwerkadressen worden geredigeerd; een ontbrekend numeriek adres met waarde
0 laat gewone nulstanden, timers en programmaparameters intact.

Onder `diagnostic_snapshot.probe.request_trace` staan de pogingen met hun
volgnummer, verzoek-ID, RPC-pad en — bij een zonevraag — de zone-UID. De uitkomst
bevat alleen het antwoordtype/fouttype en de numerieke foutcode; geen ruwe
antwoordbody of fouttekst. Zo kan bijvoorbeeld code 14 direct aan
`GetZoneStatus(front_left)` worden gekoppeld, zonder die koppeling uit de
pollvolgorde af te leiden. Stream-starts en de afsluitende STOP-pogingen staan
in dezelfde lijst. De eerste en laatste pogingen blijven bewaard tot maximaal
100 rijen; `total` en `omitted` maken ontbrekende tussenliggende rijen zichtbaar.

Een geregistreerde poging bewijst niet dat alle bytes het apparaat bereikten.
`response` betekent dat het transport een antwoord ontving; een onjuiste
streammarker of statusbody kan daarna nog worden afgekeurd. `cancelled` en
fouten zonder antwoordcode krijgen geen verzonnen apparaatantwoord. Deze
registratie is offline getest, ook voor zonecode 14 en streamafsluiting.

Dit is een zelfstandige BLE-proef, geen HA-installatie en geen
Bluetooth-proxytest. De uiteindelijke integratie gebruikt afzonderlijk de
Bluetoothmanager van Home Assistant.

## Gerichte open vragen

- Vergelijk een handmatig ingestelde zonetimer met duur/resterende tijd in de
  opname. De appcode onderbouwt milliseconden voor deze statusvelden.
- Vergelijk de kookwekker apart. Het gemeenschappelijke Protobuf-type alleen
  is nog geen onafhankelijk getoetste uitlezing of setter-eenheid.
- Lees opgeslagen Assists naast de in de officiële app weergegeven looptijd.
  De onderzochte save- en startpaden gebruiken verschillende conversies voor
  hetzelfde parameterveld. Een opname moet vaststellen wat `GetSavedCsf`
  teruglevert voordat een opgeslagen programma kan worden hergebruikt.
- Vergelijk filterstatus met het fysieke menu zonder te resetten of waarden
  te schrijven. Een nominale levensduur van een filter bewijst niet de eenheid
  van het resterende-levensduurveld.

Een statusopname bewijst geen settergedrag. Deze tool verstuurt daarom geen
bedieningsexperimenten. Bekijk het verslag voor het later delen; de export
redigeert bekende identificerende gegevens en neemt geen ruwe foutteksten op.
