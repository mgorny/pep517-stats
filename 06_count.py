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
    dependencies = defaultdict(DepCount)

    for package in packages.values():
        build_backend_families[package["family"]][package["backend"]] += 1
        formats = package["formats"]
        if package["family"] == "setuptools":
            setuptools_formats[tuple(formats)] += 1
            # check if wheel dependencies are specified
            if "wheel" in (" ".join(package["requires"] or [])):
                setuptools_wheel_deps += 1
        else:
            # check for other build systems combining setuptools
            if "setuptools" in (" ".join(package["requires"])):
                other_backends_using_setuptools[package["family"]] += 1
        for req in deduped_requirements(package.get("requires")):
            dependencies[requirement_to_package(req)].direct += 1
        for req in deduped_requirements(package.get("requires-dynamic")):
            dependencies[requirement_to_package(req)].dynamic += 1

    # 1) table with cumulative backend statistics
    print("<table style={{width: 'auto', margin: '0 2em', display: 'inline-block', verticalAlign: 'top'}}>")
    print("  <caption>Table 1. Cumulative backend use counts</caption>")
    print("  <tr><th>Backend / family</th><th>Count</th></tr>")

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
    print("<table style={{width: 'auto', margin: '0 2em', display: 'inline-block', verticalAlign: 'top'}}>")
    print("  <caption>Table 2. Detailed counts for common families</caption>")
    print("  <tr><th>Family / backend</th><th>Count</th></tr>")

    family_colors = list(BACKGROUND_COLORS)
    for family, data in sorted(build_backend_families.items(),
                               key=lambda kv: sum(kv[1].values()),
                               reverse=True):
        if len(data) > 1:
            color = family_colors.pop()
            print(f"  <tr style={{{{ background: '{ color }' }}}}>"
                  f"<th>{ family }</th><th></th></tr>")
            for backend, count in sorted(data.items(),
                                         key=lambda kv: kv[1],
                                         reverse=True):
                if backend != "(custom)":
                    backend = f"`{backend}`"
                print(f"  <tr style={{{{ background: '{ color }' }}}}>"
                      f"<td>{ backend }</td><td align='right'>{ count }</td></tr>")

    print("</table>")

    print()

    # 3) table with setuptools configuration formats
    print("<table style={{width: 'auto', margin: '0 2em', display: 'inline-block', verticalAlign: 'top'}}>")
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
    print("<table style={{width: 'auto', margin: '0 2em', display: 'inline-block', verticalAlign: 'top'}}>")
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
    print("<table style={{width: 'auto', margin: '0 2em', display: 'inline-block', verticalAlign: 'top'}}>")
    print("  <caption>Table 5. Build requirements</caption>")
    print("  <tr><th>Package</th><th>`pyproject.toml`</th><th>via hook</th></tr>")

    for dependency, counts in sorted(dependencies.items(),
                                     key=lambda kv: (-kv[1].sum, kv[0])):
        print(f"  <tr><td>`{ dependency }`</td>"
              f"<td align='right'>{ counts.direct }</td>"
              f"<td align='right'>{ counts.dynamic }</td>"
              f"<td align='right'>{ counts.sum }</td></tr>")

    print("</table>")


if __name__ == "__main__":
    sys.exit(main())
