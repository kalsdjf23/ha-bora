# Changelog

## 0.1.0 — privéconcept, niet uitgebracht

- Zelfstandige Home Assistant-integratie met Bluetooth-discovery, expliciete
  pairing, configuratieopties, statusstreams en periodieke controle.
- Afzuiging, kookzones, instellingen en diagnostiek gebaseerd op de
  apparaatdescriptor. Bediening standaard uit; koken vereist een extra optie.
- Eigen BRPC-codecs, checksums, fragmentatie, begrensde RPC's en herstel zonder
  herhalen van bedieningsopdrachten.
- Zonestatus-timers in seconden, onderbouwd door appgebruikscode; timerbediening
  en opgeslagen-programmahergebruik blijven apart te valideren.
- Vier concrete X PURE Assist-programma's uit de anoniem leesbare catalogus;
  lokale keuze, aparte startknop, exacte standaardparameters en verse controle
  op een uitgeschakelde, ongekoppelde zone. Geen fysieke proef uitgevoerd.
- Aparte Assist-fase, bevestigingsmelding en ontvangen doeltemperatuur van
  herkenbare programma's, onafhankelijk van de lokale keuze.
- Onderbouwde filtervervangmelding bij bekende recirculatie; geen verzonnen
  uren, percentage of resetfunctie.
- Expliciet uitlezen van opgeslagen Assist-favorieten, met plaatsnummers,
  herkende titels en leesdatum; cache vervalt bij fout of verbindingsverlies.
- Begrensde ontwikkelprobe met alleen leesmethoden en geredigeerde uitvoer.
- Begrensde verzoekregistratie koppelt fouten aan de juiste RPC en zone en
  bewaart streamafsluiting zonder ruwe foutteksten.
- Diagnoseverslag behoudt gelezen favorieten na afsluiten; anonimisering van
  ontbrekende numerieke identifiers wist geen gewone nulwaarden uit de status.
- Expliciete connect/disconnectdeadlines en gecontroleerde reauth-identiteit.
- Live kookmeting met bevestigde zone-/afzuigstanden en naloop. Daaruit volgde
  isolatie van tijdelijk ontbrekende zonestatus, correcte fout-/streamvolgorde
  en weigering van wachtende opdrachten naar onbeschikbare zones; offline getest.
- Centrale kookbedieningsgrenzen en vergelijking van gevraagde waarden met de
  teruggelezen status, zonder automatisch herhalen bij een afwijking.
- Gesaniteerde meetfixtures, offline tests, HA-runtime-tests en voorbereide
  Hassfest/HACS-workflows.
- Eerste private GitHub-versie met geslaagde Linux-CI (720 tests, Ruff,
  dependencycontrole en officiële hassfest). HACS-validatie blijft uitgesteld.
- Fysieke rustproef van de rapportworkflow geslaagd. Een aparte afzuigproef
  gaf code 12 en bevestigde geen bediening; afzonderlijk uitlezen bevestigde
  daarna afzuiging en alle zones op 0. Exacte mislukte RPC nog te bepalen.

Deze versie wordt voorbereid in een privérepository en is niet openbaar
uitgebracht of op de Home Assistant van de
gebruiker geïnstalleerd. Zie docs/VALIDATION.md voor bewijs en open tests.
