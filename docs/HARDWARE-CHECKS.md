# Begeleide hardwareproeven van 26 september 2026

Deze proeven gebruiken de protocolclient op een eerder gekoppelde Mac en één
BORA X PURE PUXU2R met BLE-firmware 3.0.9. De gebruiker heeft de proeven vooraf
toegestaan. Dit is geen test van de HA-adapter, Linux-pairing of een proxy.
Privéverslagen worden buiten deze repository bewaard.

## Uitlezen in rust

De rapportworkflow van `scripts/readonly_probe.py` is 60 seconden gevolgd na
initialisatie, zonder pairing, uitgebreide diagnosevragen of bediening.
Beide volledige statusrondes meldden alle vier zones en afzuiging in
handmatige vermogensstand 0.

De verzoekregistratie bevat twintig pogingen, zonder weggelaten rijen:

- Twee metadatavragen en twee volledige statusrondes van zes vragen.
- Drie gestarte statusstreams met START-bevestiging.
- Drie STOP-bevestigingen bij het afsluiten.

Alle twintig antwoorden hadden code 0. Het rapport eindigde met `completed`,
zonder fout; de verbinding was na opruiming lokaal gesloten. Het proces is
beëindigd en er is geen monitor achtergebleven.

Dit bewijst dat de nieuwe verzoekregistratie en normale rapportworkflow op
de gekoppelde Mac werken. Code 14 kwam in deze proef niet voor; herstel na
die specifieke firmwarefout blijft daardoor alleen offline getoetst. Deze
proef test ook niet `--pair`, de optionele diagnosevragen of afgebroken
verbindingen tijdens de rapportworkflow.

## Afzuigproef: eerste verbindingspoging

Voor de afzonderlijk afgesproken proef 0 → 1 → 0 was het apparaat bij de
eerste verbindingspoging niet bereikbaar. De initialisatie eindigde met
`ConnectionLost`, vóór de controle van de beginstatus en vóór een
bedieningsopdracht. De client werd afgesloten. Dit is geen geslaagde
afzuigproef en levert geen nieuw bewijs voor fysieke bediening.
