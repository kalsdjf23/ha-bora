# Official hassfest validation

Validated locally on 2026-09-26 with the official Home Assistant Core **2026.9.3** validator, commit **`6de5eb18cd4502f94af44cfff3a02250d88716ed`**. Both normal validation and the additional `--requirements` check passed with exit code **0**, **1 integration**, **0 invalid integrations**, and **no warnings**.

No integration fixes were required by hassfest. This was a packaging/schema check using local files; it did not connect to an appliance, Home Assistant installation, Bluetooth adapter, or account, and did not publish anything.

## Validator and environment

The validator was downloaded from the [official Core tag](https://github.com/home-assistant/core/tree/6de5eb18cd4502f94af44cfff3a02250d88716ed/script/hassfest). Its [documented custom-integration support](https://developers.home-assistant.io/blog/2020/04/16/hassfest/) uses the same `--integration-path` validation mode as the GitHub action.

The checkout was `/private/tmp/bora-hassfest-core`; the validation interpreter was `/private/tmp/bora-hassfest-venv/bin/python` (Python 3.14.7). This separate temporary environment reused the existing Home Assistant 2026.9.3 dependencies through a `.pth` import path. No packages were installed, upgraded, or removed in the project's existing test environment.

Only the validator's missing dependencies were installed in the temporary environment: `infrared-protocols==9.0.0`, `tqdm==4.67.1`, `pipdeptree==2.26.1`, and `ruff==0.16.3`. Ruff matches the version pinned by Core 2026.9.3's hassfest Dockerfile inputs. The Core checkout's `homeassistant` path referred to the installed package of the same version, providing its manifests and constants. No validator source was modified and no validation plugins were skipped.

## Reproduction command

With the temporary environment and official checkout available, run this from the integration repository root. Resolving the integration path first keeps the command independent of the developer's home directory.

```sh
BORA_INTEGRATION_PATH="$(pwd)/custom_components/bora"
cd /private/tmp/bora-hassfest-core
PATH="/private/tmp/bora-hassfest-venv/bin:$PATH" \
VIRTUAL_ENV=/private/tmp/bora-hassfest-venv \
/private/tmp/bora-hassfest-venv/bin/python -m script.hassfest \
  --action validate \
  --requirements \
  --integration-path "$BORA_INTEGRATION_PATH"
```

The final run used `--requirements`; the earlier default run, which checks requirement declaration format, also passed. The additional check resolves the installed declared dependency tree and checks its package metadata and compatibility rules. `bleak-retry-connector==4.7.0` was already available; this run did not alter the integration requirements.

## Results

All 23 integration validation plugins completed successfully:

| Check group | Plugins | Result |
|---|---|---|
| Identity and packaging | `codeowners`, `integration_info`, `integration_type`, `json`, `manifest` | Pass |
| Configuration and UI metadata | `application_credentials`, `conditions`, `config_schema`, `icons`, `labs`, `quality_scale`, `services`, `translations`, `triggers`, `config_flow` | Pass |
| Dependencies | `dependencies`, `requirements` (including `--requirements`) | Pass |
| Discovery declarations | `bluetooth`, `dhcp`, `mqtt`, `ssdp`, `usb`, `zeroconf` | Pass |

Final summary:

```text
Integrations: 1
Invalid integrations: 0
```

The raw console output was retained locally in `/private/tmp/bora-hassfest-result.log`. Core-wide generation checks are outside custom-integration validation; the action's custom-integration mode also limits its checks to integration plugins.

Separately, `custom_components/bora/brand/icon.png` passed structural PNG verification: **256×256**, **8-bit RGBA**, **3,999 bytes**, valid signature/chunk CRCs, successful IDAT decompression, and 256 valid scanlines. The editable source `assets/icon.svg` exists. This separate check matters because the hassfest `icons` plugin concerns icon metadata, not proof that this custom brand image will render in a remote HACS installation.

## Remaining external validation

Hassfest success does not establish hardware compatibility, successful pairing on every adapter, command behavior, Linux/ESPHome proxy support, or correctness of the integration's runtime tests. Those have separate evidence and test coverage.

The GitHub repository is private. Public HACS validation, release download layout, installation from a release, and any HACS inclusion checks remain future checks after public publication is authorized. Local hassfest success is not a claim of HACS approval. The repository contains the official hassfest workflow; its remote checks and scope are documented in [CI.md](CI.md).
