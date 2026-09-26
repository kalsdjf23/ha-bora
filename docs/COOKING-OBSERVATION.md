# Kookmeting van 26 september 2026

De gebruiker vroeg om tijdens het koken mee te kijken en bevestigde daarna
linksachter op stand 7 en de afzuiging op 3. De zelfstandige Python-client
las vanaf een eerder gekoppelde Mac ongeveer zes minuten mee.
Hij gebruikte de integratieprotocolcode met een allowlist van statusvragen,
drie statusabonnementen en periodieke reads. Er zijn geen standen gewijzigd,
pairinghandelingen uitgevoerd of opdrachten naar Home Assistant gestuurd.

## Wat is waargenomen?

| Gebeurtenis | Ontvangen gegevens |
| --- | --- |
| Begin | Vier zones en afzuiging op 0. |
| Koken | Linksachter veranderde via 3 naar 7; afzuiging via 4 naar 3. De gebruiker bevestigde zone 7 en afzuiging 3. |
| Naloop start | Afzuiging op 1 met 1.800.000 ms resterend, dus 30 minuten. |
| Zone uit | Linksachter meldde expliciet vermogen 0, ongeveer zes seconden na het begin van de naloop. |
| Aftellen | Naloop daalde met 5.000 ms per ongeveer vijf seconden, tot 1.760.000 ms in de laatste waargenomen streamupdate. |
| Uitleesfout | Een zonestatusvraag kreeg code 14 (`UNAVAILABLE`), nadat afzuiging en kookplaatstatus nog geldig waren uitgelezen. |
| Afsluiten | Alle drie statusabonnementen werden gestopt en Bluetooth werd afgesloten. De gebruiker bevestigde kookplaat uit met naloop en vroeg de meting af te ronden. |

De opname bevat 93 CRC-geldige responses, waaronder 16 echte streamupdates
van zones en afzuiging. De kookplaatstream startte, maar leverde tijdens deze
meting geen CONTINUE-bericht; kookplaatstatus kwam uit periodieke vragen.
Geen bericht leverde positief restwarmtebewijs. Geen temperatuurmeting,
timer-, Assist- of bridgebediening is getest. De naloop is niet tot nul gevolgd.

Vier geschoonde responsepayloads staan in
[de kookfixture](../tests/fixtures/x_pure_cooking_2026_09_26.json).
Apparaatidentifiers, systeeminformatie en privéopnamen zijn niet meegenomen.
De fout hoort volgens de vaste verzoekvolgorde bij `GetZoneStatus(front_left)`;
de opname bevat geen verzonden RPC-paden. De precieze firmwareoorzaak is onbekend.

## Verbetering naar aanleiding van de meting

De oude client liet de zonestatusfout de hele refresh afbreken. De nieuwe
verwerking maakt bij een geldige unary-code 14 alleen de betreffende zone
onbekend en leest de andere bronnen verder uit. Onbekend wordt geen uitstand.
Een later geldig zonestatusbericht kan de zone weer beschikbaar maken.

Fout en herstel worden in ontvangstvolgorde verwerkt, zodat een nieuwere
streamstatus niet alsnog door de wachtende foutafhandeling wordt gewist.
Een echte disconnect blijft een fout, ook vlak na de laatste response.
Andere RPC-fouten, ongeldige berichten en timeouts houden hun eerdere gedrag.

Zonebediening controleert onder dezelfde lock of actuele zonestatus aanwezig
is. Een reeds wachtende opdracht kan daardoor niet alsnog een inmiddels
onbeschikbare zone bedienen. Een ontbrekende teruglezing bevestigt geen opdracht.

Deze correctie is offline getest, inclusief HA-coordinator- en entiteitsgedrag,
beide berichtvolgordes en verbindingsverlies. Een later afzonderlijk toegestane
[uitleesproef](HARDWARE-CHECKS.md) met de nieuwe client verliep zonder fouten.
**Code 14 trad daarbij niet opnieuw op:** het herstel van deze specifieke fout
blijft alleen offline getoetst. Dit is ook geen bewijs voor HA/Linux-pairing,
proxyondersteuning of fysieke bedieningscommando's.
