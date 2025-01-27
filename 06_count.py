#!/usr/bin/env python

import argparse
import dataclasses
import json
import os
import packaging
import sys
import typing

from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


BACKGROUND_COLORS = [
    "#fee",
    "#efe",
    "#eef",
    "#ffe",
    "#eff",
    "#fef",
]

ALT_COLOR = "#eee"


SELECTED_DEP_FAMILIES = (
    "hatchling",
    "mesonpy",
    "pdm",
    "poetry",
    "scikit-build-core",
    "setuptools",
)

SELECTED_DEP_PACKAGES = {
    "setuptools",
    "wheel",
    "setuptools-scm",
    "cython",
    "hatch-vcs",
    "pytest-runner",
    "pbr",
    "pybind11",
    "cffi",
    "hatch-fancy-pypi-readme",
    "poetry-dynamic-versioning",
    "versioneer",
    "setuptools-rust",
    "hatch-jupyter-builder",
    "scikit-build",
    "setuptools-scm-git-archive",
    "hatch-requirements-txt",
    "setuptools-git-versioning",
    "versioningit",
    "hatch-nodejs-version",
    "jupyter-packaging",
    "nanobind",
    "py-cpuinfo",
    "hatch-regex-commit",
    "incremental",
    "poetry-plugin-tweak-dependencies-version",
    "setupmeta",
    "setuptools-dso",
    "calver",
    "hatch-cython",
    "poetry-plugin-drop-python-upper-constraint",
    "setuptools-changelog-shortener",
    "setuptools-declarative-requirements",
    "setuptools-git",
    "setuptools-golang",
    "changelog-chug",
    "cppy",
    "git-versioner",
    "hatch-docstring-description",
    "pdm-build-locked",
    "setuptools-download",
    "setuptools-lint",
    "setuptools-markdown",
    "setuptools-pipfile",
    "setuptools-twine",
    "vcversioner",
    "versioneer-518",
    "cmake",
    "ninja",
}


@lru_cache
def requirement_to_package(requirement: str) -> str:
    return canonicalize_name(Requirement(requirement).name)


def deduped_requirements(req_list: typing.Optional[list[str]]) -> set[str]:
    reqs = {requirement_to_package(req) for req in req_list or []}
    return reqs


@dataclasses.dataclass
class DepCount:
    direct: int = 0
    dynamic: int = 0

    @property
    def sum(self) -> int:
        return self.direct + self.dynamic


