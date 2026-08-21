#!/usr/bin/env bash
# Bring up the local dev stack.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose up --build
