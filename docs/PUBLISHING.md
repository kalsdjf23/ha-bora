# Release and HACS preparation

The source repository is [kalsdjf23/ha-bora](https://github.com/kalsdjf23/ha-bora).
It was initially created privately on 26 September 2026. The user subsequently
authorized making it public after the English-language review and validation.
This permission covers source access only: no release, HACS submission or
installation on the real Home Assistant instance is authorized by that change.

## What is ready

The project contains a custom integration with the domain `bora`, a config
flow, English interface text, protocol code, seven entity platforms, tests,
an MIT license, `manifest.json`, `hacs.json` and an original project icon.
The metadata version is `0.1.0`; this is not a published release.
Documentation, code, comments, interface text and GitHub material use English.

The current contents passed **823 local offline tests with 96% integration-code
coverage** and Ruff. Official hassfest validation, including `--requirements`,
passed earlier; the first three GitHub CI runs also passed. See
[VALIDATION.md](VALIDATION.md) for versions, coverage and evidence limits.

The [CI workflows](CI.md) run tests, Ruff and official hassfest on pushes and
pull requests. The HACS workflow is manual only and has not been dispatched.
Changing repository visibility does not trigger it. No workflow creates a
release, changes repository visibility or submits the integration to HACS.

A [local package for manual testing](PACKAGING.md) is also available: r5 has
32 files, a reproducible ZIP, and **823 passing offline tests using the extracted
integration code**. This package is not a published release or a HACS release
asset and has not been installed on the real Home Assistant instance.

Four specific X PURE Assist starts have been prepared locally. The fixed
catalogue metadata was retrieved without an account; the integration makes
no cloud calls at runtime. See [ASSIST-PRESETS.md](ASSIST-PRESETS.md) for the
exact defaults and outstanding physical checks. The
[saved favorites view](SAVED-ASSISTS.md) includes tests through HA services,
cache invalidation on reconnect and explicit reads only.

The optional **Last reported Wi-Fi status** sensor also uses explicit
diagnostic reads only. Its read timestamp and cache lifetime are tested through
HA services with a simulated peer; optional Wi-Fi hardware support is still
unverified. See [FEATURES.md](FEATURES.md) for enabling it and its limitations.

Zone timer status is readable; timer controls and other uncertainties remain
as described in [FEATURES.md](FEATURES.md) and [TIMER-EVIDENCE.md](TIMER-EVIDENCE.md).
The broader feature goals are documented in [APP-COVERAGE.md](APP-COVERAGE.md).
The bounded [read-only probe](READONLY-PROBE.md) has eighteen offline tests.
Its normal report workflow was [physically checked](HARDWARE-CHECKS.md) on the
paired Mac, without reproducing zone error code 14. Its read-only connection
class was also used during the [cooking observation](COOKING-OBSERVATION.md).
A fan-control trial did not establish successful control; its exact failing
RPC was not recorded. New error-origin diagnostics have offline coverage and
do not retroactively identify that RPC.

The GitHub URLs and codeowner in the manifest refer to the actual repository.
The account and administrator permissions were checked. A public source
repository, successful custom-repository installation, a published release
and inclusion in the default HACS catalogue are separate milestones.

## Before the first release

- [x] Record owner and repository name: `kalsdjf23/ha-bora`.
- [x] Obtain permission for public source access after English review and validation.
- [x] Use English for project documentation, source and interface text.
- [x] Check the initial upload and Git history for private identifiers, tokens,
  account data and unsanitized captures; keep only necessary, sanitized fixtures.
- [x] Build and verify a reproducible runtime package and run the offline suite
  against its extracted contents. Repeat if runtime contents change.
- [ ] Finalize the support scope and issue policy for the first release.
- [ ] Complete the physical checks in [VALIDATION.md](VALIDATION.md), including
  pairing on the target adapter, status, supported controls and recovery.
  Current Linux, HA and proxy support claims remain unproven.
- [ ] Keep the experimental status and remaining limitations visible in the
  README and release description.
- [ ] Recheck authorship and licensing of all final release files, dependencies
  and derived fixtures. Never include the official application binary.
- [ ] Review all final files and Git history again for private data.
- [ ] Run offline tests, lint and official Home Assistant validation against the
  final release commit. Record versions and results; minimum metadata currently
  uses the offline-tested Home Assistant version 2026.9.3.
- [ ] Test installation, configuration, options, reauthentication, removal and
  diagnostics download on a real Home Assistant installation.
- [ ] Align the version, changelog and installation instructions; check links and
  package contents. Keep virtual environments and private research out.
- [ ] Obtain a separate instruction before creating a release or submitting to HACS.

## Later HACS checks

Official HACS validation has not run. Its
[entrypoint](https://github.com/hacs/integration/blob/main/action/action.py)
requires a GitHub token, repository name and category. The
[repository code](https://github.com/hacs/integration/blob/main/custom_components/hacs/repositories/base.py)
reads GitHub metadata, files and releases rather than accepting only a local
integration directory. The project's earlier source review also covered the
[local container workflow](https://github.com/hacs/integration/blob/main/.github/workflows/validate.yml).
HACS requires a [public GitHub repository](https://www.hacs.xyz/docs/publish/start/#general-requirements).
Local hassfest and package checks do not replace HACS validation or establish approval.

When work on HACS publication is explicitly resumed:

- [ ] Run the official validator and address any findings.
- [ ] Verify adding, installing and updating the project as a custom integration
  repository, and document the tested installation method.
- [ ] Consider default-catalogue inclusion separately and recheck its current
  requirements before submitting anything.

References for that later stage:
[HACS integration publication](https://www.hacs.xyz/docs/publish/integration/),
[HACS default inclusion](https://www.hacs.xyz/docs/publish/include/) and
[Home Assistant integration file structure](https://developers.home-assistant.io/docs/creating_integration_file_structure/).
