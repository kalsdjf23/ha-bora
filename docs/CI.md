# CI voor de private repository

De workflow `Tests` draait bij iedere push, pull request en handmatige start.
Twee onafhankelijke jobs voeren Ruff en de offline tests uit, respectievelijk
de officiële Home Assistant-hassfest-action. Tests gebruiken gesimuleerde
Bluetooth-verbindingen en vormen geen fysieke apparaatvalidatie.

De testomgeving gebruikt Ubuntu 24.04 en Python 3.14.7. Die combinatie staat in
het officiële [Python-buildmanifest van GitHub Actions](https://github.com/actions/python-versions/blob/main/versions-manifest.json).
De vastgezette [testplugin 0.13.366](https://pypi.org/project/pytest-homeassistant-custom-component/0.13.366/)
vereist Python 3.14 of nieuwer en Home Assistant 2026.9.3. De workflow installeert
`requirements-test.txt` en controleert daarna de dependencyconsistentie met
`pip check`. Hiermee is de omgeving gekozen; pas een geslaagde GitHub-run
bewijst dat de installatie en tests op die runner slagen.

## Action-referenties en rechten

- [`actions/checkout@v7`](https://github.com/actions/checkout/tree/v7) haalt
  de geteste commit op zonder checkout-credentials achter te laten.
- [`actions/setup-python@v7`](https://github.com/actions/setup-python/tree/v7)
  installeert de gekozen Python-versie en bewaart een pip-cache gekoppeld aan
  `requirements-test.txt`.
- [`home-assistant/actions/hassfest@master`](https://github.com/home-assistant/actions/blob/master/hassfest/action.yml)
  start de officiële `ghcr.io/home-assistant/hassfest`-container.
- [`hacs/action@main`](https://github.com/hacs/action/blob/main/action.yml)
  blijft uitsluitend beschikbaar voor de latere, handmatige publieke validatie.

Beide workflows krijgen alleen `contents: read`. Er zijn geen eigen tokens,
publicatiestappen, deployments of commentaarrechten nodig. De refs `v7`,
`master` en `main` en de hassfest- en HACS-containerimages kunnen upstream veranderen;
dit is geen volledig onveranderlijk vastgezette toolchain. Hassfest volgt
daardoor actuele HA-validatieregels, terwijl de runtime-tests bij HA 2026.9.3
blijven. Een toekomstige upstreamwijziging kan een nieuwe CI-fout veroorzaken.
De workflows gebruiken GitHub-hosted Linux-runners met Docker. Overstappen naar
self-hosted runners vraagt een aparte controle van Docker en de minimale
runner-versie voor de Node 24-actions; die omgeving is hier niet ingesteld.

## HACS blijft uitgesteld

`HACS validation (public repositories only)` heeft alleen een handmatige
trigger. Bij een private repository wordt de echte `Official HACS validation`-
job overgeslagen. Een aparte job schrijft expliciet in de log en run-samenvatting
dat HACS-validatie **niet uitgevoerd** is; een groen resultaat van die melding
is geen geslaagde HACS-validatie.

HACS ondersteunt alleen [publieke GitHub-repositories](https://www.hacs.xyz/docs/publish/start/#general-requirements).
De validator gebruikt repositorymetadata en een GitHub-token; lokale tests en
hassfest vervangen die controle niet. Pas na afzonderlijk geautoriseerde
openbare publicatie kan de handmatige workflow de echte action uitvoeren.
Die gebruikt het standaard read-only workflowtoken en plaatst geen PR-comment.
Zie ook [PUBLISHING.md](PUBLISHING.md) en [VALIDATION.md](VALIDATION.md).
