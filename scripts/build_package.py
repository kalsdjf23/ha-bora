"""Build a local manual-install candidate; never install or publish it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

INTEGRATION = Path("custom_components/bora")
NOTICE = """BORA — local preparation, not a published release

This archive is for a later, supervised Home Assistant installation test.
It has not been validated on the actual Home Assistant Bluetooth adapter.
Device controls and cooking controls default to off. Physical acceptance,
first pairing, and hardware control tests remain open.

For a later manual installation, custom_components/bora belongs inside the
Home Assistant configuration directory. This file and the build script do
not perform installation, pairing, appliance control, or publication.

HACS metadata in the source project uses the normal repository layout;
this manual-install archive is not a HACS zip_release asset.
"""


def package_files(root: Path) -> dict[str, bytes]:
    """Collect source, translations and the known icon; omit all other files."""
    root = root.resolve()
    integration = root / INTEGRATION
    if any(parent.is_symlink() for parent in (integration, *integration.parents) if parent != root):
        raise ValueError(f"Symlink is not a package source: {INTEGRATION}")
    # Recursive globs do not descend into directory symlinks. Reject those
    # entries before selecting sources, instead of silently omitting modules.
    for path in integration.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Symlink is not a package source: {path.relative_to(root)}")
    paths = [
        *integration.rglob("*.py"),
        integration / "manifest.json",
        integration / "strings.json",
        *(integration / "translations").glob("*.json"),
        integration / "brand/icon.png",
    ]
    files = {}
    for path in sorted(paths):
        relative = path.relative_to(root)
        if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
            continue
        if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root):
            raise ValueError(f"Symlink is not a package source: {relative}")
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Package source escapes project: {relative}")
        files[relative.as_posix()] = path.read_bytes()
    # Keep the license with the integration instead of overwriting a file in
    # the user's HA configuration root during a later manual extraction.
    license_file = root / "LICENSE"
    if license_file.is_symlink():
        raise ValueError("License must be a regular project file")
    files[(INTEGRATION / "LICENSE").as_posix()] = license_file.read_bytes()
    files["BORA-PREPARATION.txt"] = NOTICE.encode("utf-8")
    return files


def build_package(root: Path, output: Path) -> str:
    """Write deterministic entries to a new archive and return its SHA256."""
    files = package_files(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle, ZipFile(handle, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            item = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            item.compress_type = ZIP_DEFLATED
            archive.writestr(item, data, compresslevel=9)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    version = json.loads((root / INTEGRATION / "manifest.json").read_text())["version"]
    if not isinstance(version, str) or not re.fullmatch(r"[0-9A-Za-z.+-]+", version):
        raise ValueError("Invalid package version")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=root / "dist" / f"bora-{version}-preparation.zip",
        help="New archive path; existing files are never overwritten",
    )
    args = parser.parse_args()
    digest = build_package(root, args.output)
    print(f"{digest}  {args.output}")


if __name__ == "__main__":
    main()
