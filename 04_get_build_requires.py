#!/usr/bin/env python

import argparse
import json
import multiprocessing
import os
import pyproject_hooks
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import tomllib

from pathlib import Path


def process(args: tuple[str,dict,Path,Path]) -> None:
    dist, package, out_dir, sdist_dir = args
    out_path = out_dir / f"{dist}.out"
    # skip packages that were processed already
    if out_path.exists():
        return
    err_path = out_dir / f"{dist}.err"

    print(f"Processing {dist}")

    sdist = sdist_dir / f"{dist}.tar.gz"
    assert sdist.exists(), dist
    with (tempfile.TemporaryDirectory() as tempdir,
          open(err_path, "w") as err_file):
        temppath = Path(tempdir)
        requires = " ".join(
            shlex.quote(x) for x in package["requires"] or ["setuptools"]
        )

        with open(temppath / "run.sh", "w") as f:
            f.write(textwrap.dedent(f"""\
                set -e -x
                uv venv -p 3.11
                set +x
                . .venv/bin/activate
                set -x
                set -- {requires}
                if [ ${{#}} -gt 0 ]; then
                    uv pip install "${{@}}"
                fi
                tar -xf {shlex.quote(str(sdist.absolute()))}
            """))

        subp = subprocess.run(["sh", "run.sh"],
                              cwd=temppath,
                              stdout=err_file,
                              stderr=subprocess.STDOUT,
                              )
        if subp.returncode != 0:
            return

        try:
            with open(temppath / dist / "pyproject.toml", "rb") as f:
                bs = tomllib.load(f).get("build-system", {})
                backend = bs.get("build-backend")
                backend_path = bs.get("backend-path")
        except FileNotFoundError:
            backend = None
            backend_path = None

        backend = backend or "setuptools.build_meta:__legacy__"
        backend_import = backend.split(":")[0]
        backend = backend.replace(":", ".")

        with open(temppath / "run.py", "w") as f:
            f.write(textwrap.dedent(f"""\
                import sys

                backend_path = {backend_path!r}
                if backend_path is not None:
                    sys.path = backend_path + sys.path

                import {backend_import}
                backend = {backend}

                if hasattr(backend, "get_requires_for_build_wheel"):
                    requires = backend.get_requires_for_build_wheel()
                else:
                    requires = []

                with open("../out.txt", "w") as f:
                    f.write("".join(f"{{x}}\\n" for x in requires))
            """))

        subp = subprocess.run(["../.venv/bin/python", "../run.py"],
                              cwd=temppath / dist,
                              stdout=err_file,
                              stderr=subprocess.STDOUT,
                              )
        if subp.returncode != 0:
            return

        shutil.move(temppath / "out.txt", out_path)


def main() -> int:
    argp = argparse.ArgumentParser()
    argp.add_argument("sdist_dir",
                      help="Path to the directory with source distributions",
                      type=Path)
    argp.add_argument("packages_json",
                      help="File containing package analysis result",
                      type=argparse.FileType("r"))
    argp.add_argument("out_dir",
                      help="Directory to store output and state in",
                      type=Path)
    args = argp.parse_args()

    packages = json.load(args.packages_json)
    args.out_dir.mkdir(exist_ok=True)

    pool = multiprocessing.Pool()
    for x in pool.imap_unordered(process,
                                 ((dist, package, args.out_dir, args.sdist_dir)
                                  for dist, package in packages.items())):
        pass


if __name__ == "__main__":
    sys.exit(main())
