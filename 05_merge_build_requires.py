#!/usr/bin/env python

import argparse
import json
import os
import sys

from pathlib import Path


def main() -> int:
    argp = argparse.ArgumentParser()
    argp.add_argument("packages_json",
                      help="JSON data to be updated (in place)",
                      type=argparse.FileType("r+"))
    argp.add_argument("build_requires_dir",
                      help="Directory with build requirements output",
                      type=Path)
    args = argp.parse_args()

    packages = json.load(args.packages_json)
    for dist, package_data in packages.items():
        try:
            with open(args.build_requires_dir / f"{dist}.out", "r") as f:
                dyn_reqs = [l.strip() for l in f]
        except FileNotFoundError:
            dyn_reqs = None
        package_data["requires-dynamic"] = dyn_reqs

    args.packages_json.seek(0)
    args.packages_json.truncate(0)
    json.dump(packages, args.packages_json)


if __name__ == "__main__":
    sys.exit(main())
