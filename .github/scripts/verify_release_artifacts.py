"""Check stable release source and built metadata without importing package code."""
from __future__ import annotations

import argparse
from email.parser import BytesParser
import json
import os
from pathlib import Path
import re
import tarfile
import tomllib
import zipfile


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def check_project(data: dict, project: str, version: str) -> None:
    require(data.get("project", {}).get("name") == project, "Project name mismatch")
    require(data["project"].get("version") == version, "Source version mismatch")


def check_metadata(content: bytes, project: str, version: str) -> None:
    metadata = BytesParser().parsebytes(content)
    require(len(metadata.get_all("Name", [])) == 1, "Expected one metadata Name")
    require(len(metadata.get_all("Version", [])) == 1, "Expected one metadata Version")
    require(canonical_name(metadata["Name"]) == project, "Artifact project mismatch")
    require(metadata["Version"] == version, "Artifact version mismatch")


def verify(root: Path, project: str, tag: str, dist: Path | None = None) -> None:
    require(bool(re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag)),
            "Expected a stable release tag")
    version = tag[1:]
    check_project(tomllib.loads((root / "pyproject.toml").read_text()), project, version)
    manifest = json.loads((root / ".release-please-manifest.json").read_text())
    require(manifest.get(".") == version, "Release Please manifest version mismatch")
    if dist is None:
        return
    files = list(dist.iterdir())
    require(len(files) == 2 and all(p.is_file() and not p.is_symlink() for p in files),
            "Expected exactly one wheel and one sdist, without extra files")
    wheels = [p for p in files if p.name.endswith(".whl")]
    sdists = [p for p in files if p.name.endswith(".tar.gz")]
    require(len(wheels) == len(sdists) == 1, "Expected one wheel and one sdist")
    wheel = wheels[0]
    parts = wheel.name[:-4].split("-")
    require(len(parts) in (5, 6) and canonical_name(parts[0]) == project
            and parts[1] == version, "Wheel filename mismatch")
    with zipfile.ZipFile(wheel) as archive:
        entries = [i for i in archive.infolist() if i.filename.endswith(".dist-info/METADATA")]
        require(len(entries) == 1, "Expected one wheel METADATA")
        expected = f"{project.replace('-', '_')}-{version}.dist-info/METADATA"
        require(entries[0].filename == expected, "Wheel metadata path mismatch")
        check_metadata(archive.read(entries[0]), project, version)
    sdist = sdists[0]
    stem = sdist.name[:-7]
    name, separator, file_version = stem.rpartition("-")
    require(bool(separator) and canonical_name(name) == project and file_version == version,
            "Sdist filename mismatch")
    with tarfile.open(sdist, "r:gz") as archive:
        for suffix in ("PKG-INFO", "pyproject.toml"):
            entries = [i for i in archive.getmembers() if i.name == f"{stem}/{suffix}"]
            require(len(entries) == 1 and entries[0].isfile(), f"Expected one sdist {suffix}")
            content_file = archive.extractfile(entries[0])
            require(content_file is not None, f"Missing sdist {suffix}")
            with content_file:
                content = content_file.read()
            if suffix == "PKG-INFO":
                check_metadata(content, project, version)
            else:
                check_project(tomllib.loads(content.decode()), project, version)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path)
    args = parser.parse_args()
    verify(Path.cwd(), os.environ["PUBLISH_PROJECT"], os.environ["RELEASE_TAG"], args.dist)
    print("Release source and requested distributions match the published tag.")
