# Local package for manual testing

On 26 September 2026, `dist/bora-0.1.0-preparation-20260926-r5.zip` was built
locally for a later, supervised manual Home Assistant test. It has not been
installed, published or offered as a HACS release asset. The existing
`hacs.json` continues to use the normal repository layout, without `zip_release`.

The package contains **32 files**: the runtime under `custom_components/bora/`,
the project license as `custom_components/bora/LICENSE` and
`BORA-PREPARATION.txt`. Tests, research files, private recordings, virtual
environments and caches are excluded. The package contains only the English
translation; the Dutch translation was removed from the source before this
build. The license is not placed as `LICENSE` in the Home Assistant
configuration directory. The archive is **63,920 bytes**.

SHA-256 of this unchanged test package:

```text
d4c3d9dc3e0e34bc3256add427763cabffdc869e0790abd66678447b05a3c29f
```

## Local checks

- A second build from the same source contents produced identical bytes.
- ZIP CRCs, the exact runtime file inventory and all three JSON files were
  checked. The inventory excludes private recordings and research artifacts;
  source text was also checked for local user paths and common token/key markers.
- The archive contains no absolute paths, `..` path components or symlinks;
  no paths escape the destination directory when extracted.
- **823 tests passed in 6.37 seconds from a temporary extracted package tree.**
  Tests, scripts and the pytest configuration in `pyproject.toml` were added
  as a test harness; the integration code came from the ZIP. An import audit
  confirmed that all **26 loaded BORA runtime modules** came from that extracted
  tree. The run used Python **3.14.7** and Home Assistant **2026.9.3**, with
  **96% coverage** of integration code (**2,362 statements, 83 not covered**).
  This was an offline test with simulated Bluetooth, including the fix prompted
  by the [cooking observation](COOKING-OBSERVATION.md) and the RPC error-source
  context described in [READONLY-PROBE.md](READONLY-PROBE.md). It also covered
  the explicit Wi-Fi diagnostic status, its receipt timestamp, and cleanup
  of both optional caches after an invalidated diagnostic collection.

The sibling `bora-0.1.0-preparation-20260926-r5.manifest.json` contains the file
inventory, checksums, import evidence and test result. The five older archives
still match their recorded hashes and have not been overwritten or published.

The previous `bora-0.1.0-preparation-20260926-r4.zip` is now a historical
candidate. It contained **32 files**, was **63,353 bytes**, and passed **791 tests**
against its extracted runtime with **96% coverage** (**2,324 statements,
84 not covered**). It predates the optional Wi-Fi status sensor and its cache
lifecycle checks. Its unchanged SHA-256 is:

```text
72ae8c8fe47c7a98031de46b9b0a38352329fc3f0592a0677647d8df134e5e60
```

The older `bora-0.1.0-preparation-20260926-r3.zip` is also a historical
candidate. It contained **32 files**, was **61,245 bytes**, and passed **737 tests**
against its extracted runtime with **96% coverage** (**2,303 statements,
90 not covered**). It predates the latest initialization and diagnostics
error-attribution fixes. Its unchanged SHA-256 is:

```text
4e51ebdc4a94877936bcce204d7860c42700fb4fbc325d4a18784747a927e78a
```

The older `bora-0.1.0-preparation-20260926-r2.zip` contained **33 files**,
including the former Dutch translation, and passed **714 tests** against its
extracted runtime. Its unchanged SHA-256 is:

```text
2f7cd58085977a57a0c3355dfd093f91d8cd84c5d2de6f8f3e14131c80119088
```

The still earlier `bora-0.1.0-preparation.zip` and
`bora-0.1.0-preparation-20260926.zip` are also historical candidates. None of
these older archives represents the current r5 runtime and validation result.

These checks establish local packaging and testability. They do not replace
installation on a real HA instance, Bluetooth pairing, physical control tests
or official HACS validation.

## Rebuilding

The builder is [scripts/build_package.py](../scripts/build_package.py).
It selects Python source files, the manifest, strings, translations and the
known icon, and rejects symlinks, including directory symlinks that recursive
source selection would otherwise silently skip. ZIP ordering, timestamps,
file permissions and compression settings are fixed.

Choose an output path that does not exist, for example:

```sh
python3.14 scripts/build_package.py --output dist/bora-0.1.0-preparation-check.zip
```

An existing output file is rejected rather than overwritten. The builder
installs nothing and does not connect to Home Assistant, GitHub or an
appliance. The current r5 test package is retained; changes to runtime source
require a new package and new checks.

Publication remains a separate step under
[PUBLISHING.md](PUBLISHING.md).
