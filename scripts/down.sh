#!/usr/bin/env bash
# Tear down the local dev stack.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose down
