#!/usr/bin/env python

import argparse
import os
import sys
import tomllib
import typing

from collections import defaultdict
from pathlib import Path


BACKEND_FAMILIES = {
    "setuptools": [None, "setuptools.build_meta",
                   "setuptools.build_meta:__legacy__"],
    "poetry": ["poetry.core.masonry.api", "poetry.masonry.api",
               "poetry_dynamic_versioning.backend"],
    "flit": ["flit_core.buildapi", "flit.buildapi", "flit_scm:buildapi",
             "flit_gettext.scm"],
    "maturin": ["maturin"],
    "hatchling": ["hatchling.build", "hatchling.ouroboros"],
    "pdm": ["pdm.backend", "pdm.pep517.api", "pdm.backend.intree"],
    "scikit-build-core": ["scikit_build_core.build"],
    "mesonpy": ["mesonpy"],
    "whey": ["whey"],
    "jupyter-packaging": ["jupyter_packaging.build_api"],
    "sipbuild": ["sipbuild.api"],
    "sphinx-theme-builder": ["sphinx_theme_builder"],
    "pbr": ["pbr.build"],
}


class BuildSystem(typing.NamedTuple):
    build_backend: typing.Optional[str]
    backend_path: typing.Optional[list[str]]
    requires: typing.Optional[list[str]]

    has_pep621: bool


def read_pyproject_toml(directory: Path) -> BuildSystem:
    has_pep621 = False

    try:
        with directory.joinpath("pyproject.toml").open("rb") as f:
            toml = tomllib.load(f)
            bs = toml.get("build-system", {})
            has_pep621 = "project" in toml
    except FileNotFoundError:
        bs = {}

    return BuildSystem(bs.get("build-backend"),
                       bs.get("backend-path"),
                       bs.get("requires"),
                       has_pep621)


def main() -> int:
    argp = argparse.ArgumentParser()
    argp.add_argument("unpacked_data",
                      help="Path to the directory with unpacked sdists",
                      type=Path)
    args = argp.parse_args()

    backend_to_family_mapping = {}
    for family, members in BACKEND_FAMILIES.items():
        for member in members:
            backend_to_family_mapping[member] = family

    build_backend_families = defaultdict(lambda: defaultdict(int))
    setuptools_formats = defaultdict(int)
    setuptools_wheel_deps = 0
    other_backends_using_setuptools = defaultdict(int)

    for i, dist in enumerate(args.unpacked_data.iterdir()):
        if i % 200 == 0:
            print(f"Processed {i} packages.")
        backend, backend_path, requires, has_pep621 = read_pyproject_toml(dist)
        try:
            # 1) recognize public build backends
            family = backend_to_family_mapping[backend]
        except KeyError:
            # all custom backends should be specifying backend-path
            assert backend_path, (
                f"Unclassified public backend: {backend}, in {dist}")
            # 2) for custom backends, use requires to determine what
            # they're built on
            matches = [match for match in BACKEND_FAMILIES
                       if match in " ".join(requires)]
            assert len(matches) <= 1, (
                f"Multiple backend matched requires: {requires}, in {dist}")
            try:
                family = matches[0]
            except IndexError:
                family = "(custom)"
            backend = "(custom)"
        build_backend_families[family][backend] += 1

        # 3) check which setup files are used by setuptools projects
        formats = []
        if family == "setuptools":
            if has_pep621:
                formats.append("pyproject.toml")
            try:
                with dist.joinpath("setup.cfg").open("rb") as f:
                    for line in f:
                        if line.strip() == b"[metadata]":
                            formats.append("setup.cfg")
                            break
            except FileNotFoundError:
                pass
            if dist.joinpath("setup.py").exists():
                formats.append("setup.py")
            setuptools_formats[tuple(formats)] += 1

            # 4) check if wheel dependencies are specified
            if "wheel" in (" ".join(requires or [])):
                setuptools_wheel_deps += 1

        # 5) check for other build systems combining setuptools
        if family != "setuptools":
            if "setuptools" in (" ".join(requires)):
                other_backends_using_setuptools[family] += 1

    # print the data
    print("BUILD BACKEND STATS")
    for family, members in sorted(build_backend_families.items(),
                                  key=lambda kv: sum(kv[1].values()),
                                  reverse=True):
        if len(members) > 1:
            print(f"{family:20} {'(total)':35} {sum(members.values()):4}")
        for member, count in sorted(members.items(),
                                    key=lambda kv: kv[1],
                                    reverse=True):
            if member is None:
                member = "(none)"
            print(f"{family:20} {member:35} {count:4}")
    print()

    print("SETUPTOOLS CONFIG FORMATS")
    for formats, count in sorted(setuptools_formats.items(),
                                 key=lambda kv: kv[1],
                                 reverse=True):
        if not formats:
            formats = ["(none -- broken)"]
        print(f"{' + '.join(formats):56} {count:4}")
    print()

    print(f"SETUPTOOLS WHEEL DEPENDENCIES: {setuptools_wheel_deps:4}")
    print()

    print("OTHER BACKENDS USING SETUPTOOLS")
    for backend, count in sorted(other_backends_using_setuptools.items(),
                                 key=lambda kv: kv[1],
                                 reverse=True):
        print(f"{backend:56} {count:4}")


if __name__ == "__main__":
    sys.exit(main())
