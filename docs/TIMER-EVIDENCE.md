# Bewijsgrenzen voor timers en kookprogramma's

Aanvullende offline analyse van BORA One 1.9.1, build 130922. Dit document
beschrijft eigen bevindingen uit gebruikscode, geen opnames van nieuwe
bedieningsproeven.

## Bewezen conversies

| Veld of gebruik | Onderbouwing | Gebruik in HA |
| --- | --- | --- |
| `ZoneStatus.settings.timer.duration` en `remaining` | Pure CPC-mapper `toCPCAssistFunction` leest beide velden en roept `toDuration(Int, MILLISECONDS)` aan. | Zonestatus als seconden tonen; ruwe data behouden. |
| `CsfParameter.csfTimerDuration` bij starten | Preset-startpad zet geselecteerde seconden via `inWholeMilliseconds` om en schrijft veld 11. | Bewijs voor die startparameter; geen algemene verklaring over alle timer-RPC's. |
| `remainingAfterRun` | Eerdere echte countdownopnamen. | Resterende naloop in seconden. |

De zonetimerconversies staan bij arm64-adressen `0x101448624` en
`0x1014486a0`; het presetpad bij `0x10130ac68–0x10130ad08`. De objectvelden
zijn getoetst aan de Timer-, ZoneSettings- en ZoneStatus-constructors en de
werkelijke Kotlin DurationUnit-objecten. Alleen een gevonden naam of een
plausibele waarde is niet als bewijs gebruikt.

Nog afzonderlijk te onderbouwen: de gewone `SetTimer`- en `SetEggTimer`-
requesteenheden, timerlimieten, het aparte gebruik van de kookwekker en
filtereenheden. Die worden niet automatisch uit een statusveld afgeleid.

Ook de afzonderlijk onderzochte `SetTimerState`- en `SetEggTimerState`-
berichten bewijzen nog geen start/pauze/hervatgedrag. Hun boolean kan zonder
duurveld worden verstuurd, maar er is geen appaanroep gevonden die behoud
of wissen van de resterende tijd vastlegt. Daarom wordt evenmin een
pauze-/hervatknop afgeleid uit alleen de veldnamen.

## Waarom opgeslagen Assists nog niet worden gestart

De startworkflow gebruikt een catalogus-programma-ID, niet het CSF-type als
ID. De app schrijft index 0 voor een tijdelijke start. De onderzochte
instellingsbit 0 betekent automatisch starten van de timer; dit bewijst geen
automatisch overslaan van bevestiging op de kookplaat.

Er is bovendien een concrete conversieafwijking: de favorites-savehelper
`toCsfParameter` (`0x1012d1ff8`) schrijft de uit de catalogus afgeleide
`ProgramTimer.defaultSeconds` rechtstreeks in `csfTimerDuration`. Het
startpad converteert seconden wel naar milliseconden. Dit is gecontroleerd
via de ProgramTimer-factory en haar `toSeconds`-aanroepen.

Het is onbekend of de firmware dit bij opslaan/uitlezen normaliseert of dat
hier sprake is van een appfout. Daardoor is ongewijzigd kopiëren van een
`GetSavedCsf`-resultaat naar `StartOrModifyCsf` nog geen bewezen juiste route.
Descriptorgrenzen alleen lossen dat niet op: twee verschillend geschaalde
waarden kunnen allebei binnen een geadverteerd bereik vallen.

De juiste vervolgstap is een gerichte vergelijking tussen een bekend
opgeslagen programma, de getoonde looptijd en de uitgelezen parameters.
[READONLY-PROBE.md](READONLY-PROBE.md) beschrijft het daarvoor voorbereide
hulpmiddel. Er is geen programma-ID, timereenheid of unbridge-commando gegokt.

Een nieuwe, afzonderlijke route gebruikt vier concrete records uit de openbare
catalogus. Die records en de appcode onderbouwen exacte standaardstarts zonder
een opgeslagen CSF-bericht te hergebruiken. Hun initiële timerwaarde nul is via
de volledige mapper- en startketen bewezen. Daarom zijn deze vier starts nu
lokaal voorbereid; zie [ASSIST-PRESETS.md](ASSIST-PRESETS.md). Dit verandert de
onzekerheid over opgeslagen Assists of gewone timer-setters niet.

## Aanvullend opslagonderzoek

De Favorites-editor maakt één `SaveCsf`-lijst met maximaal drie opnieuw
uit de catalogus opgebouwde parameters voor slots 3, 4 en 5. Null-keuzes
worden uit die lijst verwijderd. Slots 1 en 2 en oude, onbekende parameters
worden in dit apppad niet teruggestuurd. Na het verzoek triggert de app
`GetSavedCsf`, maar de editor vergelijkt geen volledige parameters: hij
bewaart alleen de programma-ID's van slots 3–5 en wacht 500 milliseconden.

Voor de vier timerloze catalogusrecords geven seconden en milliseconden
dezelfde nulwaarde. Daarmee is hun parameterconstructie voor opslaan nu
bekend. Er blijft echter een andere vraag open: behoudt, wist of herstelt
de firmware een weggelaten slot, en blijven slots 1–2 gelijk? Een latere
geautoriseerde vergelijking moet de volledige lijsten vóór en na een
bewuste appwijziging vastleggen. Tot dan blijft opslagbediening achterwege;
een losse slotwijziging of clear-opdracht wordt niet gegokt.
