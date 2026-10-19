#!/bin/sh
set -eu

alembic upgrade head
python -m mindora.seed
exec python -m mindora