def main() -> int:
    argp = argparse.ArgumentParser()
    argp.add_argument("packages_json",
                      help="File containing package analysis result",
                      type=argparse.FileType("r"))
    args = argp.parse_args()

    packages = json.load(args.packages_json)

    build_backend_families = defaultdict(lambda: defaultdict(int))
    setuptools_formats = defaultdict(int)
    setuptools_wheel_deps = 0
    other_backends_using_setuptools = defaultdict(int)
    dependencies = defaultdict(lambda: defaultdict(DepCount))
    total_dependencies = defaultdict(int)

    for package in packages.values():
        build_backend_families[package["family"]][package["backend"]] += 1
        if package["family"] == "setuptools":
            setuptools_formats[tuple(package["formats"])] += 1
            # check if wheel dependencies are specified
            if "wheel" in (" ".join(package["requires"] or [])):
                setuptools_wheel_deps += 1
        else:
            # check for other build systems combining setuptools
            if "setuptools" in (" ".join(package["requires"])):
                other_backends_using_setuptools[package["family"]] += 1

        if package["family"] in SELECTED_DEP_FAMILIES:
            for req in deduped_requirements(package.get("requires")):
                dependencies[requirement_to_package(req)][package["family"]].direct += 1
            for req in deduped_requirements(package.get("requires-dynamic")):
                dependencies[requirement_to_package(req)][package["family"]].dynamic += 1
        for req in deduped_requirements((package.get("requires") or []) + (package.get("requires-dynamic") or [])):
            total_dependencies[req] += 1

    # 1) table with cumulative backend statistics
    print("<table id='table-1' style={{width: 'auto', margin: '0 2em', display: 'inline-block', verticalAlign: 'top'}}>")
    print("  <caption>Table 1. Cumulative backend use counts</caption>")
    print("  <tr><th>Family or backend</th><th>Count</th></tr>")

    family_colors = list(BACKGROUND_COLORS)
    for family, data in sorted(build_backend_families.items(),
                               key=lambda kv: sum(kv[1].values()),
                               reverse=True):
        if len(data) > 1:
            print(f"  <tr style={{{{ background: '{ family_colors.pop() }' }}}}>"
                  f"<td style={{{{ height: '4em' }}}}>{ family }</td><td align='right'>{ sum(data.values()) }</td></tr>")
        else:
            backend, count = next(iter(data.items()))
            if backend != "(custom)":
                backend = f"`{ backend }`"
            print(f"  <tr><td style={{{{ height: '3em' }}}}>{ backend }</td><td align='right'>{ count }</td></tr>")

    print("</table>")

    # 2) table with per-backend details
    print("<table id='table-2' style={{width: 'auto', margin: '0 2em', display: 'inline-block', verticalAlign: 'top'}}>")
    print("  <caption>Table 2. Detailed counts for common families</caption>")
    print("  <tr><th colspan='2'>Family and backend</th><th>Count</th></tr>")

    family_colors = list(BACKGROUND_COLORS)
    for family, data in sorted(build_backend_families.items(),
                               key=lambda kv: sum(kv[1].values()),
                               reverse=True):
        if len(data) > 1:
            color = family_colors.pop()
            print(f"  <tr style={{{{ background: '{ color }' }}}}>"
                  f"<th colspan='2'>{ family }</th><th></th></tr>")
            for backend, count in sorted(data.items(),
                                         key=lambda kv: kv[1],
                                         reverse=True):
                if backend is None:
                    backend = "(none)"
                elif backend != "(custom)":
                    backend = f"`{backend}`"
                print(f"  <tr style={{{{ background: '{ color }' }}}}>"
                      f"<td></td><td>{ backend }</td>"
                      f"<td align='right'>{ count }</td></tr>")

    print("</table>")

    print()

    # 3) table with setuptools configuration formats
    print("<table id='table-3' style={{width: 'auto', margin: '0 2em', display: 'inline-block', verticalAlign: 'top'}}>")
    print("  <caption>Table 3. Counts for setuptools configuration format combinations</caption>")
    print("  <tr><th>Formats</th><th>Count</th></tr>")

    for formats, count in sorted(setuptools_formats.items(),
                                 key=lambda kv: kv[1],
                                 reverse=True):
        if formats:
            print(f"  <tr><td>{ ' + '.join(f'`{x}`' for x in formats) }</td><td align='right'>{ count }</td></tr>")
        else:
            print(f"  <tr><td>(no configuration — broken distribution)</td><td align='right'>{ count }</td></tr>")

    print("</table>")

    # 4) table with totals
    print("<table id='table-4' style={{width: 'auto', margin: '0 2em', display: 'inline-block', verticalAlign: 'top'}}>")
    print("  <caption>Table 4. Cumulative counts for every configuration format</caption>")
    print("  <tr><th>Format</th><th>Total</th></tr>")

    setuptools_count = sum(build_backend_families["setuptools"].values())
    print(f"  <tr><td>(all packages)</td><td align='right'>{ setuptools_count }</td></tr>")

    for fformat in ("setup.py", "setup.cfg", "pyproject.toml"):
        count = sum(subcount for formats, subcount in setuptools_formats.items()
                    if fformat in formats)
        print(f"  <tr><td>`{ fformat }`</td><td align='right'>{ count }</td></tr>")

    print("</table>")
    print()

    # 5) requirements
    print("<table id='table-5'>")
    print(f"  <caption>Table 5. Selected build requirements (P = `pyproject.toml`, H = via hook)</caption>")
    print("  <tr><th rowspan='2'>Package</th>", end="")
    for family in SELECTED_DEP_FAMILIES:
        print(f"<th colspan='2' align='center'>{family}</th>", end="")
    print("<th rowspan='2' style={{ textAlign: 'center', width: '3.2em'}}>Total</th></tr>")
    print("  <tr>", end="")
    for family in SELECTED_DEP_FAMILIES:
        for header in ("P", "H"):
            print(f"<th style={{{{ textAlign: 'center', width: '3.2em'}}}}>{header}</th>", end="")
    print("</tr>")

    for i, (dependency, total) in enumerate(sorted(filter(lambda kv: kv[0] in SELECTED_DEP_PACKAGES,
                                                          total_dependencies.items()),
                                                   key=lambda kv: (-kv[1], kv[0]))):
        counts = dependencies[dependency]
        if i % 2 == 1:
            print(f"  <tr style={{{{ background: '{ ALT_COLOR }' }}}}>", end="")
        else:
            print(f"  <tr>", end="")
        print(f"<td>`{ dependency }`</td>", end="")
        for family in SELECTED_DEP_FAMILIES:
              print(f"<td align='right'>{ counts[family].direct }</td>"
                    f"<td align='right'>{ counts[family].dynamic }</td>",
                    end="")
        print(f"<td align='right'>{ total_dependencies[dependency] }</td></tr>")

    print("</table>")


if __name__ == "__main__":
    sys.exit(main())
