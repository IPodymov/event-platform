#!/usr/bin/env bash
# Run the development stack in the foreground.
# Ctrl+C stops all services gracefully, then removes the containers and the
# network, so the published ports (web, PostgreSQL, Redis) are released.
# Data in the postgres_data volume is kept. Extra arguments go to `docker compose up`.
set -euo pipefail
cd "$(dirname "$0")/.."

cleanup() {
    # A second Ctrl+C must not interrupt the cleanup half-way.
    trap '' INT TERM
    echo
    echo "Stopping the stack and releasing ports..."
    docker compose down --remove-orphans
}
trap cleanup EXIT

docker compose up --build "$@"
