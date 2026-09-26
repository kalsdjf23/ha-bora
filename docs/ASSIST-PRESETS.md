# Vier voorbereide X PURE Assist-programma's

De integratie bevat nu een vaste selectie van vier programma's uit de
[openbare BORA-catalogus](https://boraone-backend.k8s-prd.cloud.bora.com/v1/automatic-programs?pimProductId=61596&page=1&pageSize=20).
Die leesvraag gaf op 25 september 2026 HTTP 200 zonder account, cookies of
authenticatieheader. Dit was een catalogusvraag, geen apparaatbediening.
De integratie gebruikt de vastgelegde metadata lokaal en doet zelf geen
catalogus- of accountverzoeken.

| Programma | Catalogus-ID | Standaarddoelwaarde |
| --- | --- | --- |
| Cook egg dishes | 62176 | 135 °C |
| Fry potato dishes | 62954 | 205 °C |
| Fry pancakes | 63120 | 180 °C |
| Fry breaded foods | 63121 | 170 °C |

Deze waarden zijn programma-instellingen, geen gemeten pantemperaturen.
Alle vier gebruiken FRYING. Ze hebben catalogusgrenzen 120–220 °C; de eerste
twee hebben stapwaarde 15 en de laatste twee 10. De integratie kopieert geen
receptinstructies of afbeeldingen. De noodzakelijke feiten staan in een
[geschoonde fixture](../tests/fixtures/x_pure_catalogue_2026_09_25.json).

## Voorbereide bediening in Home Assistant

Deze bediening is uitsluitend in simulatie getest. De eerste fysieke proef
met de HA-adapter en de kookplaat moet nog plaatsvinden.

1. Schakel zowel algemene bediening als kookbediening in de integratieopties in.
2. Kies bij de gewenste zone een **Assist to start**. Die keuze blijft lokaal;
   kiezen verstuurt geen apparaatopdracht. Er is geen standaardselectie en een
   herladen integratie begint weer zonder selectie.
3. Druk expliciet op **Start Assist**. De zone moet een bekende uitstand hebben
   en ongekoppeld zijn. De client leest dit opnieuw voordat hij de opdracht verstuurt.
4. Volg de fysieke Assist-bevestiging op de kookplaat. De integratie slaat die
   stap niet over en zet een ontvangen bevestigingsfase niet zelf door.

Een bestaande actieve zone of kookfunctie wordt via deze startknop niet
gewijzigd. De gewone programmastatus blijft de werkelijk ontvangen fase tonen.
De bestaande knop om een kookprogramma te stoppen blijft afzonderlijk
beschikbaar. Deze presets voegen geen automatische stop na een gekozen tijd
toe; de HA-start gebruikt de standaardwaarden van het gevonden apppad.

De sensoren **Cooking program phase** en **Assist confirmation required**
volgen de ontvangen apparaatstatus. De eerste toont ook `inactive` als een
bekende andere zonemodus actief is. Een onbekende fase geeft geen valse
melding dat bevestiging niet meer nodig is. De temperatuur van **Assist
target temperature** is uitsluitend de gerapporteerde instelling van een
herkenbaar programma; het is geen gemeten pantemperatuur. Een lokale andere
keuze verandert deze sensoren niet. Zonder herkenbaar programma of geldige
doelwaarde verschijnt geen temperatuur.

## Onderbouwing van de bijzondere waarden

De app haalt deze records op met een vaste productfilter `61596` en gebruikt
het numerieke catalogus-ID rechtstreeks als `csfId`. De productiecaller schrijft
bij een nieuwe start `csfIndex=0`, ook al noemt de apparaatdescriptor voor zijn
indexrange 1–5. De startcode neemt hier de aantoonbare appwaarde over en verandert
die niet in een opgeslagen-programmaslot.

Deze vier records hebben geen afzonderlijke timerstap of sliderconfiguratie.
Ontbrekende uur/minuut/secondevelden worden null en daarna nul seconden. De
mapper verbergt het timerscherm; de start-VM begint eveneens met nul seconden
en schrijft die via zijn millisecondenconversie als `csfTimerDuration=0`.
Dit is een concrete appstartuitzondering voor deze vier records, geen algemene
betekenis van timerwaarde nul. De ruwe CSF-timergrens 10.000–7.250.000 uit de
opname wordt hierdoor niet hernoemd of gewijzigd.

`csfSettings=0` volgt uit de productieconversie `!cooktopTimer`, met
`cooktopTimer=true` in alle vier records. De andere catalogusvlag
`userTimerstart` is een apart veld en is niet de bron van deze bitwaarde.
Bij één geselecteerde zone behoudt de startcaller FRYING; hij verandert dat
pas bij twee geselecteerde zones in GRILL. Deze voorbereiding biedt alleen
de enkele zone aan, zonder een bridge- of unbridgeopdracht.

De opgenomen X PURE meldt FRYING voor alle vier zones, doelgrenzen 120–240
en stapgrenzen 1–120. De code controleert de gekozen zone, het producttype en
de volledige receptgrenzen opnieuw. Hij legt geen verzonnen stapraster op:
de echte cataloguswaarde 205 past immers niet in `120 + n × 15`.

## Grenzen van de implementatie

De runtime accepteert alleen de exacte standaardstart van deze vier records,
op X PURE-producttype 2 met passende capabilities. Een andere temperatuur,
duur, index, bitwaarde, recept-ID of programmavariant wordt geweigerd. De
aanwezigheid van een lage-niveau encoder is geen generieke HA-startservice.

Voor en na de enkele schrijfopdracht worden de statussen gelezen. Alleen een
passend CSF-bericht in fase preheat, confirmation-required of active bevestigt
dat het programma wordt gerapporteerd. Dit bewijst geen bereikte temperatuur,
afgeronde fysieke bevestiging of voltooid kookproces. Bij een ontbrekende of
afwijkende teruglezing volgt een melding; de opdracht wordt niet herhaald.
Verbindingsherstel verstuurt evenmin een start uit de lokale selectie.

Een zone wordt al vóór het wachten op andere Bluetooth-operaties voor deze
start gereserveerd. Een gelijktijdige tweede start wordt geweigerd en niet
als latere opdracht bewaard. Vanaf het verzendmoment blijft een onzekere
start bovendien geblokkeerd na een fout, annulering of opnieuw verbinden.
Alleen een later ontvangen CSF-status met de bijbehorende parameters en fase
preheat, confirmation-required of active heft die onzekerheid op; de gewone
controle tegen het wijzigen van een actief programma blijft dan gelden.

Een teruggelezen uitstand bewijst niet dat een vertraagde start nooit meer
wordt toegepast. Daarom heft die uitstand de blokkade niet op. Als de eerste
opdracht werkelijk niet is toegepast, kan de zone tijdens deze clientinstantie
geblokkeerd blijven voor nieuwe Assist-starts. Deze bewaking is niet persistent
over het herladen van de integratie of een HA-herstart; herladen is geen
bevestiging van de apparaatstatus. Controleer na een onzekere start altijd
de kookplaat voordat opnieuw starten wordt overwogen.

Opgeslagen Assists, eigen parameters, andere CSF-types, wijzigen tijdens een
actief programma en de bridgeworkflow blijven afzonderlijk onderzoek. De
opslag-/startafwijking uit [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md) wordt hier
vermeden door concrete catalogusgegevens te gebruiken, niet door opgeslagen
parameters opnieuw te verzenden. Geen van deze vier starts is tijdens deze
voorbereiding op de echte kookplaat uitgevoerd.
