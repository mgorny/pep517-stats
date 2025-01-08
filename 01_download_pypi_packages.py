#!/usr/bin/env python3
# based on download_pypi_packages.py from CPython

import argparse
import glob
import os
import json
import re

from urllib.request import urlopen, urlretrieve


def download_package_code(name, package_json):
    source_index = -1
    for url_info in package_json["urls"]:
        if url_info["python_version"] == "source":
            filename = url_info["filename"]
            path = os.path.join("data", "pypi", filename)
            if not os.path.exists(path):
                url = url_info["url"]
                urlretrieve(url, path)
            return True
    return False


def main() -> None:
    argparser = argparse.ArgumentParser(
        description="Download sdists for to PyPI packages",
    )
    argparser.add_argument(
        "-n", "--number", type=int, default=100, help="Number of packages to download"
    )
    argparser.add_argument(
        "-a", "--all", action="store_true", help="Download all packages listed in the json file"
    )
    argparser.add_argument(
        "top_packages_json", help="top-pypi-packages-*.json file to process"
    )

    args = argparser.parse_args()
    number_packages = args.number
    all_packages = args.all

    with open(args.top_packages_json) as f:
        top_pypi_packages = json.load(f)
    if all_packages:
        top_pypi_packages = top_pypi_packages["rows"]
    elif number_packages >= 0 and number_packages <= 4000:
        top_pypi_packages = top_pypi_packages["rows"][:number_packages]
    else:
        raise AssertionError("Unknown value for NUMBER_OF_PACKAGES")

    try:
        os.mkdir(os.path.join("data", "pypi"))
    except FileExistsError:
        pass

    norm_re = re.compile(r"[.-]+")

    got_sdist = 0
    no_sdist = 0
    failed_metadata = 0

    for num, package in enumerate(top_pypi_packages):
        package_name = package["project"]

        matches = glob.glob(f"data/pypi/{package_name}-[0-9]*")
        if matches:
            print(f"[{num:4}] {package_name} found: {matches}")
            got_sdist += 1
            continue

        norm_package_name = norm_re.sub("_", package_name.lower())
        matches = glob.glob(f"data/pypi/{norm_package_name}-[0-9]*")
        if matches:
            print(f"[{num:4}] {package_name} found: {matches}")
            got_sdist += 1
            continue

        print(f"[{num:4}] Downloading JSON Data for {package_name}...")
        try:
            with urlopen(f"https://pypi.org/pypi/{package_name}/json") as f:
                package_json = json.load(f)
        except:
            failed_metadata += 1
            continue

        print(f"[{num:4}] Downloading {package_name} ...")
        if download_package_code(package_name, package_json):
            got_sdist += 1
        else:
            no_sdist += 1

    print(f"Summary: fetched: {got_sdist:4}; no sdist: {no_sdist:4}, "
          f"failed metadata: {failed_metadata:4}")


if __name__ == "__main__":
    main()
