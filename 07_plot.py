#!/usr/bin/env python

import argparse
import json
import sys

from collections import defaultdict

import matplotlib.pyplot as plt
from matplotlib_venn import venn3


FAMILY_COLORS = [
    (1, .9, 1),
    (.9, 1, 1),
    (1, 1, .9),
    (.9, .9, 1),
    (.9, .9, .9),
]

SETUPTOOLS_COLORS = [
    (1, .9, .9),
    (.9, 1, .9),
    (.8, .8, .8),
]


def replace_small_with_other(data: list[tuple[str, int]]) -> None:
    total = sum(kv[1] for kv in data)
    for i, (key, count) in enumerate(data):
        if count < total / 50:
            break
    data[i:] = [("other", sum(kv[1] for kv in data[i:]))]


def format_pct(num: float) -> str:
    if num > 10:
        return f"{int(num)}%"
    elif num < 1:
        return ""
    return f"{num:.1f}%"


def main() -> int:
    argp = argparse.ArgumentParser()
    argp.add_argument("packages_json",
                      help="File containing package analysis result",
                      type=argparse.FileType("r"))
    args = argp.parse_args()

    packages = json.load(args.packages_json)

    build_backend_families = defaultdict(int)
    setuptools_backends = defaultdict(int)
    setuptools_formats = defaultdict(set)

    for name, package in packages.items():
        build_backend_families[package["family"]] += 1
        if package["family"] == "setuptools":
            setuptools_backends[package["backend"]] += 1
            for st_format in package["formats"]:
                setuptools_formats[st_format].add(name)

    # 1) family pie chart
    fig, ax = plt.subplots()
    data = sorted(((family, count) for family, count
                   in build_backend_families.items()),
                  key=lambda kv: -kv[1])
    replace_small_with_other(data)
    total = sum(build_backend_families.values())
    for i, (family, count) in enumerate(data):
        if count < total / 50:
            break
    data[i:] = [("other", sum(kv[1] for kv in data[i:]))]

    ax.pie(x=[kv[1] for kv in data],
           labels=[kv[0] for kv in data],
           colors=FAMILY_COLORS,
           autopct=format_pct,
           pctdistance=.8,
           radius=1,
           wedgeprops={
               "width": .4,
               "edgecolor": "w",
           },
           startangle=180,
           counterclock=False)
    plt.savefig("fig1.svg",
                transparent=True,
                dpi=96,
                bbox_inches="tight")

    # 2) setuptools backend pie chart
    fig, ax = plt.subplots()
    data = sorted(((backend if backend is not None
                    else "(no build-backend)", count) for backend, count
                   in setuptools_backends.items()),
                  key=lambda kv: -kv[1])
    replace_small_with_other(data)
    total_backends = sum(build_backend_families.values())

    ax.pie(x=[kv[1] / total_backends for kv in data],
           labels=[kv[0] for kv in data],
           colors=SETUPTOOLS_COLORS,
           autopct=format_pct,
           pctdistance=.8,
           radius=1,
           wedgeprops={
               "width": .4,
               "edgecolor": "w",
           },
           startangle=180,
           counterclock=False,
           normalize=False)
    plt.savefig("fig2.svg",
                transparent=True,
                dpi=96,
                bbox_inches="tight")

    # 3) setuptools config format Venn diagram
    fig, ax = plt.subplots()
    formats = ("setup.py", "setup.cfg", "pyproject.toml")
    venn3([setuptools_formats[x] for x in formats],
          set_labels=formats)
    plt.savefig("fig3.svg",
                transparent=True,
                dpi=96,
                bbox_inches="tight")


if __name__ == "__main__":
    sys.exit(main())
