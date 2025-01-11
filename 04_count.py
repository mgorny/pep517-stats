#!/usr/bin/env python

import argparse
import json
import os
import sys

from collections import defaultdict
from pathlib import Path


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
