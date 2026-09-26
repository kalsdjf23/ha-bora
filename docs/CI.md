# Continuous integration

The `Tests` workflow runs on every push, pull request and manual dispatch.
Two independent jobs run Ruff and the offline tests, and the official
Home Assistant hassfest action, respectively. Tests use simulated Bluetooth
connections and do not validate physical appliance behavior.

The test environment uses Ubuntu 24.04 and Python 3.14.7. This combination
appears in the official [GitHub Actions Python build manifest](https://github.com/actions/python-versions/blob/main/versions-manifest.json).
The pinned [test plugin 0.13.366](https://pypi.org/project/pytest-homeassistant-custom-component/0.13.366/)
requires Python 3.14 or newer and Home Assistant 2026.9.3. The workflow installs
`requirements-test.txt`, then checks dependency consistency with `pip check`.
Selecting this environment alone does not establish compatibility; a successful
GitHub run is needed to confirm that installation and tests pass on that runner.

The [first private GitHub run](https://github.com/kalsdjf23/ha-bora/actions/runs/36221654783)
on commit `9c4495b0a10c6b549cfcafba4b54b006c1952ee5` passed:
**720 tests, 96% coverage**, Ruff, `pip check` and the official hassfest action.
This run used Ubuntu 24.04 and Python 3.14.7. It did not include HACS validation.

## Action references and permissions

- [`actions/checkout@v7`](https://github.com/actions/checkout/tree/v7) checks out
  the tested commit without persisting checkout credentials.
- [`actions/setup-python@v7`](https://github.com/actions/setup-python/tree/v7)
  installs the selected Python version and maintains a pip cache keyed to
  `requirements-test.txt`.
- [`home-assistant/actions/hassfest@master`](https://github.com/home-assistant/actions/blob/master/hassfest/action.yml)
  starts the official `ghcr.io/home-assistant/hassfest` container.
- [`hacs/action@main`](https://github.com/hacs/action/blob/main/action.yml)
  remains available only for later, manually triggered public validation.

Both workflows receive only `contents: read`. No custom tokens, publication
steps, deployments or comment permissions are needed. The `v7`, `master` and
`main` refs and the hassfest and HACS container images can change upstream;
this is not a fully immutable toolchain. Hassfest therefore follows current
HA validation rules, while runtime tests remain on HA 2026.9.3. A future
upstream change may cause a new CI failure.
The workflows use GitHub-hosted Linux runners with Docker. Moving to
self-hosted runners requires separate checks of Docker and the minimum
runner version for the Node 24 actions; that environment is not configured here.

## HACS remains deferred

`HACS validation (public repositories only)` has a manual trigger only.
For a private repository, the actual `Official HACS validation` job is skipped.
A separate job explicitly states in the log and run summary that HACS
validation was **not performed**; a green result for that notice is not a
successful HACS validation.

HACS supports only [public GitHub repositories](https://www.hacs.xyz/docs/publish/start/#general-requirements).
The validator uses repository metadata and a GitHub token; local tests and
hassfest do not replace that check. The manual workflow can run the actual
action when the repository is public, but it has not been dispatched. Making
the source public does not run HACS validation or submit the integration.
The manual workflow uses the
standard read-only workflow token and does not post a PR comment.
See also [PUBLISHING.md](PUBLISHING.md) and [VALIDATION.md](VALIDATION.md).
