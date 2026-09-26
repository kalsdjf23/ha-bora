# Lokaal handmatig proefpakket

Op 26 september 2026 is `dist/bora-0.1.0-preparation-20260926-r2.zip` lokaal gebouwd voor
een latere, begeleide handmatige Home Assistant-proef. Het is niet geïnstalleerd,
gepubliceerd of aangeboden als HACS-releaseasset. Het bestaande `hacs.json`
blijft de normale repositoryindeling gebruiken, zonder `zip_release`.

Het pakket bevat **33 bestanden**: de runtime onder `custom_components/bora/`,
de projectlicentie als `custom_components/bora/LICENSE` en
`BORA-PREPARATION.txt`. Tests, onderzoeksbestanden, privéopnamen, virtuele
omgevingen en caches zitten niet in het archief. De licentie wordt niet als
`LICENSE` in de Home Assistant-configuratiemap geplaatst.

SHA-256 van dit ongewijzigde proefpakket:

```text
2f7cd58085977a57a0c3355dfd093f91d8cd84c5d2de6f8f3e14131c80119088
```

## Lokale controles

- Een tweede build met dezelfde broninhoud leverde identieke bytes op.
- De ZIP-CRC's, bestandsinventaris en JSON-bestanden zijn gecontroleerd.
- Het archief bevat geen absolute paden, `..`-padcomponenten of symlinks;
  er zijn geen paden die bij uitpakken buiten de doelmap terechtkomen.
- **714 tests slaagden vanuit een tijdelijke uitgepakte pakketboom.**
  Alleen tests en scripts werden toegevoegd als testharnas; de integratiecode
  kwam uit de ZIP. Dit was een offline proef met gesimuleerde Bluetooth,
  inclusief de correctie naar aanleiding van de [kookmeting](COOKING-OBSERVATION.md).

Het JSON-manifest naast het archief bevat de bestandsinventaris, checksums
en testuitkomst. De eerdere bestanden `bora-0.1.0-preparation.zip` en
`bora-0.1.0-preparation-20260926.zip` zijn historische kandidaten en bevatten
niet de volledige laatste correctie. Ze zijn niet overschreven of gepubliceerd.

Deze controles bewijzen de lokale verpakking en testbaarheid. Ze vervangen
geen echte HA-installatie, Bluetooth-pairing, fysieke bedieningsproef of
officiële HACS-validatie.

## Opnieuw bouwen

De bouwer staat in [scripts/build_package.py](../scripts/build_package.py).
Hij selecteert Python-bronbestanden, manifest, strings, vertalingen en het
bekende icoon, en weigert symlinks, inclusief directorysymlinks die een
recursieve bronselectie anders stilzwijgend zou overslaan. ZIP-volgorde,
tijdstempels, bestandsrechten en compressie-instellingen staan vast.

Kies een uitvoerpad dat nog niet bestaat, bijvoorbeeld:

```sh
python3.14 scripts/build_package.py --output dist/bora-0.1.0-preparation-check.zip
```

Een bestaand uitvoerbestand wordt geweigerd, niet overschreven. De bouwer
installeert niets en maakt geen verbinding met Home Assistant, GitHub of
een apparaat. Het proefpakket met bovenstaande hash blijft behouden;
gewijzigde runtimebron vereist een nieuw pakket en nieuwe controles.

Publicatie blijft een afzonderlijke stap volgens
[PUBLISHING.md](PUBLISHING.md).
