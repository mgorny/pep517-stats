#!/bin/sh

set -x

mkdir -p data/unpacked || exit 1
cd data/unpacked || exit 1
find ../pypi -name '*.tar.gz' | xargs -t "-P$(nproc)" -n1 -I{} tar -xf {} '*/pyproject.toml' '*/setup.cfg' '*/setup.py'
