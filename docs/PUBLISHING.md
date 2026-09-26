# Publicatievoorbereiding

De gebruiker heeft op 26 september 2026 de privérepository
[kalsdjf23/ha-bora](https://github.com/kalsdjf23/ha-bora) en het uploaden van de
eerste versie toegestaan. Deze repository blijft privé. Openbare publicatie,
releases, HACS-aanmelding en installatie op de echte Home Assistant vereisen
een afzonderlijke opdracht.

## Wat klaarstaat

De map bevat een custom integration met domein `bora`, een configuratieflow,
vertalingen voor de configuratie, protocolcode, entiteiten, tests, een
MIT-licentie, `manifest.json`, `hacs.json` en een eigen projecticoon.
De versie in de metadata is `0.1.0`; dat is nog geen gepubliceerde release.

De huidige inhoud heeft lokaal 720 offline tests met 96% coverage van de
integratiecode en Ruff doorstaan. De officiële hassfest-validatie inclusief
`--requirements` slaagde eerder; de metadata zijn sindsdien ongewijzigd. Zie
[VALIDATION.md](VALIDATION.md) voor versies, coverage en bewijsgrenzen.
De officiële HACS-validatie blijft open zolang de repository privé blijft.
De [validator-entrypoint](https://github.com/hacs/integration/blob/main/action/action.py)
vereist een GitHub-token, een repositorynaam (`eigenaar/repository`) en een
categorie. De [repositorycode](https://github.com/hacs/integration/blob/main/custom_components/hacs/repositories/base.py)
haalt metadata, bestanden en releases van GitHub; er is geen invoer voor alleen
een lokale integratiemap. Een lokaal gestarte container verandert
dat niet: ook HACS' eigen [lokale containercontrole](https://github.com/hacs/integration/blob/main/.github/workflows/validate.yml)
gebruikt GitHub-repositories en een token. HACS vereist bovendien een
[publieke GitHub-repository](https://www.hacs.xyz/docs/publish/start/#general-requirements).
De lokale hassfest- en pakketcontroles vervangen deze validatie dus niet.

De [CI-workflows](CI.md) voeren tests, Ruff en de officiële hassfest uit bij
pushes en pull requests. De handmatige HACS-workflow slaat de echte validator
expliciet over zolang de repository privé is. Geen workflow publiceert een
release of maakt de repository openbaar.

Er is ook een [lokaal handmatig proefpakket](PACKAGING.md), met gecontroleerde
inventaris, reproduceerbare ZIP en 714 geslaagde offline tests vanuit de
uitgepakte integratiecode. Dit pakket is geen gepubliceerde release of
HACS-releaseasset en is niet op de echte Home Assistant geïnstalleerd.

Ook vier concrete X PURE Assist-starts zijn lokaal voorbereid. De vaste
catalogusmetadata zijn zonder account uitgelezen; de integratie gebruikt
geen runtimecloudaanroep. Zie [ASSIST-PRESETS.md](ASSIST-PRESETS.md) voor
de exacte standaardparameters en nog vereiste fysieke controles.

Het [opgeslagen-favorietenoverzicht](SAVED-ASSISTS.md) is eveneens voorbereid,
inclusief tests via HA-services, cacheverlies bij verbindingsherstel en geen
automatische favorietenvraag. Een lokale distributiecontrole heeft een echte
sessie-identificator uit testdata vervangen door een synthetische waarde;
een definitieve controle van alle releasebestanden blijft op de checklist.

De zonetimerstatus is leesbaar; timerbediening en overige onzekerheden blijven
zoals beschreven in [FEATURES.md](FEATURES.md) en
[TIMER-EVIDENCE.md](TIMER-EVIDENCE.md). De bredere functiedoelen staan in
[APP-COVERAGE.md](APP-COVERAGE.md). Ook is een begrensd
[read-only proefscript](READONLY-PROBE.md) voorbereid en met zeventien offline tests
getest; de volledige CLI/rapportworkflow is nog niet op hardware uitgevoerd.
Dezelfde read-only verbindingsklasse is wel tijdens de
[kookmeting](COOKING-OBSERVATION.md) gebruikt.

De GitHub-URL's en codeowner in het manifest verwijzen naar de aangemaakte
privérepository. Het ingelogde account en beheerdersrechten zijn gecontroleerd.
Dit maakt de integratie nog niet openbaar of beschikbaar via HACS.

Een publiek GitHub-project dat als aangepaste HACS-repository kan worden
toegevoegd en opname in de standaard HACS-catalogus zijn afzonderlijke stappen.
Geen van beide is met deze lokale voorbereiding afgerond.

## Open checklist vóór een eerste publicatie

- [x] Eigenaar en repositorynaam vastgelegd: `kalsdjf23/ha-bora`, privé.
- [ ] Publieke projectnaam en contact-/issuebeleid bevestigen.
- [ ] Bepalen welke fysiek gevalideerde functies en platforms de eerste release
  ondersteunt. De huidige Linux-, HA- en proxyclaims blijven onbewezen totdat
  de proeven in [VALIDATION.md](VALIDATION.md) zijn uitgevoerd.
- [ ] Beslissen of de eerste release expliciet experimenteel is en de
  beperkingen zichtbaar houden in README en releasebeschrijving.
- [ ] Verklaring van auteurschap en gekozen licentie controleren voor alle
  bestanden, afhankelijkheden en afgeleide fixtures. Geen officiële appbinary
  of andere niet voor distributie bedoelde bestanden opnemen.
- [ ] Bestanden én Git-geschiedenis controleren op adressen, serienummers,
  accountgegevens, tokens, lokale paden, ongeschoonde scans en privéopnamen.
  Testfixtures moeten alleen noodzakelijke, geschoonde protocoldata bevatten.
- [ ] Volledige offline tests en lint op de definitieve release-inhoud uitvoeren;
  resultaten en gebruikte HA/Python-versies vastleggen.
- [ ] Bevestigen dat de minimumversie bij de release nog aansluit op de geteste
  versie. De huidige metadata gebruikt de offline geteste versie 2026.9.3.
- [ ] Home Assistant-validatie opnieuw uitvoeren op de definitieve
  release-inhoud en de nog open HACS-validatie uitvoeren. Lokale aanwezigheid
  van `hacs.json` betekent niet dat HACS-controles al geslaagd zijn.
- [ ] Installatie, configuratie, opties, herauthenticatie, verwijderen en
  diagnose-download op een echte HA-installatie controleren.
- [ ] Publicatieverpakking nalopen: uitsluitend noodzakelijke runtimebestanden,
  documentatie, tests/fixtures en projectmetadata; geen lokale virtuele omgeving
  of onderzoeksbinary.
- [ ] Versienummer, wijzigingslog, release-instructies en documentatietaal voor
  de beoogde gebruikers afstemmen. Alle links controleren.
- [ ] Een afzonderlijke opdracht voor publicatie verkrijgen; pas daarna de
  repository openbaar maken en een release maken.

## Daarna: HACS

- [ ] Controleren of de gepubliceerde repository als aangepaste integration-
  repository kan worden toegevoegd, geïnstalleerd en bijgewerkt.
- [ ] De README aanvullen met de echte repository- en installatiegegevens.
- [ ] Pas na een afzonderlijk besluit standaardcatalogus-opname voorbereiden;
  de dan geldende voorwaarden en reviewprocedure opnieuw controleren.

Bronnen om op dat latere moment te raadplegen:
[HACS integration-publicatie](https://www.hacs.xyz/docs/publish/integration/),
[HACS standaardopname](https://www.hacs.xyz/docs/publish/include/) en
[Home Assistant integration-bestandsstructuur](https://developers.home-assistant.io/docs/creating_integration_file_structure/).
Deze aanvullende publicatie-eisen moeten bij de latere publicatie opnieuw
worden gecontroleerd; het brononderzoek naar de validator hierboven is geen
geslaagde HACS-validatie van dit project.
