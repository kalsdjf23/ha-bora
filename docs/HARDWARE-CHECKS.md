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

## Afzuigproef na opnieuw inschakelen

Na bevestiging van de gebruiker lukte de verbinding. De beginstatus meldde
alle vier zones en de afzuiging in handmatige stand 0. De proef liet alleen
bekende leesvragen en `SetExtractorMode` voor stand 1 of 0 toe.

De fase voor stand 1 eindigde met RPC-code 12 (`UNIMPLEMENTED`). De eenmalige
uitschakelfase voor stand 0 eindigde eveneens met code 12. Er is geen opdracht
herhaald, er zijn geen zones bediend en de verbinding is afgesloten.

**De fout is nog niet sluitend aan één RPC gekoppeld.** Het proeflog bevat
fases, maar geen per-RPC pad of request-ID. De eerste fase bevat de schrijfopdracht
en een afzuigstatusvraag; de uitschakelfase bevat de schrijfopdracht en de
gebruikelijke statusvragen. Dit bewijst geen succesvolle bediening en ook
niet dat uitsluitend `SetExtractorMode` code 12 terugstuurde.

Een afzonderlijke uitleesproef direct daarna gaf twee volledige statusrondes
met alle vier zones en de afzuiging op 0, zonder fouten. Ook die verbinding
is afgesloten. Dit bevestigt de eindtoestand, geen geslaagde uitschakelopdracht.

De statische appanalyse bevestigt het pad en de berichtvorm voor handmatige
standen 1 en 0. Een geadverteerde vermogensmodus en standenlijst bewijzen geen
ondersteuning van de setter. De volgende gerichte proef moet de exacte RPC
aan de fout koppelen; er is geen grond om willekeurige payloads, handshakes
of andere bedieningen te proberen.
